"""Vues et abonnés des chaînes YouTube (candidats et médias).

Source : YouTube Data API v3, `channels.list` avec `forHandle` (1 unité de quota par appel,
quota quotidien de 10 000 unités). Une clé d'API gratuite suffit ; elle est lue dans la
variable d'environnement YOUTUBE_API_KEY. Sans clé, la collecte est sautée.

Les vues sont cumulées depuis la création de la chaîne ; le gain d'une journée est donc la
différence entre deux relevés. Les abonnés sont arrondis par YouTube à 3 chiffres significatifs.
"""
import os
import sys

import requests

API_URL = "https://www.googleapis.com/youtube/v3/channels"
TIMEOUT = 20


def fetch_channel(handle, key, get=requests.get):
    """Statistiques d'une chaîne à partir de son @ . Retourne None si introuvable ou en erreur."""
    params = {"part": "statistics,snippet", "forHandle": handle.lstrip("@"), "key": key}
    try:
        resp = get(API_URL, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"⚠️  YouTube {handle} : {exc}", file=sys.stderr)
        return None
    if resp.status_code != 200:
        print(f"⚠️  YouTube {handle} : HTTP {resp.status_code}", file=sys.stderr)
        return None
    items = resp.json().get("items") or []
    if not items:
        print(f"⚠️  YouTube {handle} : chaîne introuvable", file=sys.stderr)
        return None
    item = items[0]
    stats = item.get("statistics", {})
    hidden = bool(stats.get("hiddenSubscriberCount"))
    return {
        "channel_id": item.get("id"),
        "title": item.get("snippet", {}).get("title"),
        "subscribers": None if hidden or "subscriberCount" not in stats else int(stats["subscriberCount"]),
        "views": int(stats.get("viewCount", 0)),
        "videos": int(stats.get("videoCount", 0)),
    }


def collect(channels, today, key=None, get=requests.get):
    """Un relevé par chaîne configurée pour la date `today`. Retourne (relevés, état)."""
    key = key if key is not None else os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return [], [{"id": None, "ok": False, "error": "YOUTUBE_API_KEY absente : collecte sautée"}]
    snapshots, status = [], []
    for ch in channels:
        if not ch.get("handle"):
            status.append({"id": ch["id"], "ok": False, "error": "handle non renseigné"})
            continue
        info = fetch_channel(ch["handle"], key, get=get)
        if info is None:
            status.append({"id": ch["id"], "ok": False, "error": "échec de la requête"})
            continue
        snapshots.append({"date": today.isoformat(), "id": ch["id"], "kind": ch["kind"],
                          "title": info["title"], "channel_id": info["channel_id"],
                          "subscribers": info["subscribers"], "views": info["views"], "videos": info["videos"]})
        status.append({"id": ch["id"], "ok": True, "title": info["title"]})
    return snapshots, status


def add_snapshots(store, new):
    """Ajoute les relevés en remplaçant ceux de même date et même chaîne."""
    keys = {(s["date"], s["id"]) for s in new}
    kept = [s for s in store if (s["date"], s["id"]) not in keys]
    return sorted(kept + new, key=lambda s: (s["date"], s["id"]))


def build_series(snapshots, channels):
    """Séries par chaîne : vues cumulées, gain depuis le premier relevé, abonnés."""
    dates = sorted({s["date"] for s in snapshots})
    by = {(s["date"], s["id"]): s for s in snapshots}
    out = {"dates": dates, "candidates": [], "media": [], "influencers": []}
    for ch in channels:
        views = [by[(d, ch["id"])]["views"] if (d, ch["id"]) in by else None for d in dates]
        subs = [by[(d, ch["id"])]["subscribers"] if (d, ch["id"]) in by else None for d in dates]
        if all(v is None for v in views):
            continue
        first = next((v for v in views if v is not None), None)
        series = {
            "id": ch["id"],
            "name": ch["name"],
            "color": ch.get("color"),
            "group": ch.get("group"),
            "views": views,
            "change": [None if v is None else v - first for v in views],
            "subscribers": subs,
            "latest": next((by[(d, ch["id"])] for d in reversed(dates) if (d, ch["id"]) in by), None),
        }
        out[{"candidate": "candidates", "media": "media"}.get(ch["kind"], "influencers")].append(series)
    return out

