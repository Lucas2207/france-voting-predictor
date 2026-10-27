"""Analyse des articles par Claude : tonalité envers chaque candidat et détection d'événements.

Chaque article n'est analysé qu'une fois (le résultat est stocké dans le fichier du
jour), donc relancer le pipeline ne refacture pas les articles déjà traités.
"""
import hashlib
import json
import os
import re
import sys
from datetime import date

import anthropic

from .news import normalize

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "low")
BATCH_SIZE = 25
FALLBACK_BETA = "server-side-fallback-2026-07-01"

FRAMES = ["programme", "sondage_dynamique", "polemique", "justice_affaires", "securite", "economie_social",
          "international", "strategie_alliances", "portrait", "autre"]

SCORING_SYSTEM = """Tu es un analyste des médias français. Pour chaque article (titre + chapô issus d'un flux RSS), tu évalues comment l'article traite chacune des personnalités politiques listées qu'il concerne réellement.

Règles :
- N'inclus une personnalité que si l'article parle d'elle (pas un simple homonyme : « la Hollande » = les Pays-Bas ; Jean-Marie ou Marion Maréchal ne sont pas Marine Le Pen).
- « tone » mesure l'image que l'article donne de la personnalité, pas ton avis ni si la nouvelle est bonne pour la France :
  -2 très défavorable (scandale, échec, attaque relayée sans contrepoint), -1 plutôt défavorable, 0 neutre ou factuel, +1 plutôt favorable, +2 très favorable (succès, ralliement, dynamique mise en avant).
- Un compte rendu factuel d'une déclaration vaut 0, sauf si le cadrage (titre, verbes, adjectifs) est clairement orienté.
- « frame » est l'angle principal de l'article pour cette personnalité.
- Si l'article ne concerne aucune personnalité de la liste, renvoie une liste vide pour cet article.
- Renvoie exactement un résultat par article, avec le même « idx »."""

EVENTS_SYSTEM = """Tu es un journaliste politique chargé de repérer les événements marquants d'une journée en France susceptibles d'influencer la campagne présidentielle de 2027 (attentat, mouvement social, décision de justice, déclaration de candidature, débat, crise gouvernementale, vote majeur au Parlement, résultat d'élection partielle, etc.).

Règles :
- Ne retiens que des faits couverts par au moins deux médias différents dans la liste fournie. Cite les « idx » des articles qui les rapportent.
- 0 à 4 événements maximum ; renvoie une liste vide si la journée n'a rien de marquant. Ne crée jamais d'événement générique (« point d'actualité », « débats télévisés »).
- Le titre et la description doivent être strictement factuels et ne contenir que ce que disent les articles fournis. N'invente aucun chiffre ni aucun détail.
- « candidates » : identifiants des personnalités directement concernées ou mises en avant par l'événement (peut être vide).
- Une liste d'événements déjà signalés peut être fournie. Si un événement du jour est la suite, la répétition ou une nouvelle précision d'un fait déjà listé, renvoie l'id de ce fait dans « existing_id » et ne le recrée pas. « existing_id » vaut null pour un fait nouveau."""


def _scoring_schema(candidate_ids):
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "idx": {"type": "integer"},
                        "candidates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "enum": candidate_ids},
                                    "tone": {"type": "integer", "enum": [-2, -1, 0, 1, 2]},
                                    "frame": {"type": "string", "enum": FRAMES},
                                },
                                "required": ["id", "tone", "frame"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["idx", "candidates"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }


EVENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {"type": "string", "enum": ["securite", "social", "justice", "institutions",
                                                             "campagne", "economie", "international", "autre"]},
                    "article_idx": {"type": "array", "items": {"type": "integer"}},
                    "candidates": {"type": "array", "items": {"type": "string"}},
                    "existing_id": {"type": ["string", "null"]},
                },
                "required": ["title", "description", "category", "article_idx", "candidates", "existing_id"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}


class AnalysisError(RuntimeError):
    pass


def _client():
    return anthropic.Anthropic(max_retries=4)


class BudgetExhausted(RuntimeError):
    """Plafond d'appels à Claude atteint pour cette exécution ; la suite sera traitée au prochain passage."""


_budget = {"left": None}


def set_budget(calls):
    _budget["left"] = calls


def _spend():
    if _budget["left"] is None:
        return
    if _budget["left"] <= 0:
        raise BudgetExhausted()
    _budget["left"] -= 1


def _call(client, system, user, schema, max_tokens):
    _spend()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if response.stop_reason == "refusal":
        raise AnalysisError(f"refus du modèle (request {response._request_id})")
    if response.stop_reason == "max_tokens":
        raise AnalysisError(f"réponse tronquée (request {response._request_id})")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise AnalysisError(f"pas de texte dans la réponse (request {response._request_id})")
    return json.loads(text), response.usage


