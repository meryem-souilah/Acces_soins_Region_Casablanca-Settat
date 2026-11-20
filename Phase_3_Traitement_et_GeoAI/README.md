# Phase 3 — Traitement et Geo-AI

Projet **Géodata appliquée** · Accès aux soins, région Casablanca-Settat · CRS unique **EPSG:26191**.

> **Défi** : où implanter quel type d'offre de soins pour maximiser la population couverte dans le temps
> d'accès adapté à chaque niveau ?

Cette phase transforme la géodatabase de la Phase 2 en mesures d'accessibilité conformes aux règles
officielles, puis entraîne et évalue un modèle Geo-AI qui reconnaît les territoires hors norme d'accès au
premier recours. Tous les résultats sont écrits dans PostGIS (schéma `sante`), avec leurs métadonnées.

---

## 1. Règles métier : le référentiel

Les règles viennent du *Référentiel de programmation des équipements publics et privés d'intérêt général*
(2016), chapitre 2 « Les équipements de santé », p. 39-41 et récapitulatif p. 79
([`references/referentiel_EPPIG_2016_sante_uniquement.pdf`](references/referentiel_EPPIG_2016_sante_uniquement.pdf)).
Elles sont stockées comme données dans la table `norme_referentiel`, sans interprétation.

| Équipement | Niveau | Seuil de population | Accessibilité | Usage dans le traitement |
| --- | --- | --- | --- | --- |
| Centre de santé urbain CSU-1 / CSU-2 | 1 | 25 000 / 50 000 hab. | **2,3 km / 30 min** | tampon réglementaire de 2,3 km ; temps à pied ≤ 30 min ; 1 CSU pour 25 000 hab. en commune urbaine |
| Hôpital de proximité | 2 | 70 000 hab. | non fixée | contrôle par province |
| Centre hospitalier provincial (CHP) | 2 | 200 000 hab. | non fixée | contrôle par province |
| Centre hospitalier régional (CHR) | 3 | un par région | non fixée | contrôle régional |
| Critères de localisation (p. 39) | — | — | — | zones d'exclusion et de proximité (§ 3.2) |

**Le référentiel ne fixe un temps d'accès que pour le premier recours.** Pour les hôpitaux, il raisonne en
population desservie. Les seuils de 15, 30 et 45 min en voiture des niveaux 2 et 3 sont donc des
**hypothèses** issues du cadrage (Phase 0), signalées comme telles (`scenario_acces.normatif = false`).

---

## 2. Chaîne de traitement

À lancer depuis ce dossier, après la Phase 2 (base `acces_soins` chargée), avec le Python de l'environnement
`geodata-sante` :

```bat
set PY=C:\Users\pc\anaconda3-pbe\envs\geodata-sante\python.exe
%PY% scripts\01_accessibilite.py
%PY% scripts\02_contraintes_localisation.py
%PY% scripts\03_features.py
%PY% scripts\04_modele.py
```

La connexion à PostgreSQL se fait par le fichier `.env` à la racine du dépôt (`PGPASSWORD=…`), jamais en
argument. Chaque script recrée ses tables : la chaîne peut être rejouée.

| Script | Rôle (consigne) | Tables PostGIS | Preuves |
| --- | --- | --- | --- |
| `01_accessibilite.py` (≈ 1 min) | Normes et scénarios ; **buffers + overlays** (`ST_Buffer` → `ST_Union` → `ST_Intersection`) ; **analyse réseau** (Dijkstra multi-source, à pied et en voiture) | `norme_referentiel`, `scenario_acces`, `zone_tampon`, `temps_acces`, vues `v_maille_pop`, `v_couverture_h3`, `v_capacite_commune`, `v_capacite_province` | [`rapport_accessibilite.md`](preuves/rapport_accessibilite.md), [`carte_temps_acces.png`](preuves/carte_temps_acces.png) |
| `02_contraintes_localisation.py` (≈ 35 s) | Critères de localisation du référentiel par **overlays** (nuisances, grands axes) | `osm_contrainte`, `contrainte_localisation`, `aptitude_h3` | [`rapport_contraintes.md`](preuves/rapport_contraintes.md), [`carte_contraintes.png`](preuves/carte_contraintes.png) |
| `03_features.py` (≈ 75 s) | Variables de contexte et cible du modèle | `feature_h3` | — |
| `04_modele.py` (≈ 2 min) | Découpage spatial, baselines, modèles, évaluation, import | `modele_geoai` (métadonnées), `prediction_h3` (couche dérivée) | [`rapport_modele.md`](preuves/rapport_modele.md), [`matrice_confusion.png`](preuves/matrice_confusion.png), [`carte_predictions.png`](preuves/carte_predictions.png), [`importance_variables.png`](preuves/importance_variables.png) |

