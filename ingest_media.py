import feedparser
import json
import re

# Comprehensive Directory of Major French Media Outlets
MEDIA_SOURCES = {
    # --- NATIONAL PRESS & DAILIES ---
    'lemonde': {'url': 'https://www.lemonde.fr/rss/une.xml', 'weight': 1.0},
    'lefigaro': {'url': 'https://www.lefigaro.fr/rss/figaro_actualites.xml', 'weight': 1.0},
    'liberation': {'url': 'https://www.liberation.fr/arc/outboundfeeds/rss-all/collection/accueil-du-site/', 'weight': 0.9},
    'humanite': {'url': 'https://www.humanite.fr/feed', 'weight': 0.7},
    'leparisien': {'url': 'https://www.leparisien.fr/arc/outboundfeeds/rss/all.xml', 'weight': 1.0},
    'lesechos': {'url': 'https://www.lesechos.fr/rss/rss_une.xml', 'weight': 0.9},
    'lacroix': {'url': 'https://www.la-croix.com/feeds/rss/site.xml', 'weight': 0.7},

    # --- WEEKLY MAGAZINES ---
    'marianne': {'url': 'https://www.marianne.net/rss.xml', 'weight': 0.8},
    'lepoint': {'url': 'https://www.lepoint.fr/24h-infos/rss.xml', 'weight': 0.8},
    'lexpress': {'url': 'https://www.lexpress.fr/rss/une.xml', 'weight': 0.8},
    'nouvelobs': {'url': 'https://www.nouvelobs.com/a-la-une/rss.xml', 'weight': 0.8},

    # --- TV BROADCASTERS & 24/7 NEWS ---
    'tf1': {'url': 'https://www.tf1info.fr/feeds/rss-une.xml', 'weight': 1.2},
    'francetv': {'url': 'https://www.francetvinfo.fr/titres.rss', 'weight': 1.2},
    'bfmtv': {'url': 'https://www.bfmtv.com/rss/info/flux-rss/flux-toutes-les-actualites/', 'weight': 1.2},
    'cnews': {'url': 'https://www.cnews.fr/rss.xml', 'weight': 1.1},
    'euronews': {'url': 'https://fr.euronews.com/rss?format=xml', 'weight': 0.8},

    # --- RADIO NETWORKS ---
    'franceinter': {'url': 'https://www.radiofrance.fr/franceinter/rss', 'weight': 1.1},
    'franceinfo_radio': {'url': 'https://www.francetvinfo.fr/franceinfo.rss', 'weight': 1.1},

    # --- MAJOR REGIONAL PRESS (PQR) ---
    'laprovence': {'url': 'https://www.laprovence.com/rss.xml', 'weight': 0.8},
    'ouestfrance': {'url': 'https://www.ouest-france.fr/rss/une', 'weight': 1.0},
    'sudouest': {'url': 'https://www.sudouest.fr/essentiel/rss.xml', 'weight': 0.9},
    'ladepeche': {'url': 'https://www.ladepeche.fr/rss.xml', 'weight': 0.8},
    'nicematin': {'url': 'https://www.nicematin.com/rss', 'weight': 0.7}
}

# Lexicons covering all major societal themes
LEXICONS = {
    'sec_imm': ['sécurité', 'police', 'violence', 'délinquance', 'ordre', 'immigration', 'frontière', 'expulsion', 'justice', 'agression', 'refus d\'obtempérer'],
    'econ_tax': ['économie', 'impôt', 'taxe', 'dette', 'déficit', 'entreprises', 'inflation', 'croissance', 'budget', 'fiscalité'],
    'purch_inc': ['pouvoir d\'achat', 'salaire', 'prix', 'carburant', 'électricité', 'logement', 'inflation', 'facture', 'panier de la ménagère'],
    'health_care': ['santé', 'hôpital', 'urgences', 'médecin', 'désert médical', 'sécurité sociale', 'médicaments', 'soins'],
    'pen_soc': ['retraite', 'pension', 'chômage', 'syndicat', 'grève', 'code du travail', 'cotisations', 'rsa'],
    'cohes_dem': ['école', 'éducation', 'laïcité', 'services publics', 'inégalités', 'banlieue', 'discrimination', 'émancipation']
}

def analyze_all_media():
    theme_scores = {k: 0.0 for k in LEXICONS.keys()}
    total_articles_scraped = 0

    print("🚀 Ingesting live streams from all major French TV, Radio, and Press outlets...")

    for media_id, config in MEDIA_SOURCES.items():
        try:
            feed = feedparser.parse(config['url'])
            media_weight = config['weight']

            for entry in feed.entries[:20]:  # Top 20 breaking articles per outlet
                text = (entry.title + " " + entry.get('summary', '')).lower()
                total_articles_scraped += 1

                for theme, keywords in LEXICONS.items():
                    for kw in keywords:
                        if re.search(r'\b' + re.escape(kw) + r'\b', text):
                            theme_scores[theme] += (1.0 * media_weight)

        except Exception as e:
            print(f"⚠️ Warning: Could not scrape {media_id}: {e}")

    # Compute percentage distribution across themes
    grand_total = sum(theme_scores.values()) or 1.0
    percentages = {
        theme: round((score / grand_total) * 100)
        for theme, score in theme_scores.items()
    }

    # Format JSON output for frontend ingestion
    output_data = {
        "timestamp": "Live Comprehensive Multi-Media Scan",
        "total_sources_monitored": len(MEDIA_SOURCES),
        "total_articles_analyzed": total_articles_scraped,
        "frames": {
            "f_sec": percentages['sec_imm'],
            "f_econ": percentages['econ_tax'],
            "f_soc": percentages['pen_soc'] + percentages['purch_inc'],
            "f_imm": round(percentages['sec_imm'] * 0.5)
        },
        "detailed_themes": percentages
    }

    # Save output to live_data.json
    with open('live_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Successfully processed {total_articles_scraped} articles across {len(MEDIA_SOURCES)} media outlets!")
    print("📊 Generated Theme Framing Output:", percentages)

if __name__ == "__main__":
    analyze_all_media()
