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

from . import mediametrie, model, news, polls, social, youtube

ROOT = Path(__file__).resolve().parent.parent
DATA = Path("data")
POLLS_FILE = DATA / "polls.json"
EVENTS_FILE = DATA / "events.json"
INTERVIEWS_FILE = DATA / "interviews.json"
FOLLOWERS_FILE = DATA / "followers.json"
YOUTUBE_FILE = DATA / "youtube.json"
INTERVIEW_VIDEOS_FILE = DATA / "interview_videos.json"
MEDIAMETRIE_FILE = DATA / "mediametrie.json"
YOUTUBE_CHANNELS = Path("config/youtube_channels.json")
PARTIES_FILE = Path("config/parties.json")
OUTPUT = Path("live_data.json")
START_DATE = date(2026, 7, 1)  # période couverte : presse, vidéos et audiences depuis cette date
CLAUDE_CALL_BUDGET = int(os.environ.get("CLAUDE_CALL_BUDGET", "150"))  # appels à Claude par exécution
HISTORY_DAYS = 180
KNOWN_WINDOW = 14      # jours pendant lesquels un événement est proposé au modèle comme déjà connu


def _load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def interview_videos(snapshots, candidates):
    """Dernier relevé de chaque vidéo d'entretien, les plus récentes d'abord."""
    latest = {}
    for s in snapshots:
        if s["video_id"] not in latest or s["date"] > latest[s["video_id"]]["date"]:
            latest[s["video_id"]] = s
    names = {c["id"]: c["name"] for c in candidates}
    rows = sorted(latest.values(), key=lambda s: s["published"], reverse=True)[:60]
    return [{"video_id": s["video_id"], "title": s["title"], "channel": s["channel"], "published": s["published"],
             "candidates": [names.get(c, c) for c in s["candidates"]], "views": s["views"],
             "url": f"https://www.youtube.com/watch?v={s['video_id']}"} for s in rows]


def subs_gain_7d(snapshots, pid):
    """Gain d'abonnés YouTube sur 7 jours : dernier relevé moins le relevé le plus proche d'il y a 7 jours."""
    rows = sorted((s for s in snapshots if s["id"] == pid and s.get("subscribers") is not None), key=lambda s: s["date"])
    if len(rows) < 2:
        return None
    last = rows[-1]
    earlier = [s for s in rows if (date.fromisoformat(last["date"]) - date.fromisoformat(s["date"])).days >= 7]
    if not earlier:
        return None
    return last["subscribers"] - earlier[-1]["subscribers"]


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
        search_articles, search_status = news.fetch_candidate_search(
            candidates, news.lean_by_outlet(feeds), START_DATE, today)
        articles += search_articles
        feed_status = feed_status + [search_status]
        articles = [a for a in articles if a["published"][:10] >= START_DATE.isoformat()]
        added = news.store(articles, candidates)
        _save(DATA / "feed_status.json", feed_status)
        ok = sum(1 for f in feed_status if f["ok"])
        print(f"✅ Presse : {ok}/{len(feed_status)} flux lus, {added} nouveaux articles")

    # 2b. Chaînes YouTube (automatique : une fois par jour)
    youtube_doc = _load(YOUTUBE_FILE, {"snapshots": []})
    interview_doc = _load(INTERVIEW_VIDEOS_FILE, {"snapshots": []})
    youtube_status = []
    if not args.no_fetch:
        channels = _load(YOUTUBE_CHANNELS, {"channels": []})["channels"]
        snapshots, youtube_status = youtube.collect(channels, today)
        youtube_doc["snapshots"] = youtube.add_snapshots(youtube_doc["snapshots"], snapshots)
        _save(YOUTUBE_FILE, youtube_doc)
        print(f"✅ YouTube : {len(snapshots)} chaîne(s) relevée(s)")

        # Vidéos d'entretiens cités dans la semaine sur les chaînes d'information
        key = os.environ.get("YOUTUBE_API_KEY")
        if key:
            cfg = _load(YOUTUBE_CHANNELS, {"channels": [], "interview_channels": []})
            channel_ids = {x["id"]: x["channel_id"] for x in youtube_doc["snapshots"] if x.get("channel_id")}
            names = {c["id"]: c["name"] for c in cfg["channels"]}
            pairs = [(channel_ids[c], names[c]) for c in cfg.get("interview_channels", []) if c in channel_ids]
            cands = _load(Path("config/candidates.json"), {"candidates": []})["candidates"]
            videos = youtube.collect_interview_videos(cands, pairs, START_DATE, today, key)
            interview_doc["snapshots"] = youtube.add_snapshots(
                interview_doc["snapshots"], [dict(v, id=v["video_id"]) for v in videos])
            _save(INTERVIEW_VIDEOS_FILE, interview_doc)
            print(f"✅ YouTube entretiens : {len(videos)} vidéo(s) citant un candidat")

    # Audiences TV hebdomadaires (Médiamétrie)
    tv_doc = _load(MEDIAMETRIE_FILE, {"weeks": []})
    if not args.no_fetch:
        known = {w["period"] for w in tv_doc["weeks"]}
        past = mediametrie.fetch_weeks_since(START_DATE, today, known)
        for w in past:
            tv_doc["weeks"] = mediametrie.add_week(tv_doc["weeks"], w)
        week = mediametrie.fetch_week(today=today)
        if week:
            tv_doc["weeks"] = mediametrie.add_week(tv_doc["weeks"], week)
        _save(MEDIAMETRIE_FILE, tv_doc)
        print(f"✅ Médiamétrie : {len(tv_doc['weeks'])} semaine(s) disponibles")

    # 3. Analyse Claude : chronologique depuis START_DATE, plafonnée par exécution
    events = _load(EVENTS_FILE, {"checked_days": [], "events": []})
    interviews_doc = _load(INTERVIEWS_FILE, {"checked_days": [], "interviews": []})
    if args.no_claude:
        print("ℹ️  Analyse Claude désactivée (--no-claude)")
    elif not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("⚠️  ANTHROPIC_API_KEY absente : analyse de tonalité et détection d'événements sautées", file=sys.stderr)
    else:
        import anthropic
        from . import analyze
        print(f"🤖 Analyse avec {analyze.MODEL} (effort {analyze.EFFORT}, {CLAUDE_CALL_BUDGET} appels max)")
        client = analyze._client()
        analyze.set_budget(CLAUDE_CALL_BUDGET)
        try:
            for day in news.all_days():
                if day < START_DATE.isoformat():
                    continue
                arts = news.load_day(day)
                n = analyze.score_articles(arts, candidates, client)
                if n:
                    news.save_day(day, arts)
                    print(f"   {day} : {n} articles analysés")
                if day >= today.isoformat():
                    continue
                # événements et interviews : chaque journée terminée une seule fois
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
        except analyze.BudgetExhausted:
            print(f"⏸️  Plafond de {CLAUDE_CALL_BUDGET} appels atteint : la suite sera traitée au prochain passage")
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
            "youtube_subs_gain_7d": subs_gain_7d(youtube_doc["snapshots"], inf["id"]),
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
        "media_by_outlet": model.outlet_matrix(days, candidates, today, window=(today - START_DATE).days + 1),
        "events": all_events[:40],
        "followers": followers,
        "youtube": yt_series,
        "interview_videos": interview_videos(interview_doc["snapshots"], candidates),
        "tv_weekly": tv_doc["weeks"][-1] if tv_doc["weeks"] else None,
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
