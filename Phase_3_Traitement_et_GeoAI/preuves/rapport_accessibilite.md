# Rapport d'accessibilité — règles du référentiel, géotraitement et réseau

Exécuté le 2026-11-18 20:07 UTC par `scripts/01_accessibilite.py`. Couches en EPSG:26191.

## Règles métier

Source : *Référentiel de programmation des équipements publics et privés d'intérêt général (2016), ch. 2 Les équipements de santé* (`references/referentiel_EPPIG_2016_sante_uniquement.pdf`), table `norme_referentiel`.

| Norme | Équipement | Niveau | Seuil de population | Accessibilité | Page |
| --- | --- | --- | --- | --- | --- |
| CSU-1 | Centre de santé urbain niveau 1 | 1 | 25 000 | 2.3 km / 30 min | p. 39-40, 79 |
| CSU-2 | Centre de santé urbain niveau 2 | 1 | 50 000 | 2.3 km / 30 min | p. 40, 79 |
| HPROX | Hôpital de proximité (ancien hôpital local) | 2 | 70 000 | non fixée | p. 39, 41, 79 |
| CHP | Centre hospitalier provincial ou préfectoral | 2 | 200 000 | non fixée | p. 39-40, 79 |
| CHR | Centre hospitalier régional | 3 | — | non fixée | p. 39, 41, 79 |
| CHI | Centre hospitalier interrégional | 3 | 2 000 000 | non fixée | p. 41, 79 |

**Conséquence** : seul le premier recours a une norme d'accès (2,3 km / 30 min, sous-entendu à pied : 4,6 km/h). Pour les hôpitaux, le référentiel raisonne en population desservie (province, région), pas en temps : les seuils en voiture restent des hypothèses, signalées comme telles.

## Scénarios

| Scénario | Niveau | Mode | Seuil | Rayon du tampon | Statut |
| --- | --- | --- | --- | --- | --- |
| N1_VOITURE_15 | 1 | voiture | 15 min | 10 km | hypothèse |
| N1_MARCHE_30 | 1 | marche | 30 min | 2.3 km | **normatif** |
| N2_VOITURE_15 | 2 | voiture | 15 min | 10 km | hypothèse |
| N2_VOITURE_30 | 2 | voiture | 30 min | 20 km | hypothèse |
| N2_VOITURE_45 | 2 | voiture | 45 min | 30 km | hypothèse |
| N3_VOITURE_15 | 3 | voiture | 15 min | 10 km | hypothèse |
| N3_VOITURE_30 | 3 | voiture | 30 min | 20 km | hypothèse |
| N3_VOITURE_45 | 3 | voiture | 45 min | 30 km | hypothèse |

Raccordement centre d'hexagone → route et route → établissement : 4.6 km/h à pied, 20 km/h en voiture. Couverture stricte : un établissement ne couvre que son niveau.

## Géotraitement vectoriel (PostGIS)

`ST_Buffer` (rayon du scénario) → `ST_Union` par scénario → `ST_Intersection` avec la région : table `zone_tampon` (0 s). Couverture à vol d'oiseau : centre de l'hexagone dans la zone.

## Analyse réseau

| Mode | Nœuds | Arcs | Règles |
| --- | --- | --- | --- |
| voiture | 228 054 | 590 094 | sens uniques respectés, vitesse du tronçon |
| marche | 227 304 | 629 562 | autoroutes exclues, double sens, 4.6 km/h |

Dijkstra multi-source (graphe inversé, super-nœud relié aux établissements) : 21 s. Table `temps_acces` : temps et établissement le plus proche par hexagone, niveau et mode.

| Niveau | Mode | Établissements | Hexagones injoignables |
| --- | --- | --- | --- |
| 1 | voiture | 373 | 5 |
| 2 | voiture | 132 | 5 |
| 3 | voiture | 4 | 5 |
| 1 | marche | 373 | 68 |

## Population couverte (population 2024 : 7 688 968)

| Scénario | Normatif | Couverte (tampon) | Couverte (réseau) | Non couverte (réseau) | Dans le tampon mais hors d'atteinte par le réseau |
| --- | --- | --- | --- | --- | --- |
| N1_VOITURE_15 | non | 98.7 % | 99.0 % | 77 231 | 61 511 |
| N1_MARCHE_30 | oui | 77.7 % | 65.8 % | 2 613 218 | 943 124 |
| N2_VOITURE_15 | non | 77.6 % | 82.1 % | 1 377 176 | 27 470 |
| N2_VOITURE_30 | non | 88.0 % | 93.7 % | 482 033 | 7 743 |
| N2_VOITURE_45 | non | 93.9 % | 98.7 % | 100 449 | 2 401 |
| N3_VOITURE_15 | non | 36.5 % | 46.6 % | 4 105 427 | 1 552 |
| N3_VOITURE_30 | non | 56.6 % | 68.5 % | 2 418 647 | 298 |
| N3_VOITURE_45 | non | 65.4 % | 73.8 % | 2 017 527 | 0 |

La dernière colonne mesure l'erreur d'une analyse à vol d'oiseau.

## Par province — scénario normatif N1_MARCHE_30

| Province | Population | Hors norme (> 30 min à pied) | Part | Temps moyen pondéré |
| --- | --- | --- | --- | --- |
| El Jadida | 907 908 | 466 017 | 51.3 % | 47 min |
| Nouaceur | 657 615 | 369 929 | 56.3 % | 35 min |
| Casablanca | 3 218 037 | 360 689 | 11.2 % | 15 min |
| Settat | 648 183 | 337 701 | 52.1 % | 47 min |
| Sidi Bennour | 451 930 | 295 853 | 65.5 % | 55 min |
| Berrechid | 639 314 | 280 800 | 43.9 % | 35 min |
| Mohammedia | 511 218 | 204 634 | 40.0 % | 27 min |
| Benslimane | 275 570 | 157 928 | 57.3 % | 52 min |
| Médiouna | 341 285 | 139 668 | 40.9 % | 30 min |

## Équilibre des classes (hexagones habités) — choix de la cible du modèle

| Scénario | Hexagones habités | Zones blanches (réseau) | Part |
| --- | --- | --- | --- |
| N1_VOITURE_15 | 7288 | 278 | 3.8 % |
| N1_MARCHE_30 | 7252 | 5841 | 80.5 % |
| N2_VOITURE_15 | 7288 | 4121 | 56.5 % |
| N2_VOITURE_30 | 7288 | 1563 | 21.4 % |
| N2_VOITURE_45 | 7288 | 343 | 4.7 % |
| N3_VOITURE_15 | 7288 | 6789 | 93.2 % |
| N3_VOITURE_30 | 7288 | 5561 | 76.3 % |
| N3_VOITURE_45 | 7288 | 4360 | 59.8 % |

Carte : `preuves/carte_temps_acces.png`.
