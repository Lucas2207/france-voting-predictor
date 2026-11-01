"""Émissions de Radio France dont le sujet est un candidat : relevé manuel (radiofrance.fr/personnes/…).

Chaque relevé est un tableau Markdown : date, émission (station entre parenthèses, ou « ICI », ou le nom de
la station), titre, et le sujet (« Oui », « Partiellement », « Non »). Les relevés sont regroupés dans
data/radio_france.json, un enregistrement par émission et par candidat.
"""
import json
import re
from pathlib import Path

from .model import canonical_outlet

MONTHS = {"janv": 1, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7, "août": 8,
          "sept": 9, "oct": 10, "nov": 11, "déc": 12}
STATIONS = {"FI": "France Inter", "FC": "France Culture", "fi": "franceinfo", "franceinfo": "franceinfo"}
# relevé source par candidat (fichiers Markdown à la racine du projet)
SOURCES = {
    "lepen": "radio-france-marine-le-pen-emissions.md",
    "melenchon": "radio-france-jean-luc-melenchon-emissions.md",
    "philippe": "radio-france-edouard-philippe-emissions.md",
    "glucksmann": "radio-france-raphael-glucksmann-emissions.md",
    "attal": "radio-france-gabriel-attal-emissions.md",
    "zemmour": "radio-france-eric-zemmour-emissions.md",
    "retailleau": "radio-france-bruno-retailleau-emissions.md",
    "lisnard": "radio-france-david-lisnard-emissions.md",
    "roussel": "radio-france-fabien-roussel-emissions.md",
    "arthaud": "radio-france-dossiers/nathalie-arthaud/README.md",
    "ruffin": "radio-france-dossiers/francois-ruffin/README.md",
}
# relevés sans émission (dossier vide) : le candidat est tout de même compté comme relevé
EMPTY_SURVEYS = {
    "dupontaignan": "radio-france-dossiers/nicolas-dupont-aignan/README.md",
}
OUTPUT = Path("data/radio_france.json")
SUBJECTS = {"Oui": "oui", "Partiellement": "partiellement", "Non": "non"}


def parse_date(text):
    m = re.match(r"\s*(\d{1,2}) (\w+)\.? (\d{4})", text)
    month = MONTHS.get(m.group(2)) if m else None
    if month is None:
        return None
    return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"


def station_of(emission):
    m = re.search(r"\((FI|FC|fi|franceinfo)\)\s*$", emission)
    if m:
        return STATIONS[m.group(1)]
    for name in ("France Inter", "France Culture", "France Musique", "franceinfo"):
        if name in emission:
            return name
    return "ICI" if re.search(r"\bICI\b", emission, re.IGNORECASE) else "Radio France"


def parse_markdown(text, candidate):
    """Lignes des tableaux : une entrée par ligne, dans l'ordre du fichier.

    Tableau à 4 colonnes (date, émission, titre, sujet) : émission Radio France, station lue dans l'émission.
    Tableau à 3 colonnes (date, titre, sujet) sous un titre « ## Média, … » : article d'un autre média.
    """
    rows = []
    media = ""
    for line in text.splitlines():
        if line.startswith("## "):
            media = canonical_outlet(re.split(r" \(|,", line[3:].strip())[0].strip()) or ""
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and media:
            date, title, subject = parse_date(cells[0]), cells[1], SUBJECTS.get(cells[2])
            if date is None or subject is None:
                continue
            rows.append({"candidate": candidate, "date": date, "emission": "", "station": media,
                         "title": title, "subject": subject})
            continue
        if len(cells) < 4:
            continue
        date = parse_date(cells[0])
        subject = SUBJECTS.get(cells[3])
        if date is None or subject is None:
            continue
        emission = re.sub(r"\s*\((FI|FC|fi|franceinfo)\)\s*$", "", cells[1])
        rows.append({"candidate": candidate, "date": date, "emission": emission, "station": station_of(cells[1]),
                     "title": cells[2], "subject": subject})
    return rows


def build(root=Path(".")):
    """Convertit les relevés Markdown en data/radio_france.json."""
    rows = []
    for candidate, name in SOURCES.items():
        rows += parse_markdown((root / name).read_text(encoding="utf-8"), candidate)
    surveyed = list(SOURCES) + list(EMPTY_SURVEYS)
    for candidate, name in EMPTY_SURVEYS.items():
        rows += parse_markdown((root / name).read_text(encoding="utf-8"), candidate)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"surveyed": surveyed, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


if __name__ == "__main__":
    print(f"{len(build())} émissions écrites dans {OUTPUT}")