def score_articles(articles, candidates, client=None):
    """Ajoute article['analysis'] = [{id, tone, frame}] aux articles pré-filtrés non encore analysés.

    Retourne le nombre d'articles analysés.
    """
    todo = [a for a in articles if a.get("mentions") and "analysis" not in a]
    if not todo:
        return 0
    client = client or _client()
    ids = [c["id"] for c in candidates]
    roster = "\n".join(f"- {c['id']} : {c['name']} ({c['party']})" for c in candidates)
    schema = _scoring_schema(ids)
    done = 0
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        lines = [f"Personnalités suivies :\n{roster}\n\nArticles :"]
        for i, a in enumerate(batch):
            lines.append(f"\n[idx {i}] {a['outlet']} — {a['title']}\n{a['summary']}")
        try:
            data, usage = _call(client, SCORING_SYSTEM, "\n".join(lines), schema, max_tokens=16000)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise  # inutile d'essayer les autres lots : la clé est refusée
        except (AnalysisError, anthropic.APIError, json.JSONDecodeError) as exc:
            print(f"⚠️  lot ignoré ({len(batch)} articles) : {exc}", file=sys.stderr)
            continue
        by_idx = {r["idx"]: r["candidates"] for r in data["results"]}
        for i, a in enumerate(batch):
            if i in by_idx:
                # dédoublonne si le modèle cite deux fois la même personne
                seen, result = set(), []
                for c in by_idx[i]:
                    if c["id"] not in seen:
                        seen.add(c["id"]); result.append(c)
                a["analysis"] = result
                done += 1
        print(f"   lot {start // BATCH_SIZE + 1} : {len(batch)} articles, "
              f"{usage.input_tokens} tokens entrée / {usage.output_tokens} sortie")
    return done


STOPWORDS = {"pour", "dans", "avec", "sans", "entre", "contre", "après", "avant", "sont", "était", "dont",
             "leur", "leurs", "cette", "ces", "aux", "des", "les", "une", "qui", "que", "sur", "par", "est",
             "selon", "vers", "chez", "comme", "plus", "très", "tout", "tous", "fait", "faire"}
REPEAT_WINDOW = 7  # jours : au-delà, deux titres proches sont deux événements distincts


def _title_tokens(title):
    return {w for w in re.findall(r"[a-z0-9]+", normalize(title)) if len(w) >= 4 and w not in STOPWORDS}


def is_repeat(title_a, title_b):
    """Titres identiques ou presque (Jaccard >= 0.5 sur les mots significatifs)."""
    if normalize(title_a) == normalize(title_b):
        return True
    a, b = _title_tokens(title_a), _title_tokens(title_b)
    return bool(a and b) and len(a & b) / len(a | b) >= 0.5


def event_id(day, title):
    return hashlib.sha1(f"{day}|{normalize(title)}".encode()).hexdigest()[:12]


def unique_sources(sources):
    """Une seule source par média : le premier article rencontré."""
    seen, out = set(), []
    for s in sources:
        if s["outlet"] in seen:
            continue
        seen.add(s["outlet"])
        out.append(s)
    return out


def apply_events(store, found):
    """Ajoute les événements trouvés à `store`, ou enrichit ceux déjà présents.

    Un événement est repris s'il porte le même id, s'il est signalé comme existant par le
    modèle, ou s'il a un titre quasi identique à un événement de la semaine précédente.
    """
    for ev in found:
        target = next((e for e in store if e["id"] == ev["id"]), None)
        if target is None and not ev.get("existing"):
            target = next((e for e in store
                           if abs((date.fromisoformat(e["date"]) - date.fromisoformat(ev["date"])).days) <= REPEAT_WINDOW
                           and is_repeat(e["title"], ev["title"])), None)
        if target is not None:
            target["sources"] = unique_sources(target["sources"] + ev["sources"])
        elif not ev.get("existing"):
            store.append({k: v for k, v in ev.items() if k != "existing"})
    return store


def dedupe_events(store):
    """Fusionne les doublons d'un historique existant ; le premier signalement garde sa date."""
    result = []
    for e in sorted(store, key=lambda e: e["date"]):
        apply_events(result, [dict(e, existing=False)])
    return result


