"""Combinaison sondages + signal médiatique.

1. Moyenne des sondages : pour chaque date, dernier sondage de chaque institut
   publié dans les POLL_WINDOW jours, pondéré par l'ancienneté (demi-vie
   POLL_HALF_LIFE jours) et la taille d'échantillon.
2. Signal médiatique : part de voix et tonalité moyenne (−2..+2) sur les
   MEDIA_RECENT derniers jours, comparées à la période de référence qui précède.
   Chaque média compte pour une voix, quel que soit son volume d'articles.
3. Projection = moyenne des sondages + ajustement média, borné à ±MEDIA_CAP points.
   L'ajustement est une hypothèse de travail NON calibrée : il reste à zéro tant
   que l'historique médiatique est insuffisant.
"""
import math
import re
from datetime import date, timedelta

POLL_WINDOW = 30
POLL_HALF_LIFE = 14
MEDIA_RECENT = 7
MEDIA_BASELINE = 28
MEDIA_MIN_ARTICLES = 8


def _d(s):
    return date.fromisoformat(s)


def poll_average(polls, person, on):
    """Moyenne pondérée et intervalle à 95 % pour une personne à une date. None si pas de données."""
    latest = {}
    for p in polls:
        end = _d(p["end_date"])
        age = (on - end).days
        if age < 0 or age > POLL_WINDOW or person not in p["scores"]:
            continue
        if p["pollster"] not in latest or end > _d(latest[p["pollster"]]["end_date"]):
            latest[p["pollster"]] = p
    if not latest:
        return None
    pts, ws, n_total = [], [], 0
    for p in latest.values():
        age = (on - _d(p["end_date"])).days
        n = min(p.get("sample") or 1000, 3000)
        w = 0.5 ** (age / POLL_HALF_LIFE) * math.sqrt(n / 1000)
        pts.append(p["scores"][person]); ws.append(w); n_total += n
    mean = sum(v * w for v, w in zip(pts, ws)) / sum(ws)
    house_var = sum(w * (v - mean) ** 2 for v, w in zip(pts, ws)) / sum(ws)
    q = mean / 100
    sampling_sd = 100 * math.sqrt(max(q * (1 - q), 0.0001) / n_total)
    half = max(1.0, 1.96 * math.sqrt(sampling_sd ** 2 + house_var))
    return {"mean": round(mean, 1), "lo": round(max(0, mean - half), 1), "hi": round(mean + half, 1),
            "n_polls": len(latest)}


def _article_key(title):
    """Clé de rapprochement d'un titre : lettres et chiffres seulement, sans accents, 40 premiers caractères."""
    from .news import normalize

    return re.sub(r"[^a-z0-9]", "", normalize(title or ""))[:40]


def window_keys(days, dossier_rows, start, end):
    """Par candidat : ensemble des (date, titre) cités sur [start, end], collecte automatique et dossiers réunis.

    Une même date et un même titre ne comptent qu'une fois pour un candidat, quelle que soit la source.
    """
    keys = {}
    for day, articles in days.items():
        if not (start <= _d(day) <= end):
            continue
        for a in articles:
            if canonical_outlet(a.get("outlet")) is None:
                continue
            for cid in a.get("mentions") or []:
                keys.setdefault(cid, set()).add((day, _article_key(a.get("title"))))
    for r in dossier_rows:
        if start <= _d(r["date"]) <= end:
            keys.setdefault(r["candidate"], set()).add((r["date"], _article_key(r["title"])))
    return keys


def media_signal(days, cand_id, on, keys=None, dossier_rows=()):
    """Exposition médiatique d'un candidat sur 7 jours. Pas d'ajustement de la projection : seule la présence compte."""
    start = on - timedelta(days=MEDIA_RECENT - 1)
    if keys is None:
        keys = window_keys(days, dossier_rows, start, on)
    n = len(keys.get(cand_id, ()))
    total = sum(len(v) for v in keys.values())
    status = "ok" if n >= MEDIA_MIN_ARTICLES else "trop_peu_articles"
    return {
        "articles_7d": n,
        "share_7d": round(n / total, 3) if total else 0.0,
        "adjustment": 0.0,
        "status": status,
    }


