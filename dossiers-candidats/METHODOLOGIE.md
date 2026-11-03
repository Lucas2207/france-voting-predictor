# Méthodologie de recherche : émissions et articles sur les candidats à la présidentielle 2027

Relevé le 1er novembre 2026. Période visée : du 1er juillet 2026 à aujourd'hui.

## 1. Radio France (radiofrance.fr)

**Source :** la page personnelle de chaque personnalité (`/personnes/<nom>` ou `/personnes/<nom>-politique` pour Fabien Roussel). Elle liste les émissions et articles rattachés à la personne, sur plusieurs pages (`?p=2`, `?p=3`…).

**Relevé :**
- lecture de chaque page, en gardant les entrées datées de 2026 ;
- arrêt à la première entrée antérieure au 1er juillet 2026 ;
- titre et chapô de chaque entrée, sans ouverture de l'article.

**Limites :**
- un article n'apparaît sur la page d'une personne que s'il est rattaché à elle. Un article qui cite un candidat dans son chapô peut être rattaché à un autre (exemple : l'article du 7 septembre sur Fabien Roussel, rattaché à Jean-Luc Mélenchon) ;
- les entrées mises en avant en haut de page sans date sont vérifiées par l'adresse de leur article.

**Classement (Oui / Partiellement / Non) :**
- **Oui** : la personne est dans le titre, ou sa candidature, son action ou ses propositions sont le sujet principal ;
- **Partiellement** : elle figure dans le titre ou le chapô parmi d'autres acteurs ou sujets ;
- **Non** : le sujet central est un autre acteur ou un autre thème.

**Contrôles :** recherche de doublons par titre, et contrôle du nombre de lignes par rapport au total annoncé.

**Notes par candidat (relevés initiaux) :**
- Marine Le Pen : un doublon supprimé, « Condamnation de Marine Le Pen : quelles conséquences pour 2027 ? » (7 juillet), diffusé à la fois dans « Le téléphone sonne » et « Édition spéciale de la rédaction » ; une seule ligne est conservée. 136 émissions.
- Fabien Roussel : le fil compte 7 entrées ; les pages 2 et 3 sont vides. Deux entrées (1er avril et 24 février 2026) sont antérieures au 1er juillet et ne sont pas retenues. Le chapô d'une entrée peut citer Fabien Roussel sans que l'article soit rattaché à sa page (article du 7 septembre, classé car il figure sur sa page).
- Éric Zemmour : le fil remonte jusqu'au 18 juin 2026 ; la page 2 ne contient qu'une entrée de janvier et la page 3 est vide. 9 émissions depuis le 1er juillet.
- David Lisnard : le fil est court (page 1 : 16 entrées, dont 8 depuis le 1er juillet ; page 2 vide).
- Pour tous les candidats : aucun doublon, sauf celui de Marine Le Pen signalé ci-dessus.

**Erreurs corrigées au cours du relevé :**
- une entrée inventée pour Marine Le Pen (7 juillet) a été remplacée par le vrai titre ;
- un article sur Fabien Roussel était classé par erreur comme absent ;
- Philippe Brun (homonyme d'Édouard Philippe) est exclu des résultats d'Édouard Philippe sur BFMTV.

## 2. BFMTV (bfmtv.com)

**Source :** la rubrique présidentielle `/politique/elections/presidentielle/`, pages 1 à 20 (`/pageN/`). Il n'existe ni moteur de recherche ni page par personnalité : `/recherche/` et `/tag/` renvoient une erreur 404.

**Relevé :**
- lecture des 20 pages de la rubrique, avec filtre sur les adresses d'articles datés du 1er juillet 2026 ou après, contenant le nom d'un candidat ;
- la date est lue dans l'adresse (format `_AD-AAAAMMJJhhmm`) ;
- les titres sont reconstitués à partir des adresses (accents et ponctuation absents) ;
- les résultats intermédiaires ont été accumulés dans le stockage de session du site, puis relus.

**Limites :**
- la rubrique ne remonte qu'à fin septembre 2026 (la page 21 n'existe pas). Les articles de juillet à septembre ne sont donc pas couverts ;
- une adresse ne contient pas toujours le nom complet, et certains titres sont tronqués ;
- la rubrique mélange des articles d'années antérieures (2021 et 2022), qui sont écartés.