def detect_events(day, articles, candidates, client=None, known=()):
    """Événements de la journée : nouveaux faits (appuyés sur au moins deux médias) et mises à jour
    de faits déjà connus (`known`: liste de {id, date, title}). Retourne None si l'appel échoue."""
    if len(articles) < 5:
        return []
    client = client or _client()
    ids = {c["id"] for c in candidates}
    known_ids = {k["id"] for k in known}
    roster = ", ".join(f"{c['id']} ({c['name']})" for c in candidates)
    lines = [f"Date : {day}\nIdentifiants des personnalités : {roster}\n"]
    if known:
        lines.append("Événements déjà signalés (id | date | titre) :")
        lines += [f"- {k['id']} | {k['date']} | {k['title']}" for k in known]
        lines.append("")
    lines.append("Titres du jour :")
    for i, a in enumerate(articles):
        lines.append(f"[idx {i}] {a['outlet']} — {a['title']}")
    try:
        data, _ = _call(client, EVENTS_SYSTEM, "\n".join(lines), EVENTS_SCHEMA, max_tokens=8000)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise
    except (AnalysisError, anthropic.APIError, json.JSONDecodeError) as exc:
        print(f"⚠️  détection d'événements ignorée pour {day} : {exc}", file=sys.stderr)
        return None
    out = []
    for ev in data["events"]:
        sources = unique_sources([{"outlet": articles[i]["outlet"], "title": articles[i]["title"], "url": articles[i]["url"]}
                                  for i in ev["article_idx"] if 0 <= i < len(articles)])
        if ev.get("existing_id") in known_ids:
            if sources:
                out.append({"id": ev["existing_id"], "existing": True, "sources": sources})
            continue
        if len({s["outlet"] for s in sources}) < 2:
            continue  # garde-fou : un fait nouveau doit venir d'au moins deux médias
        out.append({
            "id": event_id(day, ev["title"]),
            "existing": False,
            "date": day,
            "title": ev["title"],
            "description": ev["description"],
            "category": ev["category"],
            "candidates": [c for c in ev["candidates"] if c in ids],
            "origin": "presse",
            "sources": sources,
        })
    return out

INTERVIEW_SYSTEM = """Tu repères les interviews de personnalités politiques à la radio, à la télévision ou en ligne, à partir des titres et chapôs d'articles de presse, et tu relèves l'audience annoncée.

Règles :
- Ne retiens une interview que si l'article rapporte une mesure d'audience explicite : nombre de téléspectateurs ou d'auditeurs (audience_viewers) et/ou part d'audience en % (audience_share). Sans chiffre, n'inclus pas l'interview.
- Recopie les chiffres tels qu'ils figurent dans l'article. N'invente rien : si un seul des deux chiffres est donné, mets l'autre à null.
- « candidate » : identifiant de la personnalité interviewée, parmi la liste fournie. Ignore les interviews de personnes absentes de la liste.
- « channel » : la chaîne ou la radio (ex. « France Inter »). « show » : l'émission, ou null.
- Renvoie exactement les interviews trouvées, avec l'« article_idx » de l'article qui donne le chiffre."""

INTERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "interviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "string"},
                    "channel": {"type": "string"},
                    "show": {"type": ["string", "null"]},
                    "audience_viewers": {"type": ["integer", "null"]},
                    "audience_share": {"type": ["number", "null"]},
                    "article_idx": {"type": "integer"},
                },
                "required": ["candidate", "channel", "show", "audience_viewers", "audience_share", "article_idx"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["interviews"],
    "additionalProperties": False,
}


def extract_interviews(day, articles, candidates, client=None):
    """Interviews de la journée avec audience publiée. None si l'appel échoue (nouvelle tentative plus tard)."""
    todo = [a for a in articles if a.get("mentions")]
    if not todo:
        return []
    client = client or _client()
    ids = {c["id"] for c in candidates}
    roster = ", ".join(f"{c['id']} ({c['name']})" for c in candidates)
    lines = [f"Date : {day}\nPersonnalités : {roster}\n\nArticles :"]
    for i, a in enumerate(todo):
        lines.append(f"[idx {i}] {a['outlet']} — {a['title']}\n{a['summary']}")
    try:
        data, _ = _call(client, INTERVIEW_SYSTEM, "\n".join(lines), INTERVIEW_SCHEMA, max_tokens=4000)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise
    except (AnalysisError, anthropic.APIError, json.JSONDecodeError) as exc:
        print(f"⚠️  interviews ignorées pour {day} : {exc}", file=sys.stderr)
        return None
    out = []
    for item in data["interviews"]:
        if item["candidate"] not in ids:
            continue
        if item["audience_viewers"] is None and item["audience_share"] is None:
            continue  # garde-fou : pas de chiffre, pas d'interview
        if not (0 <= item["article_idx"] < len(todo)):
            continue
        src = todo[item["article_idx"]]
        out.append({
            "date": day,
            "candidate": item["candidate"],
            "channel": item["channel"],
            "show": item["show"],
            "audience_viewers": item["audience_viewers"],
            "audience_share": item["audience_share"],
            "source": {"outlet": src["outlet"], "title": src["title"], "url": src["url"]},
        })
    return out
