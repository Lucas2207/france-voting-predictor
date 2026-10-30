"""Ouvre dans le navigateur les pages des comptes listées dans le document de saisie, par lots.

Vous lisez les chiffres vous-même : le programme n'ouvre que les liens, il ne lit aucune page.
Usage : python3 outils/ouvrir_comptes.py [--lot 10] [--reseau x,instagram,tiktok,facebook]
"""
import argparse
import re
import sys
import webbrowser
import zipfile
import html
from pathlib import Path

DOC = Path("Followers Reseaux Candidats .docx")


def liens(reseaux):
    """Liens du document, par réseau (dans l'ordre du document, sans doublon)."""
    z = zipfile.ZipFile(DOC)
    xml = z.read("word/document.xml").decode("utf-8")
    rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
    cibles = {}
    for m in re.finditer(r"<Relationship [^>]*>", rels):
        tag = m.group(0)
        i, t = re.search(r'Id="([^"]+)"', tag), re.search(r'Target="([^"]+)"', tag)
        if i and t:
            cibles[i.group(1)] = html.unescape(t.group(1))
    trouves, vus, reseau = [], set(), None
    for ligne in re.findall(r"<w:tr[ >].*?</w:tr>", xml, flags=re.S):
        cellules = re.findall(r"<w:tc>.*?</w:tc>", ligne, flags=re.S)
        textes = [html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", c))).strip() for c in cellules]
        if len(textes) >= 2 and textes[1].startswith("Followers"):
            reseau = {"Followers X": "x", "Followers Tiktok": "tiktok", "Followers Instagram": "instagram",
                      "Followers Facebook": "facebook"}.get(textes[1])
            continue
        if textes and textes[0] == "Partis":
            reseau = None
            continue
        if reseau not in reseaux:
            continue
        for c in cellules:
            for rid in re.findall(r'r:id="([^"]+)"', c):
                url = cibles.get(rid)
                if url and url not in vus:
                    vus.add(url)
                    trouves.append((reseau, url))
    return trouves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lot", type=int, default=10, help="nombre de liens ouverts à chaque étape")
    ap.add_argument("--reseau", default="x,instagram,tiktok,facebook")
    args = ap.parse_args()
    if not DOC.exists():
        sys.exit(f"Document introuvable : {DOC}")
    urls = liens(set(args.reseau.split(",")))
    print(f"{len(urls)} comptes. Entrée pour ouvrir le lot suivant, « q » pour arrêter.")
    for debut in range(0, len(urls), args.lot):
        for reseau, url in urls[debut:debut + args.lot]:
            webbrowser.open_new_tab(url)
        rep = input(f"[{min(debut + args.lot, len(urls))}/{len(urls)}] Entrée = lot suivant, q = arrêter : ")
        if rep.strip().lower() == "q":
            break


if __name__ == "__main__":
    main()
