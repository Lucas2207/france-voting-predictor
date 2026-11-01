"""Émissions et articles sur les candidats : relevés manuels, par personne.

Source : dossiers-candidats/<nom>/README.md (un dossier par candidat). Chaque tableau donne une
entrée par ligne :
- 4 colonnes (date, émission, titre, sujet) : émission Radio France, station lue dans l'émission ;
- 3 colonnes (date, titre, sujet) : article d'un autre média, nommé par le titre de section « ## Média » ou par
  la ligne « Source » du dossier (BFMTV) ;
- 2 colonnes (date, titre) : article BFMTV sans classement, compté comme sujet (« propos d'un autre » : thème).
"""
import json
import re
from pathlib import Path

from .model import canonical_outlet

MONTHS = {"janv": 1, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7, "août": 8,
          "sept": 9, "oct": 10, "nov": 11, "déc": 12}
YEAR = 2026
STATIONS = {"FI": "France Inter", "FC": "France Culture", "fi": "franceinfo", "franceinfo": "franceinfo"}
SUBJECTS = {"oui": "oui", "partiellement": "partiellement", "non": "non"}
OUTPUT = Path("data/radio_france.json")

# candidat -> dossier
DOSSIERS = {
    "lepen": "marine-le-pen", "melenchon": "jean-luc-melenchon", "philippe": "edouard-philippe",
    "glucksmann": "raphael-glucksmann", "attal": "gabriel-attal", "zemmour": "eric-zemmour",
    "retailleau": "bruno-retailleau", "lisnard": "david-lisnard", "roussel": "fabien-roussel",
    "arthaud": "nathalie-arthaud", "ruffin": "francois-ruffin", "dupontaignan": "nicolas-dupont-aignan",
    "polony": "natacha-polony",
}


def parse_date(text):
    t = text.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", t)
    if m:
        return f"{YEAR}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{1,2}) (\w+)\.?(?: (\d{4}))?$", t)
    month = MONTHS.get(m.group(2)) if m else None
    if month is None:
        return None
    year = int(m.group(3)) if m.group(3) else YEAR
    return f"{year}-{month:02d}-{int(m.group(1)):02d}"


def station_of(emission):
    m = re.search(r"\((FI|FC|fi|franceinfo)\)\s*$", emission)
    if m:
        return STATIONS[m.group(1)]
    for name in ("France Inter", "France Culture", "France Musique", "franceinfo"):
        if name in emission:
            return name
    return "ICI" if re.search(r"\bICI\b", emission, re.IGNORECASE) else "Radio France"


def _subject(text):
    word = text.strip().split(" ")[0].strip("()").lower() if text.strip() else ""
    return SUBJECTS.get(word)


def _media_of_heading(line):
    name = re.sub(r"^#+\s*", "", line).strip()
    name = re.sub(r"^\d+\.\s*", "", name)
    name = re.split(r" \(|,| :", name)[0].strip()
    if name.lower().startswith("radio france"):
        return ""
    return canonical_outlet(name) or name


def _default_media(text):
    m = re.search(r"Source\s*:\s*(https?://\S+)", text)
    if m and "radiofrance.fr" in m.group(1):
        return ""
    if m and "bfmtv.com" in m.group(1):
        return "BFMTV"
    return ""


def parse_markdown(text, candidate):
    """Entrées des tableaux, dans l'ordre du fichier."""
    rows = []
    media = _default_media(text)
    header = None
    for line in text.splitlines():
        if line.startswith("## ") or line.startswith("### "):
            media = _media_of_heading(line)
            header = None
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].lower().startswith("date"):
            header = cells
            continue
        if header is None or len(cells) < 2:
            continue
        date = parse_date(cells[0])
        if date is None:
            continue
        if len(cells) >= 4 and "émission" in header[1].lower():
            subject = _subject(cells[3])
            if subject is None:
                continue
            emission = re.sub(r"\s*\((FI|FC|fi|franceinfo)\)\s*$", "", cells[1])
            rows.append({"candidate": candidate, "date": date, "emission": emission,
                         "station": station_of(cells[1]), "title": cells[2], "subject": subject})
            continue
        title = cells[1]
        if len(cells) >= 3:
            subject = _subject(cells[2])
            if subject is None:
                continue
        else:
            subject = "partiellement" if "propos d'un autre" in title else "oui"
        rows.append({"candidate": candidate, "date": date, "emission": "",
                     "station": media or "Radio France", "title": title, "subject": subject})
    return rows


def _files():
    for candidate, folder in DOSSIERS.items():
        yield candidate, Path("dossiers-candidats") / folder / "README.md"


def build(root=Path(".")):
    """Lit les dossiers, retire les doublons, écrit data/radio_france.json."""
    rows, seen, surveyed = [], set(), []
    for candidate, rel in _files():
        path = root / rel
        if not path.exists():
            continue
        if candidate not in surveyed:
            surveyed.append(candidate)
        for row in parse_markdown(path.read_text(encoding="utf-8"), candidate):
            key = (row["candidate"], row["station"], row["date"], row["title"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"surveyed": surveyed, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


if __name__ == "__main__":
    print(f"{len(build())} entrées écrites dans {OUTPUT}")
