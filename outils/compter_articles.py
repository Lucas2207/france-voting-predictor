"""Compte, par média et par candidat, les articles d'une liste extraite d'un site (recherche, plan de site…).

Entrée : un fichier JSON, liste d'articles {"media", "url", "date", "titre", "chapo"} (« title » et « chapeau »
sont aussi acceptés). La date est au format AAAA-MM-JJ (avec ou sans heure) ou JJ/MM/AAAA.

Règle de décompte (celle de METHODOLOGIE.md) : un article est compté pour un candidat si son nom figure dans le
titre ou le chapô, une fois les homonymes retirés ; un article qui en cite plusieurs compte pour chacun. Un article
dont le nom n'apparaît que dans le chapô est marqué « (chapô) ». Les articles sans date lisible ne sont pas
comptés : ils sont listés pour vérification à la main.

Sortie : le tableau des décomptes, et pour chaque candidat la section Markdown à ajouter à son dossier
(dossiers-candidats/<nom>/README.md). Avec --ecrire, la section est ajoutée au dossier, sauf si le dossier a déjà
une section pour ce média. Ensuite : python3 -m pipeline.radio_france pour recalculer les décomptes publiés.

Usage : python3 outils/compter_articles.py articles_extraits.json [--debut 2026-07-01] [--fin 2026-11-01]
        [--source "https://…"] [--csv dossier] [--ecrire]
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.model import canonical_outlet  # noqa: E402
from pipeline.radio_france import DOSSIERS  # noqa: E402

DEBUT, FIN = "2026-07-01", "2026-11-01"

# Mêmes candidats que pipeline/radio_france.py ; homonymes repris de METHODOLOGIE.md.
CANDIDATS = {
    "lepen": {"nom": "Marine Le Pen", "motifs": [r"\bLe Pen\b"],
              "exclure": [r"\bJean-Marie Le Pen\b", r"\bMarie-Caroline Le Pen\b", r"\bMarion Maréchal-Le Pen\b"]},
    "melenchon": {"nom": "Jean-Luc Mélenchon", "motifs": [r"\bM[ée]lenchon\b"], "exclure": []},
    "philippe": {"nom": "Édouard Philippe", "motifs": [r"\b[ÉE]douard Philippe\b"], "exclure": []},
    "glucksmann": {"nom": "Raphaël Glucksmann", "motifs": [r"\bGlucksmann\b"], "exclure": [r"\bAndr[ée] Glucksmann\b"]},
    "attal": {"nom": "Gabriel Attal", "motifs": [r"\bAttal\b"], "exclure": [r"\bYvan Attal\b"]},
    "zemmour": {"nom": "Éric Zemmour", "motifs": [r"\bZemmour\b"], "exclure": [r"\bMicha[ëe]l Zemmour\b"]},
    "retailleau": {"nom": "Bruno Retailleau", "motifs": [r"\bRetailleau\b"], "exclure": []},
    "lisnard": {"nom": "David Lisnard", "motifs": [r"\bLisnard\b"], "exclure": []},
    "roussel": {"nom": "Fabien Roussel", "motifs": [r"\bRoussel\b"], "exclure": [r"\bJean-Fran[çc]ois Roussel\b"]},
    "arthaud": {"nom": "Nathalie Arthaud", "motifs": [r"\bArthaud\b"], "exclure": [r"\bFlorence Arthaud\b"]},
    "ruffin": {"nom": "François Ruffin", "motifs": [r"\bRuffin\b"],
               "exclure": [r"\bLaurence Ruffin\b", r"\bJean-Christophe Ruffin\b"]},
    "dupontaignan": {"nom": "Nicolas Dupont-Aignan", "motifs": [r"\bDupont-Aignan\b"], "exclure": []},
    "polony": {"nom": "Natacha Polony", "motifs": [r"\bPolony\b"], "exclure": []},
    "villepin": {"nom": "Dominique de Villepin", "motifs": [r"\bVillepin\b"], "exclure": []},
    "riner": {"nom": "Teddy Riner", "motifs": [r"\bRiner\b"], "exclure": []},
}
assert set(CANDIDATS) == set(DOSSIERS), "liste des candidats différente de pipeline/radio_france.py"


def normaliser(texte):
    """Espaces insécables, apostrophes et traits d'union typographiques ramenés à leur forme simple."""
    t = unicodedata.normalize("NFC", texte or "")
    t = t.replace("’", "'").replace("‑", "-").replace("‐", "-")
    return re.sub(r"\s+", " ", t).strip()


