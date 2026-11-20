# Rapport de nettoyage

Exécuté le 2026-11-19 20:32 UTC par `scripts/nettoyage.py` — étapes : communes, etablissements, routes, h3.

Sortie : `donnees_propres/base_sante.gpkg`.

Toutes les couches sont en EPSG:26191. Le détail entité par entité est dans `preuves/journal_nettoyage.csv`.

## Communes et provinces

Format de la couche source : colonnes déjà normalisées (code_hcp, code_province, nom).

| Contrôle | Avant | Après |
| --- | --- | --- |
| Communes | 153 | 153 |
| Géométries invalides | 0 | 0 |
| Codes communaux en double | 0 | 0 |
| Provinces / préfectures dérivées | — | 9 |

| Code | Province | Type | Communes |
| --- | --- | --- | --- |
| 06.111 | Benslimane | province | 15 |
| 06.117 | Berrechid | province | 22 |
| 06.141 | Casablanca | prefecture | 2 |
| 06.181 | El Jadida | province | 27 |
| 06.355 | Médiouna | province | 5 |
| 06.371 | Mohammedia | prefecture | 6 |
| 06.385 | Nouaceur | province | 5 |
| 06.461 | Settat | province | 46 |
| 06.467 | Sidi Bennour | province | 25 |

**Population légale RGPH 2024** (`pop_2024`) : jointure par code géographique HCP (`code_hcp` = `code_geographique` du tableau communal), sans appariement de noms.

| Contrôle | Valeur |
| --- | --- |
| Communes avec population | 153 / 153 |
| Somme des communes | 7 688 967 |
| Total régional publié par le HCP | 7 688 967 |
| Écart | +0 |

## Établissements de santé

| Contrôle | Avant | Après |
| --- | --- | --- |
| Entités | 1591 | 1571 |
| Géométries absentes ou non ponctuelles | 0 | 0 |
| Paires de doublons point / polygone fusionnées | — | 20 |
| Entités supprimées comme doublons | — | 20 |
| Hors région | 0 | 0 |
| Sans commune par inclusion (rattachées à la plus proche) | 0 | 0 |
| Niveaux corrigés par relecture | — | 5 |

**Répartition par type et niveau**

| Type | Niveau | Nombre |
| --- | --- | --- |
| autre | 1 | 62 |
| centre_sante | 1 | 9 |
| clinique | 2 | 85 |
| dentiste | 1 | 61 |
| hopital | 2 | 46 |
| hopital | 3 | 5 |
| medecin | 1 | 58 |
| pharmacie | 1 | 1245 |

**Taux de remplissage des attributs** : `nom` 92 %, `secteur` 1 %, `nb_lits` 0 %, `urgences` 1 %.

## Réseau routier

Format de la couche source : lignes Geofabrik (0 voies non circulables retirées).

| Contrôle | Avant | Après |
| --- | --- | --- |
| Lignes de la source | 130807 | — |
| Tronçons du graphe (après découpe aux croisements) | — | 316012 |
| Nœuds | 228587 | 228054 |
| Boucles (départ = arrivée) | 106 | 0 |
| Tronçons de longueur nulle | 0 | 0 |
| Arêtes parallèles | 1687 | 0 |
| Composantes connexes | 92 | 1 |
| Longueur hors du réseau principal connexe (îlots retirés) | 108 km (0.2 %) | 0 |
| Nœuds orphelins | 533 | 0 |
| Tronçons sans vitesse OSM (vitesse par défaut) | 300117 (94 %) | — |

Longueur totale du graphe : 53 367 km.

| Type de voie | Tronçons | km | Vitesse médiane (km/h) |
| --- | --- | --- | --- |
| track | 79245 | 23544 | 20 |
| unclassified | 30143 | 10069 | 50 |
| residential | 137563 | 8819 | 40 |
| tertiary | 21937 | 4735 | 60 |
| service | 20587 | 1694 | 20 |
| secondary | 9523 | 1470 | 70 |
| primary | 8070 | 1161 | 60 |
| motorway | 538 | 950 | 120 |
| trunk | 3188 | 485 | 80 |
| living_street | 3367 | 171 | 20 |
| motorway_link | 439 | 114 | 50 |
| trunk_link | 333 | 45 | 50 |
| track_grade4 | 155 | 43 | 20 |
| primary_link | 355 | 16 | 50 |
| secondary_link | 293 | 15 | 50 |
| track_grade3 | 33 | 12 | 20 |
| track_grade2 | 7 | 9 | 20 |
| track_grade5 | 7 | 8 | 20 |
| tertiary_link | 224 | 6 | 50 |
| track_grade1 | 5 | 0 | 20 |

Vitesses par défaut appliquées : motorway 120, trunk 100, primary 80, secondary 70, tertiary 60, unclassified 50, residential 40, living_street 20, service 20, road 40, unknown 30, track 20, bretelles 50 km/h. Voies retirées (non circulables en voiture) : bridleway, cycleway, footway, path, pedestrian, steps.

## Grille H3 (résolution 8)

| Contrôle | Valeur |
| --- | --- |
| Hexagones couvrant la région | 25432 |
| Hexagones habités (population > 0) | 7290 |
| Population du raster WorldPop | 7 461 203 |
| Population affectée aux hexagones | 7 461 203 |
| dont hexagones de bordure ajoutés (centre hors région, mais habités) | 177 |
| Écart de population raster / hexagones | -0.00 % |
| Hexagones dont le centre tombe hors de toute commune (commune la plus proche) | 177 |
