# Rapport du modèle Geo-AI — zones hors norme d'accès au premier recours

Exécuté le 2026-11-19 20:44 UTC par `scripts/04_modele.py` (158 s), données du commit `d52557a`.

## Formulation

| | |
| --- | --- |
| Tâche | classification binaire supervisée |
| Unité | hexagone H3 habité (résolution 8, ≈ 0,74 km²), EPSG:26191 |
| Cible | hors_norme : temps à pied > 30 min vers le centre de niveau 1 le plus proche (scénario N1_MARCHE_30) ; norme du référentiel EPPIG 2016 (CSU : 2,3 km / 30 mn) |
| Classe positive | hors norme (1) ; classe minoritaire : desservi (0) |
| Variables | 15 variables de contexte : `log_pop`, `log_pop_k1`, `log_pop_k2`, `urbaine`, `log_pop_commune`, `log_densite_commune`, `long_route_km`, `part_piste`, `nb_noeuds`, `vitesse_moy`, `dist_route_principale_m`, `dist_ville_m`, `part_residentielle`, `nuisance_pct`, `pres_grand_axe` |
| Exclues (fuite) | toute distance, tout nombre ou temps lié aux établissements ; la distance de raccordement de l'hexagone au réseau (elle entre dans le calcul de la cible) ; les coordonnées |

## Jeux d'entraînement et de test

| Jeu | Hexagones | Blocs H3 r5 | Hors norme | Population 2024 |
| --- | --- | --- | --- | --- |
| entraînement | 5537 | 73 | 78.6 % | 6 676 070 |
| test | 1715 | 25 | 85.9 % | 974 990 |

Découpage **spatial** : 25% des blocs H3 de résolution 5 (≈ 250 km²) tenus à l'écart (graine 42), jamais utilisés pour le réglage. Un hexagone et ses voisins sont donc du même côté.

## Résultats sur le jeu de test

| Modèle | Rôle | Précision | Rappel | F1 hors norme | F1 desservi | F1 macro | Exactitude équilibrée | ROC-AUC | PR-AUC desservi | Rappel pondéré population |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| classe_majoritaire | baseline | 0.859 | 1.000 | 0.924 | 0.000 | **0.462** | 0.500 | 0.500 | 0.141 | 1.000 |
| logistique_2_variables | baseline | 0.925 | 0.796 | 0.856 | 0.427 | **0.641** | 0.702 | 0.798 | 0.433 | 0.408 |
| foret_aleatoire | principal | 0.926 | 0.908 | 0.917 | 0.526 | **0.722** | 0.733 | 0.844 | 0.593 | 0.595 |
| gradient_boosting | principal | 0.932 | 0.881 | 0.906 | 0.524 | **0.715** | 0.746 | 0.827 | 0.594 | 0.631 |

Le F1 de la classe « hors norme » est trompeur ici (80 % des hexagones) : la classe majoritaire seule atteint déjà un F1 élevé sans rien apprendre. Les critères de comparaison sont le **F1 macro**, l'**exactitude équilibrée** et la **PR-AUC de la classe desservie**.

Matrices de confusion : `preuves/matrice_confusion.png`. Carte des erreurs : `preuves/carte_predictions.png`.

## Validation croisée : spatiale contre aléatoire (entraînement)

| Modèle | F1 macro, CV spatiale (GroupKFold) | F1 macro, CV aléatoire (KFold) | Écart |
| --- | --- | --- | --- |
| classe_majoritaire | 0.439 | 0.440 | +0.001 |
| logistique_2_variables | 0.704 | 0.708 | +0.004 |
| foret_aleatoire | 0.761 | 0.787 | +0.026 |
| gradient_boosting | 0.752 | 0.791 | +0.040 |

L'écart mesure l'optimisme d'une validation aléatoire : des hexagones voisins, très semblables, se retrouvent des deux côtés. C'est la raison du découpage spatial.

## Modèle principal retenu : `foret_aleatoire`

- algorithme : RandomForestClassifier ;
- hyperparamètres (choisis par CV spatiale, critère F1 macro) : `{"max_depth": 8, "min_samples_leaf": 5}` ;
- seuil de décision : 0.5 (non réglé sur le test) ;
- I de Moran des résidus sur le test (voisinage H3) : **0.638** (0 = erreurs sans structure spatiale ; > 0 = erreurs regroupées).

**Importance par permutation** (jeu de test, baisse du F1 macro, 10 répétitions) :

| Variable | Importance | Écart-type |
| --- | --- | --- |
| log_pop_k1 | 0.032 | 0.012 |
| log_pop_commune | 0.027 | 0.005 |
| dist_ville_m | 0.011 | 0.007 |
| dist_route_principale_m | 0.010 | 0.004 |
| nuisance_pct | 0.009 | 0.002 |
| vitesse_moy | 0.005 | 0.005 |
| log_densite_commune | 0.003 | 0.005 |
| part_residentielle | 0.002 | 0.002 |
| log_pop_k2 | 0.001 | 0.010 |
| long_route_km | -0.000 | 0.004 |
| pres_grand_axe | -0.001 | 0.001 |
| urbaine | -0.001 | 0.001 |
| part_piste | -0.002 | 0.004 |
| nb_noeuds | -0.003 | 0.003 |
| log_pop | -0.007 | 0.005 |

Figure : `preuves/importance_variables.png`.

## PostGIS

- `sante.modele_geoai` : 4 modèles (date, algorithme, hyperparamètres, variables, découpage, métriques de test et de CV, commit des données) ;
- `sante.prediction_h3` : prédiction du modèle principal (id 3) pour les 7252 hexagones, jeu, probabilité, type d'erreur, géométrie en EPSG:26191.

## Limites

- La cible est calculée, pas observée : elle hérite des hypothèses de l'étape 1 (réseau piéton limité aux routes, vitesse uniforme de 4,6 km/h, 93 centres en position approchée).
- WorldPop date de 2020 ; il est recalé sur le RGPH 2024 au niveau communal seulement.
- Le modèle reconnaît des CONTEXTES de zone hors norme ; il ne remplace pas le calcul réseau, exact, dès que les établissements sont connus.
- Classes déséquilibrées (80 / 20) : pondération `class_weight='balanced'`, seuil fixe à 0,5.