def lire_date(texte):
    """Date ISO (AAAA-MM-JJ) de l'article, ou None si elle est absente ou illisible."""
    t = (texte or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        a, mo, j = m.groups()
    else:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
        if not m:
            return None
        j, mo, a = m.groups()
    try:
        return date(int(a), int(mo), int(j)).isoformat()
    except ValueError:
        return None


def cite(texte, regles):
    for motif in regles["exclure"]:
        texte = re.sub(motif, "", texte, flags=re.IGNORECASE)
    return any(re.search(motif, texte) for motif in regles["motifs"])


def comptabiliser(articles, debut=DEBUT, fin=FIN):
    """Retourne (lignes retenues, articles sans date, médias inconnus)."""
    vus, retenus, sans_date, inconnus = set(), [], [], set()
    for art in articles:
        brut = art.get("media", "")
        media = canonical_outlet(brut)
        if media is None:
            inconnus.add(brut)
            continue
        titre = normaliser(art.get("titre") or art.get("title"))
        chapo = normaliser(art.get("chapo") or art.get("chapeau"))
        url = (art.get("url") or "").strip()
        jour = lire_date(art.get("date"))
        cle = (media, url) if url else (media, jour, titre.lower())
        if cle in vus:
            continue
        vus.add(cle)
        if jour is None:
            sans_date.append(art)
            continue
        if not (debut <= jour <= fin):
            continue
        for cand, regles in CANDIDATS.items():
            dans_titre = cite(titre, regles)
            if dans_titre or cite(chapo, regles):
                retenus.append({"candidat": cand, "media": media, "date": jour, "titre": titre,
                                "chapo_seul": not dans_titre, "url": url})
    return retenus, sans_date, inconnus


def tableau(retenus):
    medias = sorted({r["media"] for r in retenus})
    lignes = ["candidat".ljust(22) + "".join(m[:14].rjust(16) for m in medias) + "TOTAL".rjust(8)]
    for cand, regles in CANDIDATS.items():
        n = [sum(1 for r in retenus if r["candidat"] == cand and r["media"] == m) for m in medias]
        lignes.append(regles["nom"].ljust(22) + "".join(str(x).rjust(16) for x in n) + str(sum(n)).rjust(8))
    return "\n".join(lignes)


def section(media, lignes, source, debut, fin):
    """Section Markdown au format des dossiers (tableau à 2 colonnes, lu par pipeline/radio_france.py)."""
    def jj_mm(iso):
        return f"{iso[8:10]}/{iso[5:7]}"
    texte = [f"## {media}", "",
             f"Source : {source or '(à compléter)'}, relevé le {date.today().isoformat()}. Un article est compté "
             f"s'il est daté du {debut} au {fin} et que le nom du candidat figure dans son titre ou son chapô ; "
             "« (chapô) » quand le nom n'apparaît que dans le chapô.", "",
             "| Date | Titre |", "|---|---|"]
    for r in sorted(lignes, key=lambda r: r["date"], reverse=True):
        titre = r["titre"].replace("|", "/") + (" (chapô)" if r["chapo_seul"] else "")
        texte.append(f"| {jj_mm(r['date'])} | {titre} |")
    return "\n".join(texte) + "\n"


def a_deja_section(dossier_md, media):
    return any(re.match(rf"^#+\s*(\d+\.\s*)?{re.escape(media)}\b", l) for l in dossier_md.splitlines())


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("fichier", nargs="?", default="articles_extraits.json")
    p.add_argument("--debut", default=DEBUT)
    p.add_argument("--fin", default=FIN)
    p.add_argument("--source", default="", help="adresse de la recherche ou du plan de site, citée dans la section")
    p.add_argument("--csv", help="dossier où écrire synthese.csv et details.csv (avec titres : à garder en local)")
    p.add_argument("--ecrire", action="store_true", help="ajouter les sections aux dossiers des candidats")
    a = p.parse_args()

    articles = json.loads(Path(a.fichier).read_text(encoding="utf-8"))
    retenus, sans_date, inconnus = comptabiliser(articles, a.debut, a.fin)

    print(f"=== Décompte du {a.debut} au {a.fin} : {len(articles)} articles lus ===")
    print(tableau(retenus))
    if inconnus:
        print(f"\nMédias absents de config/medias.json, ignorés : {', '.join(sorted(inconnus))}")
    if sans_date:
        print(f"\n{len(sans_date)} articles sans date lisible, non comptés (à vérifier à la main) :")
        for art in sans_date:
            print(f"  - {art.get('media')} | {art.get('titre') or art.get('title')} | {art.get('url', '')}")

    if a.csv:
        out = Path(a.csv)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "details.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["candidat", "media", "date", "titre", "chapo_seul", "url"])
            w.writeheader()
            w.writerows(retenus)
        with open(out / "synthese.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["candidat", "media", "articles"])
            for cand in CANDIDATS:
                for m in sorted({r["media"] for r in retenus}):
                    w.writerow([cand, m, sum(1 for r in retenus if r["candidat"] == cand and r["media"] == m)])

    for media in sorted({r["media"] for r in retenus}):
        for cand in CANDIDATS:
            lignes = [r for r in retenus if r["candidat"] == cand and r["media"] == media]
            if not lignes:
                continue
            texte = section(media, lignes, a.source, a.debut, a.fin)
            chemin = Path("dossiers-candidats") / DOSSIERS[cand] / "README.md"
            if not a.ecrire:
                print(f"\n--- {chemin} ---\n{texte}")
                continue
            actuel = chemin.read_text(encoding="utf-8") if chemin.exists() else ""
            if a_deja_section(actuel, media):
                print(f"{chemin} : section « {media} » déjà présente, non modifiée")
                continue
            chemin.write_text(actuel.rstrip("\n") + "\n\n" + texte, encoding="utf-8")
            print(f"{chemin} : {len(lignes)} articles ajoutés ({media})")


if __name__ == "__main__":
    main()
