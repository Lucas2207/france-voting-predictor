import json
import random
from datetime import datetime, timedelta

CANDIDATES = {
    'Marine Le Pen (RN)': {'base_v': 25.0, 'followers': 14.50, 'color': '#0F172A', 'party': 'RN', 'emoji': '🇫🇷🦅', 'team': 'Bardella, Maréchal, Chenu'},
    'Jean-Luc Mélenchon (LFI)': {'base_v': 13.5, 'followers': 11.20, 'color': '#E11D48', 'party': 'LFI', 'emoji': '🔥✊', 'team': 'Guetté, Bompard, Hassan, Caron'},
    'Édouard Philippe (Horizons)': {'base_v': 14.5, 'followers': 1.80, 'color': '#2563EB', 'party': 'Horizons', 'emoji': '⚓é', 'team': 'Le Gendre, Naegelen'},
    'Gabriel Attal (Renaissance)': {'base_v': 12.0, 'followers': 6.50, 'color': '#0284C7', 'party': 'Renaissance', 'emoji': '🏛️🔵', 'team': 'Borne, Darmanin, Séjourné'},
    'Raphaël Glucksmann (PP/PS)': {'base_v': 11.0, 'followers': 2.10, 'color': '#EC4899', 'party': 'PP/PS', 'emoji': '🌹🇪🇺', 'team': 'Faure, Delga'},
    'François Hollande (PS)': {'base_v': 9.5, 'followers': 4.30, 'color': '#F43F5E', 'party': 'PS', 'emoji': '🌹📖', 'team': 'Vallaud, Mayer-Rossignol'},
    'Bruno Retailleau (LR)': {'base_v': 1.5, 'followers': 2.40, 'color': '#1E3A8A', 'party': 'LR', 'emoji': '🌳⚖️', 'team': 'Wauquiez, Pécresse'},
    'Dominique de Villepin (DVD)': {'base_v': 6.0, 'followers': 0.85, 'color': '#475569', 'party': 'DVD', 'emoji': '📜🏛️', 'team': 'Gaullistes indépendants'},
    'Éric Zemmour (Reconquête)': {'base_v': 5.5, 'followers': 6.20, 'color': '#7C3AED', 'party': 'Reconquête', 'emoji': '⚔️🛡️', 'team': 'Knafo, Meunier'},
    'David Lisnard (Nouvelle Énergie)': {'base_v': 4.5, 'followers': 0.65, 'color': '#0D9488', 'party': 'Nouvelle Énergie', 'emoji': '⚡ maire', 'team': 'Collectifs d’élus locaux'}
}

BASE_EVENTS = {
    "2026-10-01": {
        "title": "Lancement du suivi quotidien",
        "desc": "Ouverture officielle de la plateforme de modélisation des intentions de vote et de l'impact média/social."
    },
    "2026-10-17": {
        "title": "Manifestations et grèves nationales",
        "desc": "• Quoi/Où : Mobilisation interprofessionnelle majeure dans 120 villes.\n• Qui : 350 000 manifestants (syndicats) / 180 000 (Intérieur).\n• Revendications : Pouvoir d'achat, salaires et services publics.\n• Réponse : 80 000 forces de l'ordre déployées, 45 interpellations."
    },
    "2026-10-23": {
        "title": "Attentat de Trappes et La Verrière",
        "desc": "• Quoi/Où : Attaque terroriste islamiste déjouée in extremis / perpétrée en zone urbaine sensible.\n• Bilan : 2 blessés graves, 1 suspect neutralisé par le RAID.\n• Conséquence : Débat immédiat sur la sécurité, l'immigration et l'autorité."
    },
    "2026-10-25": {
        "title": "Annonce de mesures de sécurité & couvre-feu",
        "desc": "• Quoi/Où : Conseil de défense exceptionnel à l'Élysée.\n• Mesures : Instauration d'un couvre-feu ciblé, renforcement du plan Vigipirate au niveau Urgence Attentat.\n• Réaction politique : Débats intenses au Parlement."
    }
}

def generate_history():
    history = []
    start_date = datetime(2026, 10, 1)
    today = datetime.now()
    if today < start_date:
        today = start_date + timedelta(days=26)
    total_days = (today - start_date).days + 1

    random.seed(2026)
    sim_data = {c: {'v': data['base_v'], 'f': data['followers']} for c, data in CANDIDATES.items()}
    events_dynamic = BASE_EVENTS.copy()

    for d in range(total_days):
        date_dt = start_date + timedelta(days=d)
        date_str = date_dt.strftime("%Y-%m-%d")

        # Génération automatique d'un micro-événement si la date avance et n'existe pas
        if date_str not in events_dynamic and d > 25:
            events_dynamic[date_str] = {
                "title": f"Point d'actualité politique et sociale ({date_str})",
                "desc": f"• Débat télévisé et interventions des porte-paroles.\n• Impact direct sur les communautés numériques suite aux polémiques de la semaine.\n• Évolution mesurée des dynamiques d'adhésion."
            }

        daily_votes = {}
        daily_followers = {}

        for cand in CANDIDATES:
            v_noise = round(random.uniform(-0.3, 0.3), 2)
            # Accentuation de la croissance des followers pour éviter des lignes plates
            f_noise = round(random.uniform(0.015, 0.045), 3)

            if date_str in ["2026-10-17", "2026-10-18"]:
                if "Mélenchon" in cand or "Glucksmann" in cand: v_noise += 1.0
            elif date_str in ["2026-10-23", "2026-10-24"]:
                if "Le Pen" in cand or "Retailleau" in cand: v_noise += 1.4

            sim_data[cand]['v'] = round(max(1.0, sim_data[cand]['v'] + v_noise), 1)
            sim_data[cand]['f'] = round(max(0.1, sim_data[cand]['f'] + f_noise), 2)

            daily_votes[cand] = sim_data[cand]['v']
            daily_followers[cand] = sim_data[cand]['f']

        history.append({
            "date": date_str,
            "voting_intentions": daily_votes,
            "social_media_followers_m": daily_followers
        })

    return history, events_dynamic

def run():
    history, events = generate_history()
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "start_date": "2026-10-01",
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "events": events,
        "history": history
    }
    with open('live_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("✅ Données dynamiques et événements mis à jour avec succès.")

if __name__ == "__main__":
    run()
