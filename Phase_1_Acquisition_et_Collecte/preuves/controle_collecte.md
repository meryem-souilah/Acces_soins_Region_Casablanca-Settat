# Contrôle du jeu de données brut

Exécuté le 2026-10-22 14:40 UTC par `scripts/controle_collecte.py`.

**CRS uniforme : oui** — CRS rencontrés : EPSG:26191 (attendu : EPSG:26191).

Surface de la région : 20 207 km².

| Couche | CRS | Entités | Géométries invalides | Hors région | Type | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Contour régional | EPSG:26191 | 1 | 0 | 0 | MultiPolygon | ✅ |
| Communes (OSM, codes HCP) | EPSG:26191 | 153 | 0 | 0 | MultiPolygon | ✅ |
| Établissements de santé | EPSG:26191 | 1 588 | 0 | 0 | Point | ✅ |
| Réseau routier (tronçons) | EPSG:26191 | 130 813 | 0 | 0 | LineString | ✅ |
| Population WorldPop 100 m (raster) | EPSG:26191 | 2186×1753 px | — | — | total 7 466 216 hab. | ✅ écart +0.00 % vs 4326 |

Jointure communes ↔ population légale HCP 2024 (code géographique) : **153 / 153** communes de la carte appariées, 153 communes dans le tableau HCP — ✅

Les géométries invalides ne sont pas corrigées à ce stade : la correction tracée (`ST_MakeValid`, rapport avant/après) relève de l'intersession 3.