**Classement automatique (à vérifier) :** un article est attribué à un candidat si son nom est le premier cité dans le titre, ou s'il est l'auteur des propos (verbe de parole juste avant le nom : « déclare », « estime », « affirme », « assure », etc.). Les articles où le candidat n'est que cité ne sont pas listés.

**Contrôles :** nombre de lignes de chaque dossier comparé au total annoncé ; le total a été aligné sur les lignes du tableau.

## 3. TF1 (tf1info.fr)

**Source :** la recherche du site, `https://www.tf1info.fr/recherche/?query=<nom complet>`. Une page affiche 10 résultats ; le bouton « Voir plus de résultats » en ajoute 10.

**Limite de la recherche :** elle n'a pas de filtre de date et classe les résultats par pertinence, avec des articles de 2017 à 2026 mêlés. Le tri par date (`sort=date`) ne change pas l'ordre. Il n'est donc pas possible de s'arrêter au 1er juillet : les articles de la période sont relevés parmi les résultats chargés.

**Relevé :**
- chargement de la recherche, puis 8 extensions du bouton « Voir plus de résultats » (90 résultats au total) pour chaque candidat ;
- 16 extensions (170 résultats) pour les candidats qui ont au moins un article de la période à la 8e extension : Marine Le Pen, Gabriel Attal, Fabien Roussel, et Jean-Luc Mélenchon (demandé explicitement) ;
- pour chaque résultat : titre, adresse et date lue dans « Publié le … ». Les pages de tag sans date sont écartées ;
- sont retenus les articles datés du 1er juillet au 1er novembre 2026 dont le nom du candidat figure dans le titre.

**Limites :**
- le chapô n'est pas affiché sur la page de recherche : seul le titre est vérifié ;
- l'ordre des résultats n'est pas stable d'un passage à l'autre. Pour Fabien Roussel, un article apparu à la 8e extension lors d'un passage est revenu à la 7e lors d'un second passage ;
- au-delà de la 8e extension, les articles de la période sont rares, mais la recherche n'est pas exhaustive (par exemple 2 320 résultats pour Nicolas Dupont-Aignan, 21 100 pour Raphaël Glucksmann) ;
- « Le Pen » peut retenir quelques articles sur Jean-Marie Le Pen.

**Articles de la période apparaissant après la 8e extension :**
- Marine Le Pen : 7 (de la 9e à la 16e extension) ;
- Gabriel Attal : 1 (16e extension) ;
- Jean-Luc Mélenchon : 3 (11e et 12e extensions) ;
- Fabien Roussel : aucun au second passage.

**Contrôles :** nombre de lignes de chaque section TF1 comparé au total annoncé.

## 4. franceinfo (franceinfo.fr)

**Source :** la recherche du site, `https://www.franceinfo.fr/recherche/?request=<nom complet>`. La première page affiche 20 contenus ; les pages suivantes sont `/recherche/N.html?request=<nom>`.

**Limite de la recherche :** la recherche renvoie au maximum 200 contenus (pages 1 à 10 ; la page 11 renvoie une erreur 410). Elle n'a pas de filtre de date. Les résultats sont classés par pertinence, puis dans l'ensemble par date décroissante, mais pas strictement d'une page à l'autre (par exemple la page 6 contient des articles de 2015). Les articles de la période sont donc retenus parmi les 200 résultats.

**Relevé :**
- chargement des pages 1 à 10 de chaque recherche, en lisant pour chaque carte le lien, le titre, le chapô et la date « Publié le JJ/MM/AAAA » ;
- sont retenus les articles datés du 1er juillet au 1er novembre 2026 dont le nom du candidat figure dans le titre ou dans le chapô, comme pour les autres médias ;
- un article dont le nom n'apparaît que dans le chapô est marqué « (chapô) » dans le tableau ;
- le nom de famille seul sert au filtre, sauf pour Édouard Philippe, où le filtre exige « Édouard Philippe » pour exclure Jean-Philippe Tanguy et d'autres homonymes.

**Limites :**
- la limite de 200 contenus fait que des articles de la période peuvent ne pas figurer dans les résultats : la recherche renvoie 200 contenus uniques pour Raphaël Glucksmann et pour Marine Le Pen, sans qu'il soit possible de savoir combien d'autres articles de la période existent ;
- « Le Pen » peut retenir des articles sur Jean-Marie Le Pen : pour Marine Le Pen, un article de ce type (17 août) a été vérifié à la main et retiré. Un article du 15 septembre (« RN : un parti, deux lignes entre Le Pen et Bardella ? ») désigne la candidate sans la nommer dans le titre ou le chapô, et reste compté ;
- un même article peut être compté pour plusieurs candidats s'il les cite tous les deux (exemple : « Marine Le Pen, Gabriel Attal, Édouard Philippe... »).

