"""Émissions de Radio France dont le sujet est un candidat : relevé manuel (radiofrance.fr/personnes/…).

Le relevé est un tableau Markdown : date, émission (avec la station entre parenthèses ou « ICI »), titre,
et le sujet (« Oui », « Partiellement », « Non »). Le fichier source est converti en JSON dans data/.
"""
import re

MONTHS = {"janv": 1, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7, "août": 8,
          "sept": 9, "oct": 10, "nov": 11, "déc": 12}
STATIONS = {"FI": "France Inter", "FC": "France Culture", "fi": "franceinfo"}
SUBJECTS = {"Oui": "oui", "Partiellement": "partiellement", "Non": "non"}


def parse_date(text):
    m = re.match(r"\s*(\d{1,2}) (\w+)\.? (\d{4})", text)
    month = MONTHS.get(m.group(2)) if m else None
    if month is None:
        return None
    return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"


def station_of(emission):
    m = re.search(r"\((FI|FC|fi)\)\s*$", emission)
    if m:
        return STATIONS[m.group(1)]
    for name in ("France Inter", "France Culture", "franceinfo"):
        if name in emission:
            return name
    return "ICI" if re.search(r"\bICI\b", emission) else "Radio France"


def parse_markdown(text):
    """Lignes du tableau : une émission par ligne, dans l'ordre du fichier."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        date = parse_date(cells[0])
        subject = SUBJECTS.get(cells[3])
        if date is None or subject is None:
            continue
        emission = re.sub(r"\s*\((FI|FC|fi)\)\s*$", "", cells[1])
        rows.append({"date": date, "emission": emission, "station": station_of(cells[1]),
                     "title": cells[2], "subject": subject})
    return rows
