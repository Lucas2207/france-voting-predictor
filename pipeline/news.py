"""Collecte quotidienne des flux RSS et stockage par jour de publication (heure de Paris)."""
import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import requests

PARIS = ZoneInfo("Europe/Paris")
ARTICLES_DIR = Path("data/articles")
USER_AGENT = "Mozilla/5.0 (compatible; france-elections-predictor/1.0)"
SUMMARY_MAX = 600


def normalize(text):
    """Minuscules sans accents, pour la recherche d'alias."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _strip_html(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _published(entry, fallback):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).astimezone(PARIS)
    return fallback


def fetch_feeds(feeds):
    """Retourne (articles, état_des_flux)."""
    now = datetime.now(PARIS)
    articles, status = [], []
    for feed in feeds:
        try:
            resp = requests.get(feed["url"], timeout=25, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as exc:  # un flux en panne ne doit pas bloquer les autres
            status.append({"outlet": feed["outlet"], "ok": False, "error": str(exc)[:200]})
            continue
        count = 0
        for e in parsed.entries:
            link = (e.get("link") or "").split("?")[0].split("#")[0]
            title = _strip_html(e.get("title"))
            if not link or not title:
                continue
            articles.append({
                "id": hashlib.sha1(link.encode()).hexdigest()[:16],
                "outlet": feed["outlet"],
                "lean": feed["lean"],
                "url": link,
                "title": title,
                "summary": _strip_html(e.get("summary"))[:SUMMARY_MAX],
                "published": _published(e, now).isoformat(timespec="minutes"),
            })
            count += 1
        status.append({"outlet": feed["outlet"], "ok": True, "items": count})
    return articles, status


def tag_mentions(article, candidates):
    """Pré-filtre : identifiants des candidats dont un alias apparaît dans le titre ou le résumé."""
    text = normalize(f"{article['title']} {article['summary']}")
    found = []
    for c in candidates:
        for alias in c["aliases"]:
            if re.search(r"\b" + re.escape(normalize(alias)) + r"\b", text):
                found.append(c["id"])
                break
    return found


def day_path(day):
    return ARTICLES_DIR / f"{day}.json"


def load_day(day):
    p = day_path(day)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_day(day, articles):
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    articles = sorted(articles, key=lambda a: a["published"])
    day_path(day).write_text(json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")


def store(articles, candidates):
    """Fusionne les nouveaux articles dans data/articles/<jour>.json. Retourne le nombre ajouté."""
    by_day = {}
    for a in articles:
        by_day.setdefault(a["published"][:10], []).append(a)
    added = 0
    for day, items in by_day.items():
        existing = load_day(day)
        known = {a["id"] for a in existing}
        for a in items:
            if a["id"] in known:
                continue
            a["mentions"] = tag_mentions(a, candidates)
            existing.append(a)
            known.add(a["id"])
            added += 1
        save_day(day, existing)
    return added


def all_days():
    return sorted(p.stem for p in ARTICLES_DIR.glob("*.json"))
