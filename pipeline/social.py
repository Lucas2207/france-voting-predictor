"""Abonnés sur les réseaux sociaux et audiences des interviews.

Les abonnés ne sont pas récupérés automatiquement : les API officielles exigent
l'accord du titulaire du compte, et le scraping enfreint les conditions des
plateformes. Chaque relevé est donc saisi à la main (data/followers.json), via
`python -m pipeline.social add`.

Un relevé reste valable CARRY_DAYS jours : entre deux relevés, on garde la
dernière valeur connue, sinon chaque relevé manqué ferait chuter la courbe.
"""
import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

PLATFORMS = ["tiktok", "instagram", "x", "facebook"]
CARRY_DAYS = 14
TOP_MEMBERS = 5


def _d(s):
    return date.fromisoformat(s)


def load_json(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def validate_entry(entry, known_ids):
    """Retourne la liste des erreurs de validation (vide si l'entrée est correcte)."""
    errors = []
    if entry.get("id") not in known_ids:
        errors.append(f"id inconnu : {entry.get('id')!r}")
    if entry.get("platform") not in PLATFORMS:
        errors.append(f"plateforme inconnue : {entry.get('platform')!r} (attendu : {', '.join(PLATFORMS)})")
    if not isinstance(entry.get("followers"), int) or entry["followers"] < 0:
        errors.append("followers doit être un entier positif")
    try:
        _d(entry.get("date", ""))
    except ValueError:
        errors.append("date invalide (format AAAA-MM-JJ)")
    if not str(entry.get("source", "")).startswith(("http://", "https://")):
        errors.append("source doit être une URL")
    return errors


def add_entry(entries, entry):
    """Ajoute ou remplace le relevé (personne, plateforme, date). Retourne la liste triée."""
    key = (entry["id"], entry["platform"], entry["date"])
    kept = [e for e in entries if (e["id"], e["platform"], e["date"]) != key]
    kept.append(entry)
    return sorted(kept, key=lambda e: (e["date"], e["id"], e["platform"]))


def latest_by_platform(entries, pid, on):
    """Dernier relevé de chaque plateforme valable à la date `on`."""
    out = {}
    for e in entries:
        if e["id"] != pid:
            continue
        age = (on - _d(e["date"])).days
        if age < 0 or age > CARRY_DAYS:
            continue
        if e["platform"] not in out or _d(e["date"]) > out[e["platform"]][0]:
            out[e["platform"]] = (_d(e["date"]), e["followers"])
    return {p: v for p, (_, v) in out.items()}


def total(entries, pid, on):
    values = latest_by_platform(entries, pid, on)
    return sum(values.values()) if values else None


def top_members(entries, members, on):
    """Les TOP_MEMBERS membres les plus suivis à la date `on` (sans relevé = exclu)."""
    scored = []
    for m in members:
        t = total(entries, m["id"], on)
        if t:
            scored.append((t, m))
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:TOP_MEMBERS]]


def person_series(entries, pid, dates):
    values = [total(entries, pid, _d(d)) for d in dates]
    first = next((v for v in values if v is not None), None)
    return {
        "id": pid,
        "followers": values,
        "change": [None if v is None or first is None else v - first for v in values],
        "latest_by_platform": latest_by_platform(entries, pid, _d(dates[-1])) if dates else {},
    }


def party_series(entries, party, dates, today):
    members = top_members(entries, party["members"], today)
    values = []
    for d in dates:
        day = _d(d)
        parts = [total(entries, m["id"], day) for m in members]
        parts = [p for p in parts if p is not None]
        values.append(sum(parts) if parts else None)
    first = next((v for v in values if v is not None), None)
    return {
        "id": party["id"],
        "members": [m["id"] for m in members],
        "followers": values,
        "change": [None if v is None or first is None else v - first for v in values],
    }


