"""Vues et abonnés des chaînes YouTube (candidats et médias).

Source : YouTube Data API v3, `channels.list` avec `forHandle` (1 unité de quota par appel,
quota quotidien de 10 000 unités). Une clé d'API gratuite suffit ; elle est lue dans la
variable d'environnement YOUTUBE_API_KEY. Sans clé, la collecte est sautée.

Les vues sont cumulées depuis la création de la chaîne ; le gain d'une journée est donc la
différence entre deux relevés. Les abonnés sont arrondis par YouTube à 3 chiffres significatifs.
"""
import os
import re
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



PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def channel_videos(channel_id, since, key, get=requests.get):
    """Vidéos publiées par une chaîne depuis la date `since` (liste des uploads, 1 unité par page de 50)."""
    playlist = "UU" + channel_id[2:]  # playlist des envois d'une chaîne
    out, token = [], None
    while True:
        params = {"part": "snippet", "playlistId": playlist, "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        try:
            resp = get(PLAYLIST_URL, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            print(f"⚠️  YouTube liste {channel_id} : {exc}", file=sys.stderr)
            break
        if resp.status_code != 200:
            print(f"⚠️  YouTube liste {channel_id} : HTTP {resp.status_code}", file=sys.stderr)
            break
        body = resp.json()
        reached_start = False
        for it in body.get("items", []):
            sn = it.get("snippet", {})
            published = sn.get("publishedAt", "")
            if published[:10] < since.isoformat():
                reached_start = True
                break
            vid = sn.get("resourceId", {}).get("videoId")
            if vid:
                out.append({"video_id": vid, "title": sn.get("title", ""), "published": published})
        token = body.get("nextPageToken")
        if reached_start or not token:
            break
    return out


def video_views(video_ids, key, get=requests.get):
    """Vues actuelles de chaque vidéo (1 unité de quota par lot de 50)."""
    views = {}
    ids = list(dict.fromkeys(video_ids))
    for start in range(0, len(ids), 50):
        params = {"part": "statistics", "id": ",".join(ids[start:start + 50]), "key": key}
        try:
            resp = get(VIDEOS_URL, params=params, timeout=TIMEOUT)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        for it in resp.json().get("items", []):
            views[it["id"]] = int(it.get("statistics", {}).get("viewCount", 0))
    return views


def name_in_title(name, title):
    """Le nom complet, ou le nom de famille s'il est assez distinctif, figure dans le titre."""
    from .news import normalize
    t = normalize(title)
    parts = normalize(name).split()
    if normalize(name) in t:
        return True
    return len(parts[-1]) >= 5 and parts[-1] in t


def alias_in_title(aliases, title):
    """Un des alias complets figure dans le titre, en mots entiers (pas de nom de famille seul)."""
    from .news import normalize
    t = normalize(title)
    return any(re.search(r"\b" + re.escape(normalize(a)) + r"\b", t) for a in aliases)


def collect_interview_videos(candidates, channels, since, today, key, get=requests.get):
    """Vidéos publiées depuis `since` sur les chaînes d'information dont le titre cite un candidat (nom complet ou alias).

    `channels` : liste de (channel_id, nom de la chaîne). Retourne des relevés {date, video_id, ...}.
    """
    if not key:
        return []
    found = {}
    for channel_id, channel_name in channels:
        for v in channel_videos(channel_id, since, key, get=get):
            for cand in candidates:
                aliases = cand.get("aliases") or [cand["name"]]
                if not alias_in_title(aliases, v["title"]):
                    continue
                entry = found.setdefault(v["video_id"], {"video_id": v["video_id"], "title": v["title"],
                                                         "published": v["published"], "channel": channel_name,
                                                         "candidates": []})
                if cand["id"] not in entry["candidates"]:
                    entry["candidates"].append(cand["id"])
    views = video_views(list(found), key, get=get)
    return [{"date": today.isoformat(), **e, "views": views[e["video_id"]]} for e in found.values() if e["video_id"] in views]


def collect_own_videos(people, since, today, key, get=requests.get):
    """Toutes les vidéos publiées depuis `since` sur les chaînes propres des personnes suivies.

    `people` : liste de (pid, nom, channel_id). Pas de filtre sur le titre : ce sont leurs propres vidéos.
    """
    if not key:
        return []
    out = []
    for pid, name, channel_id in people:
        vids = channel_videos(channel_id, since, key, get=get)
        views = video_views([v["video_id"] for v in vids], key, get=get)
        for v in vids:
            if v["video_id"] not in views:
                continue
            out.append({"date": today.isoformat(), "id": v["video_id"], "video_id": v["video_id"], "title": v["title"],
                        "published": v["published"], "channel": name, "candidates": [pid], "views": views[v["video_id"]]})
    return out

