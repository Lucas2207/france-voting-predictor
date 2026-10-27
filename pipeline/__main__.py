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

from . import model, news, polls

ROOT = Path(__file__).resolve().parent.parent
DATA = Path("data")
POLLS_FILE = DATA / "polls.json"
EVENTS_FILE = DATA / "events.json"
OUTPUT = Path("live_data.json")
ANALYSE_DAYS = 3       # jours récents (re)vérifiés à chaque exécution
MAX_ARTICLE_AGE = 7    # ignore les vieux articles remontés par certains flux
HISTORY_DAYS = 180


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
        cutoff = (today - timedelta(days=MAX_ARTICLE_AGE)).isoformat()
        articles = [a for a in articles if a["published"][:10] >= cutoff]
        added = news.store(articles, candidates)
        _save(DATA / "feed_status.json", feed_status)
        ok = sum(1 for f in feed_status if f["ok"])
        print(f"✅ Presse : {ok}/{len(feed_status)} flux lus, {added} nouveaux articles")

    # 3. Analyse Claude + 4. événements
    events = _load(EVENTS_FILE, {"checked_days": [], "events": []})
    recent_days = [d for d in news.all_days() if d >= (today - timedelta(days=ANALYSE_DAYS)).isoformat()]
    if args.no_claude:
        print("ℹ️  Analyse Claude désactivée (--no-claude)")
    elif not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("⚠️  ANTHROPIC_API_KEY absente : analyse de tonalité et détection d'événements sautées", file=sys.stderr)
    else:
        from . import analyze
        print(f"🤖 Analyse avec {analyze.MODEL} (effort {analyze.EFFORT})")
        client = analyze._client()
        for day in recent_days:
            arts = news.load_day(day)
            n = analyze.score_articles(arts, candidates, client)
            if n:
                news.save_day(day, arts)
                print(f"   {day} : {n} articles analysés")
            # événements : uniquement pour les journées terminées, une seule fois
            if day < today.isoformat() and day not in events["checked_days"]:
                found = analyze.detect_events(day, arts, candidates, client)
                events["events"].extend(found)
                events["checked_days"].append(day)
                print(f"   {day} : {len(found)} événement(s) détecté(s)")
        _save(EVENTS_FILE, events)

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


if __name__ == "__main__":
    main()