**Contrôles :** nombre de lignes de chaque section franceinfo comparé au total annoncé.

## 5. Le Monde (lemonde.fr)

**Source :** la recherche du site, `https://www.lemonde.fr/recherche/?search_keywords=<nom complet>&start_at=01%2F07%2F2026&end_at=01%2F11%2F2026&page=N`. Les dates de début et de fin sont appliquées par le site, au format JJ/MM/AAAA. Une page affiche 40 résultats ; la pagination s'arrête à la page renvoyant une erreur 404.

**Relevé :**
- chargement de chaque page de résultats (`page=1`, `page=2`…) jusqu'à la 404 : pour Marine Le Pen, 502 résultats sur 13 pages ; pour Raphaël Glucksmann, 226 sur 6 pages ;
- pour chaque résultat : titre, chapô et adresse de l'article. La date est lue dans l'adresse (`/article/AAAA/MM/JJ/`), car certaines cartes affichent « Publié hier » ;
- sont retenus les articles datés du 1er juillet au 1er novembre 2026 dont le nom du candidat figure dans le titre ou le chapô ; un article dont le nom n'apparaît que dans le chapô est marqué « (chapô) ».

**Limites :**
- le site limite les requêtes : après plusieurs pages, il renvoie une erreur 429. La collecte a été reprise à la page interrompue après une pause, sans perte de pages ;
- « Le Pen » peut retenir des articles sur Jean-Marie Le Pen. Pour Marine Le Pen, deux articles de ce type (7 octobre et 4 juillet) ont été vérifiés à la main et retirés ; un article du 30 août (Lisnard, « second tour Le Pen-Mélenchon » dans le chapô) désigne la candidate sans la nommer et reste compté ;
- le nom de famille « Roussel » ou « Ruffin » peut désigner une autre personne : pour François Ruffin, un article sur Laurence Ruffin, maire de Grenoble, a été retiré à la main ;
- le chapô étant souvent complet, un article peut être compté pour un candidat parce qu'il le cite sans être centré sur lui (même convention que pour les autres médias).

**Contrôles :** nombre de lignes de chaque section Le Monde comparé au total annoncé ; vérification du sujet pour Marine Le Pen et François Ruffin.

## 6. CNEWS (cnews.fr)

**Source :** la recherche du site, `https://www.cnews.fr/rechercher/<nom complet>`. Une page affiche 20 résultats, triés par date décroissante ; la pagination est gérée par le serveur (`?_wrapper_format=html&page=N`).

**Relevé :**
- chargement des pages de résultats jusqu'à deux pages consécutives entièrement antérieures au 1er juillet 2026. L'ordre par date n'est pas strictement respecté (une page peut contenir un article plus récent que la précédente) : une seule page ancienne ne suffit donc pas à arrêter le relevé ;
- date lue dans l'adresse de l'article (`/AAAA-MM-JJ/`), car les cartes de résultats n'affichent pas la date. Pour les émissions vidéo, la date de l'adresse peut être d'un jour après celle indiquée dans le titre (« Émission du 08/09/2026 » listé au 09/09) ;
- sont retenus les articles datés du 1er juillet au 1er novembre 2026 dont le nom du candidat figure dans le titre. Le chapô n'est pas affiché sur la page de recherche : seul le titre est vérifié, comme pour TF1 ;
- le « En direct » placé devant certains titres est retiré.

**Limites :**
- la recherche porte sur le texte des articles, pas sur le titre : des articles qui citent le candidat sans le nommer dans le titre ne sont pas retenus ;
- le nom de famille sert au filtre, sauf pour Édouard Philippe (« Édouard Philippe », pour exclure les homonymes). Pour Marine Le Pen, aucun des 140 titres chargés ne concerne Jean-Marie ou Marie-Caroline Le Pen ;
- pas de vérification du sujet au-delà du titre : un article peut être compté pour un candidat parce qu'il le nomme sans être centré sur lui (même convention que pour les autres médias) ;
- la recherche renvoie beaucoup de résultats pour les candidats les plus cités (1 280 pour Marine Le Pen) ; l'exhaustivité n'est pas garantie, puisque l'arrêt dépend de l'ordre par date.

