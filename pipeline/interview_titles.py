"""Entretiens de candidats repérés dans les titres d'articles : passages sur les chaînes TV et radios retenues.

Un titre compte s'il annonce un entretien ou un passage en plateau (« interview », « entretien »,
« invité du 20h », « face à … » en début de titre) et s'il cite un candidat. Seuls les médias de type
TV ou radio de config/medias.json sont gardés. Il n'y a pas d'audience ici.
"""
import json
import re
from pathlib import Path

from .model import canonical_outlet
from .youtube import alias_in_title

INTERVIEW = re.compile(
    r"\b(interviews?|entretiens?)\b"
    r"|\binvitée?\s+(?:du|de|d'|sur|dans)\b"
    r"|\bl'invité\s+(?:du|de|d'|sur)\b"
    r"|^face à (?=(?-i:[A-ZÉÈ][\w'’-]+ [A-ZÉÈ]))",
    re.IGNORECASE,
)
# vérifications de propos (« VRAI OU FAUX », « VÉRIF' ») : elles citent une interview, elles ne sont pas un passage
FACT_CHECK = re.compile(r"^(vrai ou faux|vérif)", re.IGNORECASE)


def _broadcast_channels():
    doc = json.loads(Path("config/medias.json").read_text(encoding="utf-8"))
    return {m["name"] for m in doc["medias"] if m["type"] in ("tv", "radio")}


def find_interviews(days, candidates):
    """Passages repérés, du plus récent au plus ancien. `days` : {jour: [articles]}.

    Un même titre sur une même chaîne n'est compté qu'une fois (date de première publication).
    """
    channels = _broadcast_channels()
    found = {}
    for day in sorted(days):
        for a in days[day]:
            channel = canonical_outlet(a.get("outlet"))
            title = a.get("title") or ""
            if channel not in channels or not INTERVIEW.search(title) or FACT_CHECK.search(title):
                continue
            ids = [c["id"] for c in candidates if alias_in_title(c.get("aliases") or [c["name"]], title)]
            if not ids:
                continue
            found.setdefault((channel, title), {
                "date": a["published"][:10], "candidates": ids, "channel": channel,
                "title": title, "url": a.get("url") or "",
            })
    return sorted(found.values(), key=lambda e: (e["date"], e["channel"]), reverse=True)
