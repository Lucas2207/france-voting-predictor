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
from datetime import date, timedelta

POLL_WINDOW = 30
POLL_HALF_LIFE = 14
MEDIA_RECENT = 7
MEDIA_BASELINE = 28
MEDIA_MIN_ARTICLES = 8
MEDIA_BETA = 1.5   # points d'intention par unité de variation de tonalité
MEDIA_CAP = 2.0


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


def _media_window(days, start, end, cand_id):
    """Statistiques d'un candidat sur [start, end] : nb d'articles, tonalité équilibrée par média."""
    per_outlet, n = {}, 0
    total_mentions = 0
    for day, articles in days.items():
        if not (start <= _d(day) <= end):
            continue
        for a in articles:
            for c in a.get("analysis") or []:
                total_mentions += 1
                if c["id"] == cand_id:
                    per_outlet.setdefault(a["outlet"], []).append(c["tone"])
                    n += 1
    if n == 0:
        return {"articles": 0, "tone": None, "share": 0.0, "_total": total_mentions}
    outlet_means = [sum(v) / len(v) for v in per_outlet.values()]
    return {
        "articles": n,
        "tone": round(sum(outlet_means) / len(outlet_means), 2),
        "share": round(n / total_mentions, 3) if total_mentions else 0.0,
        "_total": total_mentions,
    }


def media_signal(days, cand_id, on):
    recent = _media_window(days, on - timedelta(days=MEDIA_RECENT - 1), on, cand_id)
    base_end = on - timedelta(days=MEDIA_RECENT)
    base = _media_window(days, base_end - timedelta(days=MEDIA_BASELINE - 1), base_end, cand_id)
    analysed_days = sorted(d for d, arts in days.items() if any("analysis" in a for a in arts))
    history_days = (on - _d(analysed_days[0])).days + 1 if analysed_days else 0

    adj, status = 0.0, "ok"
    if history_days < MEDIA_RECENT * 2:
        status = "calibrage"  # pas encore de période de référence
    elif recent["articles"] < MEDIA_MIN_ARTICLES or base["articles"] < MEDIA_MIN_ARTICLES:
        status = "trop_peu_articles"
    else:
        adj = max(-MEDIA_CAP, min(MEDIA_CAP, MEDIA_BETA * (recent["tone"] - base["tone"])))
    return {
        "articles_7d": recent["articles"],
        "share_7d": recent["share"],
        "tone_7d": recent["tone"],
        "tone_baseline": base["tone"],
        "adjustment": round(adj, 1),
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
    """Tonalité moyenne par média et par candidat sur la fenêtre récente."""
    start = on - timedelta(days=window - 1)
    acc = {}
    for day, articles in days.items():
        if not (start <= _d(day) <= on):
            continue
        for a in articles:
            media = canonical_outlet(a["outlet"])
            if media is None:
                continue
            for c in a.get("analysis") or []:
                acc.setdefault(media, {}).setdefault(c["id"], []).append(c["tone"])
    out = {}
    for outlet, by_c in acc.items():
        out[outlet] = {cid: {"tone": round(sum(v) / len(v), 2), "n": len(v)} for cid, v in by_c.items()}
    return out


def daily_media(days, candidates):
    """Série quotidienne : nombre d'articles qui citent chaque candidat (mention dans le titre ou le résumé).

    Ce décompte ne demande aucune analyse : il ne dépend pas de l'API. La tonalité, elle, n'est
    calculée que sur les articles analysés.
    """
    series = []
    for day in sorted(days):
        row = {}
        for a in days[day]:
            if canonical_outlet(a.get("outlet")) is None:
                continue
            for cid in a.get("mentions") or []:
                r = row.setdefault(cid, {"n": 0, "_t": 0, "_k": 0})
                r["n"] += 1
                for c in a.get("analysis") or []:
                    if c["id"] == cid:
                        r["_t"] += c["tone"]; r["_k"] += 1
        if row:
            series.append({"date": day, "candidates": {
                cid: {"articles": r["n"], "tone": round(r["_t"] / r["_k"], 2) if r["_k"] else None}
                for cid, r in row.items()}})
    return series


def build(polls, days, candidates, today, history_start):
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
    for c in candidates:
        now = poll_average(polls, c["wiki"], today)
        if not now:
            continue
        prev = poll_average(polls, c["wiki"], week_ago)
        media = media_signal(days, c["id"], today)
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
