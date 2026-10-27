"""Parts d'audience TV hebdomadaires publiées par Médiamétrie.

Médiamétrie publie chaque semaine un communiqué (« L'audience de la télévision du ... ») avec un
export Excel des parts d'audience par chaîne. On prend le communiqué le plus récent affiché sur la
page d'accueil, puis son export. Le détail par émission (audience d'une diffusion précise) n'est pas
en accès libre : il reste dans les articles de presse, extraits par analyse.
"""
import io
import re
import sys
import unicodedata
from datetime import date, timedelta

import openpyxl
import requests

BASE = "https://www.mediametrie.fr"
WEEKLY_RE = re.compile(r'href="(/fr/audiences-et-resultats/tv/mediamat-hebdomadaire/[^"]+)"')
EXCEL_RE = re.compile(r'href="(/fr/audience/\d+/download-excel)"')
TIMEOUT = 30

# Libellés du fichier -> clés utilisées dans le site
CHANNELS = {
    "TF1": "tf1", "FRANCE 2": "france2", "FRANCE 3": "france3", "FRANCE 5": "france5", "M6": "m6",
    "W9": "w9", "ARTE": "arte", "TMC": "tmc", "CANAL+": "canalplus",
    "Chaînes nationales": "nationales", "Autres TV": "autres",
}


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text).replace("​", "").strip())
    return "".join(c for c in text if not unicodedata.combining(c)).upper()


def parse_shares(xlsx_bytes):
    """Lit l'export : total TV et part d'audience (%) de chaque chaîne suivie."""
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    total, shares = None, {}
    lookup = {_norm(k): v for k, v in CHANNELS.items()}
    for row in ws.iter_rows(values_only=True):
        cells = [c for c in row if c not in (None, "")]
        for i, cell in enumerate(cells):
            label = _norm(cell)
            if label.startswith("TOTAL TV") and i + 1 < len(cells) and isinstance(cells[i + 1], (int, float)):
                total = int(cells[i + 1])
            key = lookup.get(re.sub(r"\s*\(\d\)$", "", label).strip())
            if key and key not in shares:
                nxt = next((c for c in cells[i + 1:] if isinstance(c, (int, float))), None)
                if nxt is not None:
                    shares[key] = float(nxt)
    return {"total_tv": total, "shares": shares}


MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]
SLUG_PREFIX = "laudience-de-la-television-"


def week_slug(monday):
    """Fin de l'URL d'un communiqué hebdomadaire : du-19-au-25-octobre-2026 (ou à cheval sur deux mois)."""
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        dates = f"du-{monday.day}-au-{sunday.day}-{MONTHS[sunday.month - 1]}-{sunday.year}"
    else:
        dates = f"du-{monday.day}-{MONTHS[monday.month - 1]}-au-{sunday.day}-{MONTHS[sunday.month - 1]}-{sunday.year}"
    return SLUG_PREFIX + dates


def week_label(slug):
    return slug.replace(SLUG_PREFIX, "").replace("-", " ").replace(" au ", " au ")


def fetch_weeks_since(start, today, known_periods, get=requests.get):
    """Communiqués hebdomadaires depuis `start` (semaines complètes), absents de `known_periods`.

    Les communiqués anciens ne sont pas tous accessibles : ceux qui manquent sont ignorés.
    """
    monday = start - timedelta(days=start.weekday())
    weeks = []
    while monday + timedelta(days=6) < today:
        slug = week_slug(monday)
        label = week_label(slug)
        if label not in known_periods:
            try:
                page = get(f"{BASE}/fr/audiences-et-resultats/tv/mediamat-hebdomadaire/{slug}", timeout=TIMEOUT).text
                excel = EXCEL_RE.search(page)
                if excel:
                    parsed = parse_shares(get(BASE + excel.group(1), timeout=TIMEOUT).content)
                    if parsed["shares"]:
                        weeks.append({"fetched": today.isoformat(), "period": label, **parsed})
            except requests.RequestException:
                pass
        monday += timedelta(days=7)
    return weeks


def latest_release(get=requests.get):
    """Page et export du communiqué hebdomadaire le plus récent. Retourne (libellé, octets) ou None."""
    try:
        home = get(f"{BASE}/fr", timeout=TIMEOUT, headers={"User-Agent": "france-elections-predictor/1.0"}).text
        page_path = WEEKLY_RE.search(home)
        if not page_path:
            return None
        page = get(BASE + page_path.group(1), timeout=TIMEOUT).text
        excel_path = EXCEL_RE.search(page)
        if not excel_path:
            return None
        xlsx = get(BASE + excel_path.group(1), timeout=TIMEOUT).content
        label = week_label(page_path.group(1).rsplit("/", 1)[-1])
        return label, xlsx
    except requests.RequestException as exc:
        print(f"⚠️  Médiamétrie : {exc}", file=sys.stderr)
        return None


def fetch_week(get=requests.get, today=None):
    """Relevé hebdomadaire complet, ou None si indisponible."""
    release = latest_release(get)
    if release is None:
        return None
    label, xlsx = release
    parsed = parse_shares(xlsx)
    if not parsed["shares"]:
        print("⚠️  Médiamétrie : export lu sans chaîne reconnue", file=sys.stderr)
        return None
    return {"fetched": (today or date.today()).isoformat(), "period": label, **parsed}


def add_week(history, week):
    """Ajoute le relevé (une entrée par période)."""
    kept = [w for w in history if w["period"] != week["period"]]
    return sorted(kept + [week], key=lambda w: w["fetched"])