**Contrôles :** nombre de lignes de chaque section CNEWS comparé au total annoncé. Aucun article de la période pour Nathalie Arthaud ; un seul pour François Ruffin.

## 7. Libération (liberation.fr)

**Source :** la recherche avancée du site, `https://www.liberation.fr/recherche/?searchKeywords=<nom complet>&sort=date`, avec les champs « Du » et « Au » réglés sur le 01/07/2026 et le 01/11/2026 (`startDate` et `endDate` dans l'adresse). Les mêmes bornes sont envoyées à l'interface de recherche du site.

**Relevé :**
- l'interface renvoie au plus 29 contenus par requête, sans pagination exploitable. Le relevé découpe donc la période en fenêtres de dates de plus en plus fines, jusqu'à ce qu'une fenêtre renvoie moins de 29 contenus. Chaque article est ainsi récupéré une fois, sans trou dans la période ;
- date lue dans la réponse du site (`displayDate`) ;
- sont retenus les articles datés du 1er juillet au 1er novembre 2026 dont le nom du candidat figure dans le titre ou dans le chapô. Un article dont le nom n'apparaît que dans le chapô est marqué « (chapô) ».

**Limites :**
- la recherche porte sur le texte des articles : un article qui cite le candidat seulement dans le corps du texte n'est pas retenu ;
- le filtre sur le nom de famille suit la même convention que pour les autres médias : « Le Pen » peut retenir des titres sur Jean-Marie ou Marie-Caroline Le Pen, et les titres qui en portent le nom sont écartés ;
- un article peut être compté pour plusieurs candidats s'il les cite tous les deux.

**Contrôles :** nombre de lignes de chaque section Libération comparé au total annoncé.

## 8. Ouest-France (ouest-france.fr)

**Source :** la recherche du site, `https://www.ouest-france.fr/recherche/?q=<nom complet>`, onglet « Actualités ». Les résultats sont affichés par pages de 20 articles, avec la pagination du site (`#!r/…&page=N`).

**Accès :** les résultats n'apparaissent qu'après acceptation des cookies publicitaires du site. Le consentement a été donné par la personne qui a mené le relevé.

**Relevé :**
- les dates de période ont été réglées dans le filtre « Période personnalisée » (1er juillet – 1er novembre 2026), mais la liste affichait encore des articles hors période (par exemple un article de mars 2026). Le relevé a donc été fait sans filtre de date ;
- les pages sont lues une à une jusqu'à une page dont tous les articles sont antérieurs au 1er juillet 2026 ;
- date lue sur chaque carte de résultat, titre tel qu'affiché ;
- sont retenus les articles datés du 1er juillet au 1er novembre 2026 dont le nom du candidat figure dans le titre. Le chapô n'est pas relevé ;
- les libellés « Réservé aux abonnés Ouest-France » et « bloqué » ajoutés au titre sont retirés.

**Limites :**
- le classement du site est par pertinence, et non strictement par date : un article de la période peut apparaître après une page entièrement antérieure. Le relevé s'arrête donc à la première page entièrement antérieure, comme pour les autres médias sans tri fiable ;
- la recherche porte sur le texte des articles : un article qui cite le candidat seulement dans le corps du texte n'est pas retenu ;
- « Le Pen » retient aussi les titres où Marie-Caroline Le Pen est citée, quand le titre contient aussi « Marine Le Pen » ; aucun titre sur Jean-Marie Le Pen n'est présent dans les résultats chargés ;
- un article peut être compté pour plusieurs candidats s'il les cite tous les deux.

**Contrôles :** nombre de lignes de chaque section Ouest-France comparé au total annoncé. Un article omis lors de la première transcription (Marine Le Pen, 7 juillet) a été ajouté après comparaison avec les résultats chargés.

## 9. Ce qui n'est pas fait

- pas d'ouverture des articles un par un : le classement se base sur le titre et le chapô ou l'adresse ;
- pas de couverture de BFMTV pour juillet à septembre 2026 ;
- les dossiers Radio France ne sont pas tous à jour pour les personnalités sans page propre (Zemmour, Lisnard, Roussel) : ils sont couverts par les pages des autres personnalités citées dans les chapôs.

## 10. Fichiers

- Dossiers par candidat : `dossiers-candidats/<nom>/README.md`
- Tableaux Radio France : section « Radio France » de chaque dossier (les anciens fichiers `radio-france-<nom>-emissions.md` à la racine ont été supprimés une fois repris dans les dossiers)
