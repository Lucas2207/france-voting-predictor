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
from urllib.parse import quote

PARIS = ZoneInfo("Europe/Paris")
ARTICLES_DIR = Path("data/articles")
USER_AGENT = "Mozilla/5.0 (compatible; france-elections-predictor/1.0)"
SUMMARY_MAX = 600
SEARCH_URL = "https://news.google.com/rss/search"


def month_windows(start, today):
    """Mois calendaires couvrant [start, today] : (début, fin exclue). Google renvoie ~100 résultats par requête."""
    from datetime import date
    out, cur = [], date(start.year, start.month, 1)
    while cur <= today:
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        out.append((max(cur, start), nxt))
        cur = nxt
    return out


def normalize(text):
    """Minuscules sans accents, pour la recherche d'alias."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


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


def lean_by_outlet(feeds):
    """Positionnement connu par média (config/feeds.json) ; 'non classé' sinon."""
    return {f["outlet"]: f["lean"] for f in feeds}


def fetch_candidate_search(candidates, leans, start, today):
    """Articles qui citent chaque candidat depuis `start`, via Google Actualités (couvre les sites sans flux RSS).

    Une requête par candidat et par mois. Le média d'origine est lu dans la source de chaque article.
    Retourne (articles, état).
    """
    now = datetime.now(PARIS)
    articles, errors, total = [], 0, 0
    queries = [(c, f'"{c["name"]}" after:{a.isoformat()} before:{b.isoformat()}')
               for c in candidates for a, b in month_windows(start, today)]
    for c, query in queries:
        total += 1
        url = f"{SEARCH_URL}?q={quote(query)}&hl=fr&gl=FR&ceid=FR:fr"
        try:
            resp = requests.get(url, timeout=25, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception:
            errors += 1
            continue
        for e in parsed.entries:
            src = e.get("source")
            outlet = src.get("title") if hasattr(src, "get") else None
            link = e.get("link") or ""
            title = _strip_html(e.get("title"))
            if not outlet or not link or not title:
                continue
            title = re.sub(r"\s+-\s+" + re.escape(outlet) + r"$", "", title)
            articles.append({
                "id": hashlib.sha1(link.encode()).hexdigest()[:16],
                "outlet": outlet,
                "lean": leans.get(outlet, "non classé"),
                "url": link,
                "title": title,
                "summary": "",
                "published": _published(e, now).isoformat(timespec="minutes"),
            })
    status = {"outlet": "Google Actualités (recherche par candidat)", "ok": errors < total,
              "items": len(articles), "error": f"{errors} requête(s) en échec sur {total}" if errors else None}
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
    """Fusionne les nouveaux articles dans data/articles/<jour>.json. Retourne le nombre ajouté.

    Un même titre publié le même jour n'est gardé qu'une fois (flux RSS et recherche se recouvrent).
    """
    by_day = {}
    for a in articles:
        by_day.setdefault(a["published"][:10], []).append(a)
    added = 0
    for day, items in by_day.items():
        existing = load_day(day)
        known = {a["id"] for a in existing}
        titles = {normalize(a["title"]) for a in existing}
        for a in items:
            if a["id"] in known or normalize(a["title"]) in titles:
                continue
            a["mentions"] = tag_mentions(a, candidates)
            existing.append(a)
            known.add(a["id"])
            titles.add(normalize(a["title"]))
            added += 1
        save_day(day, existing)
    return added


def all_days():
    return sorted(p.stem for p in ARTICLES_DIR.glob("*.json"))