_MEDIA_MAP = None


def canonical_outlet(name):
    """Nom officiel d'un média de config/medias.json, ou None si ce n'est pas un média retenu."""
    global _MEDIA_MAP
    if _MEDIA_MAP is None:
        import json
        from pathlib import Path
        doc = json.loads(Path("config/medias.json").read_text(encoding="utf-8"))
        _MEDIA_MAP = {}
        for m in doc["medias"]:
            for alias in [m["name"]] + m["aliases"]:
                _MEDIA_MAP[alias.strip().lower()] = m["name"]
    return _MEDIA_MAP.get((name or "").strip().lower())


def outlet_matrix(days, candidates, on, window=MEDIA_RECENT):
    """Articles dont le sujet est un candidat (nom ou alias dans le titre), par média retenu, sur la fenêtre."""
    from .news import tag_mentions

    start = on - timedelta(days=window - 1)
    acc = {}
    for day, articles in days.items():
        if not (start <= _d(day) <= on):
            continue
        for a in articles:
            media = canonical_outlet(a.get("outlet"))
            if media is None:
                continue
            for cid in tag_mentions({"title": a.get("title") or "", "summary": ""}, candidates):
                acc.setdefault(media, {}).setdefault(cid, 0)
                acc[media][cid] += 1
    return acc


def monthly_subjects(days, candidates):
    """Articles dont le titre porte sur un candidat, par mois, pour les médias retenus (mêmes critères que la matrice)."""
    from .news import tag_mentions

    counts = {}
    for day, articles in days.items():
        for a in articles:
            if canonical_outlet(a.get("outlet")) is None:
                continue
            for cid in tag_mentions({"title": a.get("title") or "", "summary": ""}, candidates):
                month = day[:7]
                counts.setdefault(cid, {}).setdefault(month, 0)
                counts[cid][month] += 1
    if not days:
        return {"months": [], "candidates": {}}
    first, last = min(days)[:7], max(days)[:7]
    y, m = int(first[:4]), int(first[5:7])
    months = []
    while f"{y:04d}-{m:02d}" <= last:
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return {"months": months, "candidates": {cid: [counts[cid].get(mo, 0) for mo in months] for cid in counts}}


def daily_media(days, candidates):
    """Série quotidienne : nombre d'articles de médias retenus qui citent chaque candidat."""
    series = []
    for day in sorted(days):
        row = {}
        for a in days[day]:
            if canonical_outlet(a.get("outlet")) is None:
                continue
            for cid in a.get("mentions") or []:
                row[cid] = row.get(cid, 0) + 1
        if row:
            series.append({"date": day, "candidates": {cid: {"articles": n} for cid, n in row.items()}})
    return series


def build(polls, days, candidates, today, history_start, dossier_rows=()):
    history = []
    d = history_start
    while d <= today:
        row = {}
        for c in candidates:
            avg = poll_average(polls, c["wiki"], d)
            if avg:
                row[c["id"]] = avg
        if row:
            history.append({"date": d.isoformat(), "polls": row})
        d += timedelta(days=1)

    week_ago = today - timedelta(days=7)
    projection = []
    keys = window_keys(days, dossier_rows, today - timedelta(days=MEDIA_RECENT - 1), today)
    for c in candidates:
        now = poll_average(polls, c["wiki"], today)
        if not now:
            continue
        prev = poll_average(polls, c["wiki"], week_ago)
        media = media_signal(days, c["id"], today, keys)
        projected = round(now["mean"] + media["adjustment"], 1)
        projection.append({
            "id": c["id"],
            "poll_avg": now["mean"],
            "poll_lo": now["lo"],
            "poll_hi": now["hi"],
            "n_polls": now["n_polls"],
            "change_7d": round(now["mean"] - prev["mean"], 1) if prev else None,
            "media": media,
            "projected": projected,
            "projected_lo": round(max(0, now["lo"] + media["adjustment"]), 1),
            "projected_hi": round(now["hi"] + media["adjustment"], 1),
        })
    projection.sort(key=lambda p: -p["projected"])
    return history, projection