Fichiers communs : `scripts/commun.py` (connexion, chemins), `sql/schema_phase3.sql`, `sql/schema_modele.sql`.
Modèle entraîné : `donnees/modele_principal.joblib`.

---

## 3. Géotraitement vectoriel et analyse réseau

### 3.1 Accessibilité

| Choix | Valeur | Justification |
| --- | --- | --- |
| Unité de demande | hexagone H3 résolution 8 (≈ 0,74 km²) | maille régulière du cadrage |
| Population | WorldPop 2020 recalé sur le RGPH 2024 par commune (vue `v_maille_pop`) | répartition fine, total officiel (7 688 968 hab.) |
| Niveau 1 | **à pied, 4,6 km/h, seuil 30 min** ; tampon de 2,3 km | la norme CSU elle-même (2,3 km en 30 min) |
| Réseau piéton | tous les tronçons sauf autoroutes, dans les deux sens | un piéton ignore les sens uniques |
| Niveaux 2 et 3 | en voiture, vitesse du tronçon, sens uniques respectés ; seuils 15, 30, 45 min | hypothèses (aucune norme) ; tampon = seuil × 40 km/h |
| Raccordement | centre de l'hexagone → nœud le plus proche (et nœud → établissement) à 4,6 km/h à pied, 20 km/h en voiture | on ne démarre pas sur la route |
| Algorithme | Dijkstra multi-source sur le graphe inversé, depuis un super-nœud relié à tous les établissements d'un niveau | un seul calcul par niveau : temps et établissement le plus proche pour chaque hexagone |
| Niveaux de soins | niveau 1 : 373 centres de santé et dispensaires du Ministère + 58 cabinets médicaux OSM (431) ; niveau 2 : 131 hôpitaux et cliniques ; niveau 3 : 4 sites (CHU Ibn Rochd et son site du 20 Août, hôpital universitaire Cheikh Khalifa, CHR Moulay Youssef) | définition du cadrage (Phase 0) ; centres de santé OSM exclus (doublons des centres du Ministère) |
| Couverture | stricte : un établissement ne couvre que son niveau ; **non stricte** en comparaison (scénarios `_NS`) : un niveau supérieur couvre aussi les niveaux inférieurs | règle du cadrage et comparaison qu'il prévoyait |

**Résultats principaux** (population 2024) :

| Scénario | Statut | Couverte à vol d'oiseau | Couverte par le réseau | Hors d'atteinte malgré le tampon |
| --- | --- | --- | --- | --- |
| Niveau 1, 30 min à pied | **normatif** | 78,1 % | **66,5 %** | 925 862 hab. |
| Niveau 1, 30 min à pied, couverture non stricte | comparaison | 78,8 % | 68,4 % | 843 087 hab. |
| Niveau 2, 30 min en voiture | hypothèse | 88,0 % | 93,7 % | 7 743 hab. |
| Niveau 2, 30 min en voiture, couverture non stricte | comparaison | 88,0 % | 93,7 % | 7 743 hab. |
| Niveau 3, 45 min en voiture | hypothèse | 65,4 % | 73,8 % | 0 |

- **2,56 millions d'habitants sont hors norme d'accès au premier recours.** La part dépasse 50 % à Sidi
  Bennour, Benslimane, Nouaceur et Settat (El Jadida : 47 %).
