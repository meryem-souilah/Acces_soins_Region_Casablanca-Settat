# Rapport de géocodage des établissements de soins de santé primaires

Exécuté le 2026-10-29 17:15 UTC par `scripts/geocodage_essp.py`. Requêtes Nominatim envoyées : 0 (les autres réponses viennent du cache).

## Rattachement aux communes HCP

| Méthode | Établissements |
| --- | --- |
| nom identique | 257 |
| arrondissement de Casablanca | 119 |
| nom proche | 21 |
| correction manuelle | 7 |

## Origine des positions

| precision_geom | Établissements | Signification |
| --- | --- | --- |
| geocodage_etablissement | 66 | Nominatim a trouvé l'établissement lui-même |
| geocodage_lieu | 109 | Nominatim a trouvé le douar ou le quartier qui porte ce nom |
| manuel | 0 | position saisie à la main (corrections/positions_essp.csv) |
| non_trouve | 229 | sans position : à compléter dans corrections/a_positionner_essp.csv |

Établissements de l'analyse encore sans position : 216 (les 31 centres spécialisés et laboratoires ne sont pas listés).

Points à plus de 500 m de leur commune déclarée : 0 (attendu : 0).

Points juste hors de leur commune, dans la bande de tolérance de 500 m : 4. Ils sont acceptés : la limite communale et le géocodage ont chacun une imprécision de quelques centaines de mètres.

| id_source | Nom | Distance à la commune (m) |
| --- | --- | --- |
| msps2022/1576 | MOUALINE EL GHABA | 261.2 |
| msps2022/1688 | Bni Yakhlef | 339.1 |
| msps2022/1690 | S.Moussa Ben Ali | 106.4 |
| msps2022/1797 | Ouled  Hajjaj | 398.1 |

## Par province

| Code | Total | Positionnés |
| --- | --- | --- |
| 06.111 | 27 | 14 |
| 06.117 | 36 | 15 |
| 06.141 | 120 | 47 |
| 06.181 | 44 | 22 |
| 06.355 | 12 | 3 |
| 06.371 | 21 | 8 |
| 06.385 | 22 | 8 |
| 06.461 | 89 | 39 |
| 06.467 | 33 | 19 |