def platform_series(entries, pid, platform, dates):
    """Abonnés d'une personne sur un seul réseau, relevé par relevé (valeur valable CARRY_DAYS jours)."""
    values = [latest_by_platform(entries, pid, _d(d)).get(platform) for d in dates]
    first = next((v for v in values if v is not None), None)
    return {
        "id": pid,
        "followers": values,
        "change": [None if v is None or first is None else v - first for v in values],
    }


def build_followers(entries, candidates, parties, influencers, today):
    """Séries d'abonnés pour les candidats, les partis et les personnalités influentes.

    `by_platform` donne, pour chaque réseau, les séries des candidats et des personnalités.
    """
    dates = sorted({e["date"] for e in entries})
    if not dates:
        return {"dates": [], "candidates": [], "parties": [], "influencers": [], "by_platform": {}, "platforms": PLATFORMS}
    return {
        "dates": dates,
        "platforms": PLATFORMS,
        "candidates": [person_series(entries, c["id"], dates) for c in candidates],
        "parties": [party_series(entries, p, dates, today) for p in parties],
        "influencers": [person_series(entries, i["id"], dates) for i in influencers],
        "by_platform": {
            platform: {
                "candidates": [platform_series(entries, c["id"], platform, dates) for c in candidates],
                "influencers": [platform_series(entries, i["id"], platform, dates) for i in influencers],
            }
            for platform in PLATFORMS
        },
    }


def interview_key(i):
    return (i["date"], i["candidate"], i["channel"])


def merge_interviews(existing, new):
    """Ajoute les nouvelles interviews sans doublon (même jour, candidat, chaîne)."""
    seen = {interview_key(i) for i in existing}
    for i in new:
        if interview_key(i) not in seen:
            existing.append(i)
            seen.add(interview_key(i))
    return sorted(existing, key=lambda i: i["date"])


def interview_summary(interviews, candidate_ids):
    """Audience moyenne par candidat (sur les interviews où un chiffre est publié)."""
    out = {}
    for cid in candidate_ids:
        mine = [i for i in interviews if i["candidate"] == cid]
        viewers = [i["audience_viewers"] for i in mine if i.get("audience_viewers")]
        shares = [i["audience_share"] for i in mine if i.get("audience_share") is not None]
        out[cid] = {
            "count": len(mine),
            "avg_viewers": round(sum(viewers) / len(viewers)) if viewers else None,
            "avg_share": round(sum(shares) / len(shares), 1) if shares else None,
        }
    return out


# --- Saisie manuelle des relevés -------------------------------------------

def _cli_add(args):
    cands = load_json("config/candidates.json", {"candidates": []})["candidates"]
    parties = load_json("config/parties.json", {"parties": []})["parties"]
    known = {c["id"] for c in cands} | {m["id"] for p in parties for m in p["members"]}
    entry = {
        "date": args.date, "id": args.id, "platform": args.platform,
        "followers": args.followers, "source": args.source,
    }
    errors = validate_entry(entry, known)
    if errors:
        print("Relevé refusé :\n  - " + "\n  - ".join(errors), file=sys.stderr)
        return 1
    path = Path("data/followers.json")
    doc = load_json(path, {"entries": []})
    doc["entries"] = add_entry(doc.get("entries", []), entry)
    save_json(path, doc)
    print(f"✅ {args.id} / {args.platform} / {args.date} : {args.followers:,} abonnés enregistrés".replace(",", " "))
    return 0


def known_people():
    """Identifiants et noms de toutes les personnes suivies (candidats et membres de partis), sans doublon."""
    cands = load_json("config/candidates.json", {"candidates": []})["candidates"]
    parties = load_json("config/parties.json", {"parties": []})["parties"]
    people = {c["id"]: c["name"] for c in cands}
    for p in parties:
        for m in p["members"]:
            people.setdefault(m["id"], m["name"])
    return people


PROFILE_URLS = {"x": "https://x.com/{}", "instagram": "https://www.instagram.com/{}/",
                "tiktok": "https://www.tiktok.com/@{}", "facebook": "https://www.facebook.com/{}"}


