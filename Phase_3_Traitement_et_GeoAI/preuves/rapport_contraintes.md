# Rapport — critères de localisation du référentiel

Exécuté le 2026-11-18 20:10 UTC par `scripts/02_contraintes_localisation.py` (35 s). Couches en EPSG:26191.

Règles : référentiel EPPIG 2016, p. 39 (« Critères de localisation des équipements de santé »). Le référentiel ne chiffre aucune distance : **100 m** d'éloignement des nuisances et **2 km** pour la proximité des grands axes sont des hypothèses de travail.

## Overlays (PostGIS)

`ST_Buffer` (distance de la règle) → `ST_Union` par catégorie → `ST_Intersection` avec la région : table `contrainte_localisation`. Puis, pour chaque hexagone, `ST_Intersection` / `ST_Area` avec les zones : table `aptitude_h3`.

| Catégorie | Règle du référentiel | Équipements | Effet | Distance | Objets OSM | Surface |
| --- | --- | --- | --- | --- | --- | --- |
| decharge | éviter les décharges de déchets | CSU, hôpitaux | exclure | 100 m | 10 | 2 km² |
| grand_axe_nuisance | éviter les grands axes routiers (bruit, pollution) | CSU, hôpital de proximité | exclure | 100 m | 2522 | 159 km² |
| industrie | éviter usines, zones et unités industrielles | CSU, hôpitaux | exclure | 100 m | 1593 | 168 km² |
| station_service | éviter les stations d'essence | CSU, hôpitaux | exclure | 100 m | 788 | 16 km² |
| voie_ferree | éviter les lignes de chemins de fer | CSU, hôpitaux | exclure | 100 m | 1364 | 85 km² |
| zone_residentielle | éviter la proximité avec les zones résidentielles | hôpitaux provinciaux et régionaux | exclure | 0 m | 10771 | 235 km² |
| grand_axe_acces | implantation encouragée à proximité des grands axes de circulation et d'évacuation | hôpitaux provinciaux et régionaux | favoriser | 2000 m | 5647 | 4 762 km² |

**Non disponibles** (absents de l'extrait OSM Geofabrik) : lignes à haute tension, zones inondables. La proximité « encouragée » des espaces verts n'est pas utilisée (critère de confort, pas d'exclusion).

## Aptitude des hexagones

- **apte CSU** : moins de 50% de l'hexagone en zone de nuisance (voies ferrées, industrie, décharges, stations-service, grands axes) ;
- **apte hôpital** : à moins de 2 km d'une autoroute, voie express ou route principale, moins de 50% en zone de nuisance et moins de 50% en zone résidentielle.

|  | Hexagones habités | Population 2024 |
| --- | --- | --- |
| total | 7290 | 7 688 968 |
| apte CSU | 7042 | 6 428 364 |
| apte hôpital | 3034 | 4 453 742 |

Ces couches serviront à écarter les sites candidats non conformes au référentiel (étape d'implantation) et de variables de contexte pour le modèle.

Carte : `preuves/carte_contraintes.png`.