- L'analyse à vol d'oiseau surestime la couverture à pied : **925 862 habitants** sont à moins de 2,3 km d'un
  établissement de niveau 1, mais à plus de 30 min par le réseau.
- Couverture non stricte : compter les hôpitaux et CHU comme soins de proximité n'ajoute que 1,9 point
  (142 990 hab.) ; au niveau 2, aucun effet (les CHU sont à Casablanca, déjà couverte). La règle stricte du
  cadrage ne change donc pas le diagnostic.
- Cabinets médicaux : les ajouter au niveau 1 fait passer la couverture de 65,8 % à 66,5 % ; les 58 cabinets
  recensés par OSM sont surtout urbains (38 à Casablanca, 15 à El Jadida).
- Capacité : les communes urbaines ont 199 centres de santé publics pour 255 requis (1 CSU pour 25 000 hab.),
  soit **61 manquants** (Casablanca −23, Dar Bouazza −6, Bouskoura −4). Les cabinets privés ne sont pas
  comptés : la règle porte sur le centre de santé urbain public.

### 3.2 Critères de localisation

`ST_Buffer` de chaque nuisance, `ST_Union` par catégorie, puis `ST_Intersection` avec la région ; ensuite
`ST_Intersection` / `ST_Area` avec chaque hexagone.

| Catégorie (référentiel p. 39) | Effet | Distance | Source OSM |
| --- | --- | --- | --- |
| voies ferrées, industrie et carrières, décharges, stations-service | exclure (CSU, hôpitaux) | 100 m | Geofabrik : railways, landuse, traffic |
| grands axes (autoroutes, voies express) | exclure (CSU) | 100 m | Geofabrik : roads |
| zones résidentielles | exclure (hôpitaux) | 0 m | Geofabrik : landuse |
| grands axes de circulation (autoroute, voie express, route principale) | favoriser (hôpitaux) | 2 km | Geofabrik : roads |

Hexagone **apte CSU** : moins de 50 % en zone de nuisance (97 % des hexagones habités). **Apte hôpital** :
à moins de 2 km d'un grand axe, moins de 50 % en nuisance et en zone résidentielle (42 %). Ces couches
servent de variables du modèle et serviront à filtrer les sites candidats.

---

## 4. Formulation Geo-AI

| | |
| --- | --- |
| Tâche | **classification binaire supervisée** |
| Unité | hexagone H3 habité (7 252, dont 80 % hors norme) |
| Cible | `hors_norme` = 1 si le centre de niveau 1 le plus proche est à **plus de 30 min à pied** (norme CSU), calculé à l'étape 3.1 |
| Question | le contexte d'un territoire suffit-il à reconnaître une zone hors norme, et quels facteurs l'expliquent ? |
| Usage | repérer les territoires à risque et expliquer les déficits pour appuyer le choix des sites |

**Variables (15, contexte uniquement)** :

