"""Collecte des sondages du premier tour depuis Wikipédia (fr).

Source : « Liste de sondages sur l'élection présidentielle française de 2027 ».
On lit le wikitexte brut et on en extrait, pour chaque sondage, chaque
hypothèse (ligne du tableau) avec le score de chaque personnalité testée.
"""
import re
from datetime import date

import requests

WIKI_TITLE = "Liste_de_sondages_sur_l'élection_présidentielle_française_de_2027"
WIKI_RAW_URL = "https://fr.wikipedia.org/w/index.php"
USER_AGENT = "france-elections-predictor/1.0 (https://github.com/Lucas2207/france-voting-predictor)"

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}

LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
NUMBER_RE = re.compile(r"(?<![\w|])<?\s*(\d+(?:[,.]\d+)?)")


def fetch_wikitext():
    resp = requests.get(
        WIKI_RAW_URL,
        params={"title": WIKI_TITLE, "action": "raw"},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


def _split_attr(cell):
    """Sépare « attributs | contenu » en ignorant les | internes aux [[ ]] et {{ }}."""
    depth_sq = depth_br = 0
    last_sep = None
    i = 0
    while i < len(cell):
        two = cell[i:i + 2]
        if two == "[[":
            depth_sq += 1; i += 2; continue
        if two == "]]":
            depth_sq -= 1; i += 2; continue
        if two == "{{":
            depth_br += 1; i += 2; continue
        if two == "}}":
            depth_br -= 1; i += 2; continue
        if cell[i] == "|" and depth_sq == 0 and depth_br == 0:
            last_sep = i
        i += 1
    if last_sep is None:
        return "", cell.strip()
    return cell[:last_sep], cell[last_sep + 1:].strip()


def _span(attrs, name):
    m = re.search(name + r'\s*=\s*"?(\d+)', attrs)
    return int(m.group(1)) if m else 1


def _clean(text):
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"\{\{blanc\|([^}]*)\}\}", r"\1", text)
    text = re.sub(r"\{\{formatnum:([^}]*)\}\}", r"\1", text)
    text = text.replace("{{1er}}", "1").replace("'''", "")
    return text


def _parse_values(content):
    """Retourne [(valeur, personne_nommée_ou_None)] pour une cellule de score."""
    out = []
    for part in re.split(r"<hr\s*/?>", _clean(content)):
        stripped = re.sub(r"<[^>]+>", " ", part).strip()
        if not stripped or stripped.startswith("—") or stripped.startswith("-"):
            continue
        m = NUMBER_RE.search(stripped)
        if not m:
            continue
        names = LINK_RE.findall(part)
        if re.search(r"\]\]\s*(?:\{\{blanc\|)?/", part):
            # ex. « Bardella / Le Pen » : personne indéterminée, on garde le titulaire de colonne
            person = None
        else:
            # Le premier lien est la personne ; les suivants sont son parti, ex. « Hollande (PS) »
            person = re.sub(r"\s*\(.*\)$", "", names[0]).strip() if names else None
        out.append((float(m.group(1).replace(",", ".")), person))
    return out


def _parse_end_date(text, year):
    text = _clean(text)
    text = re.sub(r"<[^>]+>", " ", text)
    # « 21-22 octobre » -> 22 ; « 31 août - 2 septembre » -> 2 septembre
    matches = re.findall(r"(?:\d{1,2}\s*-\s*)?(\d{1,2})\s+([a-zéû]+)", text.lower())
    matches = [(d, m) for d, m in matches if m in MONTHS]
    if not matches:
        return None
    day, month = matches[-1]
    try:
        return date(year, MONTHS[month], int(day))
    except ValueError:
        return None


def _pollster(content):
    content = _clean(content)
    m = re.search(r"\[https?://\S+\s+([^\]]+)\]", content)
    name = m.group(1) if m else re.sub(r"<[^>]+>|\[|\]", "", content)
    url = re.search(r"\[(https?://\S+)", content)
    name = name.strip()
    name = {"Opinionway": "OpinionWay", "Harris-Interactive": "Harris Interactive", "Harris": "Harris Interactive"}.get(name, name)
    return name, (url.group(1) if url else None)


def parse_first_round(wikitext, min_year=2025):
    """Analyse les tableaux du premier tour. Retourne (sondages, annotations)."""
    start = wikitext.find("== Sondages concernant le premier tour ==")
    end = wikitext.find("== Sondages concernant le second tour ==")
    section = wikitext[start:end]

    polls, notes = [], []
    year = None
    lines = section.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = re.match(r"^=+\s*(.*?)\s*=+\s*$", line)
        if heading:
            y = re.findall(r"(20\d\d)", heading.group(1))
            if y:
                year = int(y[-1])
            i += 1
            continue
        if line.startswith("{|") and year and year >= min_year:
            j = i
            while j < len(lines) and not lines[j].startswith("|}"):
                j += 1
            p, n = _parse_table(lines[i + 1:j], year)
            polls.extend(p)
            notes.extend(n)
            i = j + 1
            continue
        i += 1
    return polls, notes


