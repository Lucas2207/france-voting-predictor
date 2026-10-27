"""Analyse des articles par Claude : tonalité envers chaque candidat et détection d'événements.

Chaque article n'est analysé qu'une fois (le résultat est stocké dans le fichier du
jour), donc relancer le pipeline ne refacture pas les articles déjà traités.
"""
import json
import os
import sys

import anthropic

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
- « candidates » : identifiants des personnalités directement concernées ou mises en avant par l'événement (peut être vide)."""


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
                },
                "required": ["title", "description", "category", "article_idx", "candidates"],
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


def _call(client, system, user, schema, max_tokens):
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


def detect_events(day, articles, candidates, client=None):
    """Événements marquants du jour, appuyés sur au moins deux médias.

    Retourne None si l'appel a échoué (la journée sera retentée au prochain passage).
    """
    if len(articles) < 5:
        return []
    client = client or _client()
    ids = {c["id"] for c in candidates}
    roster = ", ".join(f"{c['id']} ({c['name']})" for c in candidates)
    lines = [f"Date : {day}\nIdentifiants des personnalités : {roster}\n\nTitres du jour :"]
    for i, a in enumerate(articles):
        lines.append(f"[idx {i}] {a['outlet']} — {a['title']}")
    try:
        data, _ = _call(client, EVENTS_SYSTEM, "\n".join(lines), EVENTS_SCHEMA, max_tokens=8000)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise
    except (AnalysisError, anthropic.APIError, json.JSONDecodeError) as exc:
        print(f"⚠️  détection d'événements ignorée pour {day} : {exc}", file=sys.stderr)
        return None
    events = []
    for ev in data["events"]:
        sources = [articles[i] for i in ev["article_idx"] if 0 <= i < len(articles)]
        if len({s["outlet"] for s in sources}) < 2:
            continue  # garde-fou : on exige deux médias distincts
        events.append({
            "date": day,
            "title": ev["title"],
            "description": ev["description"],
            "category": ev["category"],
            "candidates": [c for c in ev["candidates"] if c in ids],
            "origin": "presse",
            "sources": [{"outlet": s["outlet"], "title": s["title"], "url": s["url"]} for s in sources[:6]],
        })
    return events