def account_url(pid, platform):
    """URL du compte d'une personne sur X ou Instagram (config/social_accounts.json), ou chaîne vide."""
    handle = load_json("config/social_accounts.json", {}).get(platform, {}).get(pid, "")
    return PROFILE_URLS[platform].format(handle) if handle and platform in PROFILE_URLS else ""


def x_url(pid):
    return account_url(pid, "x")


def _cli_template(args):
    """Écrit un fichier CSV à remplir : une ligne par personne et par plateforme.

    Pour chaque réseau dont le compte est connu, l'URL est pré-remplie.
    """
    people = known_people()
    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "nom", "plateforme", "abonnes", "source"])
        for pid, name in people.items():
            for platform in PLATFORMS:
                source = account_url(pid, platform)
                w.writerow([pid, name, platform, "", source])
    print(f"✅ Modèle écrit : {args.output} ({len(people)} personnes). Remplissez « abonnes » et « source », puis importez-le.")
    return 0


def _cli_import(args):
    """Importe un CSV rempli. Les lignes sans abonnés sont ignorées ; les autres sont validées une à une."""
    known = set(known_people())
    path = Path("data/followers.json")
    doc = load_json(path, {"entries": []})
    entries = doc.get("entries", [])
    accepted, skipped, errors = 0, 0, []
    with open(args.file, encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f, delimiter=";"), start=2):
            raw = (row.get("abonnes") or "").strip()
            if not raw:
                skipped += 1
                continue
            try:
                followers = _parse_followers(raw)
            except argparse.ArgumentTypeError as exc:
                errors.append(f"ligne {n} : {exc}")
                continue
            entry = {"date": args.date, "id": row.get("id", "").strip(), "platform": row.get("plateforme", "").strip(),
                     "followers": followers, "source": (row.get("source") or "").strip()}
            problems = validate_entry(entry, known)
            if problems:
                errors.append(f"ligne {n} : " + "; ".join(problems))
                continue
            entries = add_entry(entries, entry)
            accepted += 1
    if errors:
        print("Lignes refusées :\n  - " + "\n  - ".join(errors), file=sys.stderr)
    if accepted:
        doc["entries"] = entries
        save_json(path, doc)
    print(f"✅ {accepted} relevé(s) importé(s) au {args.date}, {skipped} ligne(s) vide(s) ignorée(s), {len(errors)} refusée(s).")
    return 1 if errors else 0


def _parse_followers(text):
    """« 1,2 M », « 850 k », « 1 234 567 » -> entier."""
    t = text.strip().lower().replace(" ", " ").replace(" ", "")
    m = re.fullmatch(r"([\d.,]+)([mk]?)", t)
    if not m:
        raise argparse.ArgumentTypeError(f"nombre illisible : {text!r}")
    num = float(m.group(1).replace(",", "."))
    mult = {"m": 1_000_000, "k": 1_000, "": 1}[m.group(2)]
    return round(num * mult)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m pipeline.social")
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="ajouter un relevé d'abonnés")
    add.add_argument("id", help="identifiant (candidates.json ou parties.json)")
    add.add_argument("platform", choices=PLATFORMS)
    add.add_argument("followers", type=_parse_followers, help="ex. 1,2M, 850k ou 1234567")
    add.add_argument("source", help="URL du compte consulté")
    add.add_argument("--date", default=date.today().isoformat(), help="AAAA-MM-JJ (défaut : aujourd'hui)")
    tpl = sub.add_parser("template", help="créer le CSV hebdomadaire à remplir")
    tpl.add_argument("--output", default="data/releves.csv")
    imp = sub.add_parser("import", help="importer le CSV hebdomadaire rempli")
    imp.add_argument("file")
    imp.add_argument("--date", default=date.today().isoformat(), help="date des relevés (défaut : aujourd'hui)")
    args = ap.parse_args(argv)
    return {"add": _cli_add, "template": _cli_template, "import": _cli_import}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