def _parse_table(lines, year):
    # Découpage en lignes de tableau
    rows, cur = [], []
    for line in lines:
        if line.startswith("|-"):
            rows.append(cur); cur = []
        else:
            cur.append(line)
    rows.append(cur)

    # Ligne d'en-tête contenant les noms : celle où les « ! » ont des [[Nom|Court]] sans Fichier
    columns = None  # liste de personnes, une entrée par colonne physique (après les 3 premières)
    for row in rows:
        heads = [l for l in row if l.startswith("!")]
        if heads and all("Fichier" not in h for h in heads) and any("[[" in h for h in heads):
            columns = []
            for h in heads:
                attrs, content = _split_attr(h[1:])
                names = LINK_RE.findall(content)
                person = re.sub(r"\s*\(.*\)$", "", names[0]).strip() if names else None  # peut être un parti (« Candidat PS »)
                columns.extend([person] * _span(attrs, "colspan"))
            break
    if columns is None:
        return [], []

    polls, notes = [], []
    carry = {}  # index de colonne -> (contenu, lignes restantes)
    for row in rows:
        cells = [l[1:] for l in row if l.startswith("|") and not l.startswith("|}")]
        if not cells or any(l.startswith("!") for l in row):
            continue
        if "Infobox Parti politique français/couleurs" in cells[0] and len(cells) > 5 and all(
            _split_attr(c)[1] == "" for c in cells
        ):
            continue  # ligne de bandeau de couleurs
        # Annotation pleine largeur (événement de campagne)
        if len(cells) == 1 and _span(_split_attr(cells[0])[0], "colspan") >= 8:
            notes.append(_parse_note(cells[0]))
            continue

        # Reconstitue les 3 premières colonnes avec les rowspan
        fixed = []
        queue = list(cells)
        for col in range(3):
            if col in carry and carry[col][1] > 0:
                fixed.append(carry[col][0])
                carry[col] = (carry[col][0], carry[col][1] - 1)
            elif queue:
                c = queue.pop(0)
                attrs, content = _split_attr(c)
                rs = _span(attrs, "rowspan")
                fixed.append(content)
                if rs > 1:
                    carry[col] = (content, rs - 1)
            else:
                fixed.append("")
        pollster, url = _pollster(fixed[0])
        end_date = _parse_end_date(fixed[1], year)
        sample = re.sub(r"\D", "", _clean(fixed[2])) or None
        if not end_date or not pollster:
            continue

        scores = {}
        col = 0
        for c in queue:
            attrs, content = _split_attr(c)
            span = _span(attrs, "colspan")
            holder = columns[col] if col < len(columns) else None  # None = « Autres »
            for value, named in _parse_values(content):
                person = named or holder
                if person and holder is not None:
                    scores[person] = value
            col += span
        if scores:
            polls.append({
                "pollster": pollster,
                "end_date": end_date.isoformat(),
                "sample": int(sample) if sample else None,
                "url": url,
                "scores": scores,
            })
    return polls, notes


def _parse_note(cell):
    _, content = _split_attr(cell)
    refs = re.findall(r"\|url=([^|}\s]+)", content)
    d = re.search(r"\{\{date\|(\d{1,2})\|(\d{1,2})\|(\d{4})\}\}", content)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", content, flags=re.S)
    text = re.sub(r"\{\{date\|(\d{1,2})\|(\d{1,2})\|(\d{4})\}\}", r"\1/\2/\3", text)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>|'''|''", "", text).strip()
    return {
        "date": date(int(d.group(3)), int(d.group(2)), int(d.group(1))).isoformat() if d else None,
        "text": text,
        "sources": refs[:3],
    }


def group_by_poll(rows):
    """Regroupe les hypothèses d'un même sondage en un score par personne.

    Les instituts testent plusieurs hypothèses ; une personnalité testée seule
    dans son couloir (ex. unique candidat du centre) y est artificiellement
    haute. On ne garde donc que les hypothèses les plus complètes (nombre de
    candidats >= maximum - 1) et on fait la moyenne sur celles-ci.
    """
    grouped = {}
    for r in rows:
        key = (r["pollster"], r["end_date"])
        g = grouped.setdefault(key, {**{k: r[k] for k in ("pollster", "end_date", "sample", "url")}, "_rows": []})
        g["_rows"].append(r["scores"])
    out = []
    for g in grouped.values():
        scenarios = g.pop("_rows")
        widest = max(len(s) for s in scenarios)
        kept = [s for s in scenarios if len(s) >= widest - 1]
        acc = {}
        for s in kept:
            for person, v in s.items():
                acc.setdefault(person, []).append(v)
        g["scores"] = {p: round(sum(v) / len(v), 2) for p, v in acc.items()}
        g["scenarios"] = len(scenarios)
        g["scenarios_used"] = len(kept)
        out.append(g)
    return sorted(out, key=lambda g: g["end_date"])