| Famille | Variables |
| --- | --- |
| Population | `log_pop`, `log_pop_k1`, `log_pop_k2` (hexagone et voisinage H3 à 1 et 2 anneaux) |
| Commune | `urbaine`, `log_pop_commune`, `log_densite_commune` |
| Réseau routier | `long_route_km`, `part_piste`, `nb_noeuds`, `vitesse_moy` (par `ST_Intersection` des tronçons avec l'hexagone), `dist_route_principale_m` |
| Urbanisation | `dist_ville_m` (ville ou bourg OSM le plus proche), `part_residentielle` |
| Référentiel | `nuisance_pct`, `pres_grand_axe` |

**Variables exclues pour éviter les fuites** : toute distance, tout nombre ou temps lié aux établissements
de santé ; la distance de raccordement de l'hexagone au réseau (elle entre dans le calcul de la cible) ;
les coordonnées (le modèle apprendrait la carte au lieu du contexte).

---

## 5. Protocole d'apprentissage et choix documentés

| Choix | Décision | Pourquoi |
| --- | --- | --- |
| Découpage | **spatial** : 25 % des blocs H3 de résolution 5 (≈ 250 km²) en test, graine 42 (5 537 hexagones en entraînement, 1 715 en test) | des hexagones voisins se ressemblent ; un découpage aléatoire mettrait des quasi-doublons des deux côtés |
| Réglage | `GridSearchCV` avec `GroupKFold` (5 plis, groupes = blocs) sur l'entraînement, critère F1 macro | le test reste intact jusqu'à l'évaluation finale |
| Déséquilibre (80 / 20) | `class_weight="balanced"`, seuil de décision 0,5, non réglé sur le test | ne pas favoriser la classe majoritaire ; pas d'optimisation sur le test |
| Baseline triviale | classe majoritaire | ce qu'on obtient sans rien apprendre |
| Baseline simple | régression logistique sur 2 variables (`log_pop_k1`, `dist_ville_m`) | « dense et proche d'une ville = desservi » |
| Modèles | forêt aléatoire (400 arbres) ; gradient boosting (`HistGradientBoostingClassifier`) | non linéaires, robustes aux variables corrélées, interprétables par permutation ; données tabulaires : le deep learning n'apporterait rien de défendable |
| Grilles | forêt : `max_depth` ∈ {8, 16, ∞}, `min_samples_leaf` ∈ {5, 20} ; boosting : `learning_rate` ∈ {0,03 ; 0,1}, `max_leaf_nodes` ∈ {15, 31}, `min_samples_leaf` ∈ {20, 60}, `l2_regularization` ∈ {0, 1} | petites grilles, plis spatiaux |
| Sélection du modèle principal | meilleur F1 macro en **CV spatiale** (pas sur le test) | éviter de choisir sur le test |
| Métriques | précision, rappel, F1 des deux classes, **F1 macro**, **exactitude équilibrée**, ROC-AUC, PR-AUC de la classe minoritaire, matrice de confusion, rappel pondéré par la population | avec 80 % de positifs, le F1 « hors norme » seul est trompeur |
| Contrôles | CV spatiale contre CV aléatoire ; I de Moran des résidus ; importance par permutation sur le test | mesurer l'optimisme, la structure spatiale des erreurs et le rôle des variables |

### Résultats sur le jeu de test

| Modèle | Rôle | F1 macro | Exactitude équilibrée | F1 hors norme | F1 desservi | ROC-AUC |
| --- | --- | --- | --- | --- | --- | --- |
| Classe majoritaire | baseline | 0,462 | 0,500 | 0,924 | 0,000 | 0,500 |
| Logistique 2 variables | baseline | 0,641 | 0,702 | 0,856 | 0,427 | 0,798 |
| **Forêt aléatoire** (`max_depth=8`, `min_samples_leaf=5`) | **principal** | **0,722** | 0,733 | 0,917 | 0,526 | **0,844** |
| Gradient boosting | candidat | 0,715 | 0,746 | 0,906 | 0,524 | 0,827 |

- Le modèle principal dépasse la baseline simple de **+0,08 en F1 macro** et **+0,05 en ROC-AUC**.
- La forêt aléatoire est retenue parce qu'elle a le meilleur score en CV spatiale (0,761 contre 0,752), règle
  fixée avant de regarder le test. Sur le test, elle a aussi le meilleur F1 macro (0,722 contre 0,715).
- Résultats reproductibles : graine 42 et lecture des variables dans un ordre fixe (`ORDER BY h3_index`).
- **CV aléatoire contre CV spatiale** : +0,026 (forêt) et +0,040 (boosting). La validation aléatoire est
  optimiste, ce qui confirme la nécessité du découpage spatial.
- Variables les plus utiles : population du voisinage, population de la commune, distance à la ville.

### Intégration PostGIS

- **`sante.modele_geoai`** : une ligne par modèle (baselines comprises), avec date du traitement,
  algorithme, hyperparamètres (JSON), variables, cible, découpage, effectifs, seuil, toutes les métriques de
  test, matrice de confusion, F1 en CV spatiale et aléatoire, commit git des données.
- **`sante.prediction_h3`** : couche dérivée du modèle principal ; pour chaque hexagone, le jeu
  (train / test), la classe réelle et prédite, la probabilité, le type d'erreur (VP/VN/FP/FN) et la
  géométrie `Polygon` en **EPSG:26191**.

Contrôle rapide dans pgAdmin :

```sql
SELECT nom, role, f1_macro_test, exactitude_equilibree_test, roc_auc_test, date_traitement
FROM sante.modele_geoai ORDER BY f1_macro_test DESC;

-- recalcul du F1 macro depuis la couche dérivée (doit égaler f1_macro_test du modèle principal)
WITH m AS (SELECT count(*) FILTER (WHERE erreur = 'VP') vp, count(*) FILTER (WHERE erreur = 'FP') fp,
                  count(*) FILTER (WHERE erreur = 'FN') fn, count(*) FILTER (WHERE erreur = 'VN') vn
           FROM sante.prediction_h3 WHERE jeu = 'test')
SELECT (2.0 * vp / (2 * vp + fp + fn) + 2.0 * vn / (2 * vn + fn + fp)) / 2 AS f1_macro FROM m;
```

---

## 6. Limites

**Accessibilité**
- Le réseau piéton ne contient que les routes : chemins et sentiers ont été retirés en Phase 2. Le temps à
  pied est donc surestimé en zone rurale.
- Vitesse à pied uniforme (4,6 km/h, déduite de la norme) ; en voiture, 94 % des tronçons ont une vitesse
  par défaut selon leur type.
- Cabinets médicaux : OSM n'en recense que 58, presque tous urbains ; l'offre privée de proximité est
  sous-estimée, surtout en zone rurale.
- 93 centres du Ministère ont une position approchée (centre habité de la commune) ; 38 hexagones
  habités (37 908 hab.) ne sont reliés qu'à des autoroutes et sont exclus du scénario à pied.
- Les seuils des niveaux 2 et 3 sont des hypothèses : le référentiel n'en donne pas.
- La règle de capacité des CSU ne concerne que les communes urbaines ; le référentiel ne traite pas les
  centres ruraux (CSR, dispensaires). La commune de Casablanca est traitée en bloc, pas par arrondissement.

**Critères de localisation**
- Distances d'éloignement (100 m) et de proximité (2 km) choisies faute de valeurs dans le référentiel.
- Lignes à haute tension et zones inondables : absentes des données OSM disponibles.
- Zones résidentielles OSM incomplètes : la règle « éviter les zones résidentielles » n'est appliquée que
  partiellement.

**Modèle**
- La cible est calculée, pas observée : elle hérite des hypothèses ci-dessus.
- **Erreurs regroupées dans l'espace** (I de Moran des résidus = 0,64), surtout en périphérie des bourgs.
  Le modèle ne connaît pas la position des centres (règle anti-fuite), or c'est elle qui décide de la
  desserte à ces limites. Il reconnaît des contextes ; il ne remplace pas le calcul réseau, exact quand les
  établissements sont connus.
- Classe « desservi » moins bien reconnue (F1 0,53) que la classe « hors norme » (F1 0,92).
- Les blocs de test sont plus ruraux que l'entraînement (85,9 % contre 78,6 % de zones hors norme).
- Variables de population corrélées : leur importance par permutation est partagée et reste faible.
- WorldPop date de 2020 et n'est recalé sur le RGPH 2024 qu'au niveau communal.

**Piste d'amélioration** : ajouter la densité de bâtiments OSM (couche `buildings` de Geofabrik), sans doute
le meilleur signal pour les périphéries de bourgs, puis relancer `03` et `04` avec le même protocole.

---

## 7. Note technique (Windows)

numpy (conda) utilise Intel MKL 2026.1, dont la couche de threads OpenMP par défaut fait planter Python sans
message (code `0xc06d007f`) au premier produit matriciel, dans matplotlib comme dans scikit-learn.
`Phase_2_Pretraitement_et_Geodatabase/scripts/config.py`, importé en premier par tous les scripts, impose
`MKL_THREADING_LAYER=TBB` (ou `SEQUENTIAL` si TBB est absent).
