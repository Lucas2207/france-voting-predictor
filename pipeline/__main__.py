"""Pipeline quotidien : python -m pipeline

Étapes : sondages (Wikipédia) -> flux RSS -> analyse Claude -> événements -> live_data.json.
Options : --no-claude (saute l'analyse), --no-fetch (réutilise les données locales).
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import model, news, polls, social, youtube

ROOT = Path(__file__).resolve().parent.parent
DATA = Path("data")
POLLS_FILE = DATA / "polls.json"
EVENTS_FILE = DATA / "events.json"
INTERVIEWS_FILE = DATA / "interviews.json"
FOLLOWERS_FILE = DATA / "followers.json"
YOUTUBE_FILE = DATA / "youtube.json"
YOUTUBE_CHANNELS = Path("config/youtube_channels.json")
PARTIES_FILE = Path("config/parties.json")
OUTPUT = Path("live_data.json")
ANALYSE_DAYS = 7       # jours d'articles analysés à chaque exécution (= durée de conservation)
MAX_ARTICLE_AGE = 7    # ignore les vieux articles remontés par certains flux
HISTORY_DAYS = 180
KNOWN_WINDOW = 14      # jours pendant lesquels un événement est proposé au modèle comme déjà connu


def _load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-claude", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()

    os.chdir(ROOT)
    failed = False
    candidates = _load(Path("config/candidates.json"), {})["candidates"]
    feeds = _load(Path("config/feeds.json"), {})["feeds"]
    today = datetime.now(news.PARIS).date()

    # 1. Sondages
    poll_data = _load(POLLS_FILE, {"polls": [], "notes": []})
    if not args.no_fetch:
        try:
            rows, notes = polls.parse_first_round(polls.fetch_wikitext())
            grouped = polls.group_by_poll(rows)
            if len(grouped) < 10:
                raise ValueError(f"seulement {len(grouped)} sondages lus : format de page probablement modifié")
            poll_data = {"fetched": datetime.now(news.PARIS).isoformat(timespec="minutes"),
                         "source": "https://fr.wikipedia.org/wiki/" + polls.WIKI_TITLE,
                         "polls": grouped, "notes": notes}
            _save(POLLS_FILE, poll_data)
            print(f"✅ Sondages : {len(grouped)} enquêtes ({len(rows)} hypothèses)")
        except Exception as exc:
            print(f"⚠️  Sondages non mis à jour, données précédentes conservées : {exc}", file=sys.stderr)

    # 2. Flux RSS
    feed_status = _load(DATA / "feed_status.json", [])
    if not args.no_fetch:
        articles, feed_status = news.fetch_feeds(feeds)
        search_articles, search_status = news.fetch_candidate_search(candidates, news.lean_by_outlet(feeds))
        articles += search_articles
        feed_status = feed_status + [search_status]
        cutoff = (today - timedelta(days=MAX_ARTICLE_AGE)).isoformat()
        articles = [a for a in articles if a["published"][:10] >= cutoff]
        added = news.store(articles, candidates)
        _save(DATA / "feed_status.json", feed_status)
        ok = sum(1 for f in feed_status if f["ok"])
        print(f"✅ Presse : {ok}/{len(feed_status)} flux lus, {added} nouveaux articles")

    # 2b. Chaînes YouTube (automatique : une fois par jour)
    youtube_doc = _load(YOUTUBE_FILE, {"snapshots": []})
    youtube_status = []
    if not args.no_fetch:
        channels = _load(YOUTUBE_CHANNELS, {"channels": []})["channels"]
        snapshots, youtube_status = youtube.collect(channels, today)
        youtube_doc["snapshots"] = youtube.add_snapshots(youtube_doc["snapshots"], snapshots)
        _save(YOUTUBE_FILE, youtube_doc)
        print(f"✅ YouTube : {len(snapshots)} chaîne(s) relevée(s)")

    # 3. Analyse Claude + 4. événements
    events = _load(EVENTS_FILE, {"checked_days": [], "events": []})
    interviews_doc = _load(INTERVIEWS_FILE, {"checked_days": [], "interviews": []})
    recent_days = [d for d in news.all_days() if d >= (today - timedelta(days=ANALYSE_DAYS)).isoformat()]
    if args.no_claude:
        print("ℹ️  Analyse Claude désactivée (--no-claude)")
    elif not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("⚠️  ANTHROPIC_API_KEY absente : analyse de tonalité et détection d'événements sautées", file=sys.stderr)
    else:
        import anthropic
        from . import analyze
        print(f"🤖 Analyse avec {analyze.MODEL} (effort {analyze.EFFORT})")
        client = analyze._client()
        try:
            for day in recent_days:
                arts = news.load_day(day)
                n = analyze.score_articles(arts, candidates, client)
                if n:
                    news.save_day(day, arts)
                    print(f"   {day} : {n} articles analysés")
            # événements et interviews : chaque journée terminée une seule fois, dans l'ordre
            for day in news.all_days():
                if day >= today.isoformat():
                    continue
                arts = news.load_day(day)
                if day not in events["checked_days"]:
                    known = [{"id": e["id"], "title": e["title"], "date": e["date"]}
                             for e in events["events"]
                             if 0 <= (date.fromisoformat(day) - date.fromisoformat(e["date"])).days <= KNOWN_WINDOW]
                    found = analyze.detect_events(day, arts, candidates, client, known=known)
                    if found is not None:
                        analyze.apply_events(events["events"], found)
                        events["checked_days"].append(day)
                        print(f"   {day} : {len(found)} événement(s) détecté(s) ou mis à jour")
                if day not in interviews_doc["checked_days"]:
                    found = analyze.extract_interviews(day, arts, candidates, client)
                    if found is not None:
                        interviews_doc["interviews"] = social.merge_interviews(interviews_doc["interviews"], found)
                        interviews_doc["checked_days"].append(day)
                        print(f"   {day} : {len(found)} interview(s) avec audience")
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            # Sondages et presse restent publiés, mais l'exécution doit apparaître en échec
            print(f"❌ Clé API refusée, analyse Claude interrompue : {exc}", file=sys.stderr)
            failed = True
        events["events"] = analyze.dedupe_events(events["events"])
        _save(EVENTS_FILE, events)
        _save(INTERVIEWS_FILE, interviews_doc)

    # 5. Modèle et sortie
    days = {d: news.load_day(d) for d in news.all_days()}
    history, projection = model.build(poll_data["polls"], days, candidates, today,
                                      history_start=today - timedelta(days=HISTORY_DAYS))
    wiki_events = [{
        "date": n["date"], "title": n["text"], "description": "", "category": "campagne",
        "candidates": [], "origin": "wikipedia",
        "sources": [{"outlet": "Wikipédia", "title": "Annotation du tableau des sondages", "url": u} for u in n["sources"]],
    } for n in poll_data.get("notes", []) if n.get("date")]
    all_events = sorted(wiki_events + events["events"], key=lambda e: e["date"], reverse=True)

    parties = _load(PARTIES_FILE, {"parties": []})["parties"]
    followers_doc = _load(FOLLOWERS_FILE, {"entries": []})
    influencers = _load(Path("config/influencers.json"), {"influencers": []})["influencers"]
    followers = social.build_followers(followers_doc["entries"], candidates, parties, influencers, today)
    yt_channels = _load(YOUTUBE_CHANNELS, {"channels": []})["channels"]
    yt_series = youtube.build_series(youtube_doc["snapshots"], yt_channels)
    influencer_rows = []
    for inf in influencers:
        yt = yt_series["influencers"]
        yt_latest = next((s["latest"] for s in yt if s["id"] == inf["id"]), None)
        influencer_rows.append({
            "id": inf["id"], "name": inf["name"], "party": inf["party"], "statut": inf["statut"], "note": inf.get("note", ""),
            "followers": social.total(followers_doc["entries"], inf["id"], today),
            "youtube_views": yt_latest["views"] if yt_latest else None,
            "youtube_subscribers": yt_latest["subscribers"] if yt_latest else None,
        })
    interviews = [i for i in interviews_doc["interviews"] if i["date"] >= (today - timedelta(days=HISTORY_DAYS)).isoformat()]

    total_articles = sum(len(a) for a in days.values())
    analysed = sum(1 for a in days.values() for x in a if "analysis" in x)
    output = {
        "last_updated": datetime.now(news.PARIS).strftime("%Y-%m-%d %H:%M"),
        "today": today.isoformat(),
        "candidates": candidates,
        "projection": projection,
        "history": history,
        "polls": [p for p in poll_data["polls"] if p["end_date"] >= (today - timedelta(days=HISTORY_DAYS)).isoformat()],
        "media_daily": model.daily_media(days, candidates),
        "media_by_outlet": model.outlet_matrix(days, candidates, today),
        "events": all_events[:40],
        "followers": followers,
        "youtube": yt_series,
        "influencers": influencer_rows,
        "youtube_status": youtube_status,
        "parties": [{k: p[k] for k in ("id", "name", "badge", "color")} for p in parties],
        "interviews": interviews,
        "interview_summary": social.interview_summary(interviews, [c["id"] for c in candidates]),
        "sources": {
            "polls": poll_data.get("source"),
            "polls_fetched": poll_data.get("fetched"),
            "feeds": feed_status,
            "articles_total": total_articles,
            "articles_analysed": analysed,
            "media_since": min(days) if days else None,
        },
        "parameters": {k: getattr(model, k) for k in (
            "POLL_WINDOW", "POLL_HALF_LIFE", "MEDIA_RECENT", "MEDIA_BASELINE",
            "MEDIA_MIN_ARTICLES", "MEDIA_BETA", "MEDIA_CAP")},
    }
    _save(OUTPUT, output)
    print(f"✅ {OUTPUT} écrit : {len(projection)} candidats, {len(history)} jours d'historique, "
          f"{analysed}/{total_articles} articles analysés")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
