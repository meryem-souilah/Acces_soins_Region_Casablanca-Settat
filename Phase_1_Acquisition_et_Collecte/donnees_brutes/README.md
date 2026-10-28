# Données brutes — README de provenance

Ce fichier est **généré par `scripts/collecte.py`** à chaque exécution : ne pas le modifier à la main. La version machine est `manifest.json`.

- Projet : Accès aux soins — région Casablanca-Settat
- Dernière collecte : 2026-10-28T19:53:34Z
- CRS de toutes les couches produites : **EPSG:26191** (Merchich / Nord Maroc)
- Rejouer : `python scripts/collecte.py` (cache réutilisé) ou `--force` (tout retélécharger)
- Les fichiers volumineux ne sont pas versionnés (limite GitHub) : leur SHA-256 ci-dessous permet de vérifier qu'un nouveau téléchargement est identique.

## Arborescence

```
donnees_brutes/
├── limites/     overpass_communes.json → limites_casablanca_settat.gpkg (region, communes)
├── osm_sante/   requete.overpassql, overpass_reponse.json → etablissements_sante.gpkg
├── osm_routes/  extrait Geofabrik (morocco-*-free.shp) → routes_casablanca_settat.gpkg
├── worldpop/    raster national → découpes 4326 et 26191
├── hcp/         PDF RGPH 2024 → pages et lignes de la région (code 06…)
├── manifest.json
└── README.md
```

## Limites administratives — communes (admin_level 8) et contour régional

- **producteur** : Contributeurs OpenStreetMap (codes géographiques HCP : ref:MA:HCP)
- **url** : https://overpass.kumi.systems/api/interpreter
- **mode** : automatique (API Overpass) — cache local réutilisé
- **licence** : ODbL 1.0 — © contributeurs OpenStreetMap (codes communaux HCP)
- **date telechargement** : 2026-10-21T21:09:56Z
- **date collecte** : 2026-10-28T19:43:16Z
- **crs origine** : EPSG:4326
- **crs sortie** : EPSG:26191
- **avertissement** : Le jeu COD-AB d'OCHA/HDX pour le Maroc s'arrête aux provinces (admin2) : les communes viennent d'OSM, jointes au HCP par leur code.
- date donnees osm : 2026-10-28T19:39:47Z
- nb communes : 153
- provinces retenues : ['06.111', '06.117', '06.141', '06.181', '06.355', '06.371', '06.385', '06.461', '06.467']
- surface region km2 : 20207.3
- emprise 26191 : [156993, 192915, 373437, 360575]

| Fichier | Rôle | Taille (Mo) | SHA-256 |
| --- | --- | --- | --- |
| `donnees_brutes/limites/overpass_communes.json` | origine | 1.47 | `f38e30f3d5c46e9e…` |
| `donnees_brutes/limites/limites_casablanca_settat.gpkg` | produit | 1.02 | `c4a870a1285a51fe…` |

## Établissements de santé (hôpitaux, cliniques, médecins, dentistes, pharmacies)

- **producteur** : Contributeurs OpenStreetMap
- **url** : https://overpass-api.de/api/interpreter
- **mode** : automatique (API Overpass)
- **licence** : ODbL 1.0 — © contributeurs OpenStreetMap
- **date telechargement** : 2026-10-28T19:44:03Z
- **date collecte** : 2026-10-28T19:44:03Z
- **crs origine** : EPSG:4326
- **crs sortie** : EPSG:26191
- date donnees osm : 2026-10-28T19:42:49Z
- nb entites rectangle : 1737
- nb entites region : 1591
- repartition : {'pharmacy': 1259, 'hospital': 83, 'clinic': 74, 'doctors': 71, 'dentist': 58, 'healthcare=laboratory': 23, 'healthcare=yes': 6, 'healthcare=physiotherapist': 4, 'healthcare=counselling': 2, 'healthcare=pharmacy': 1}
- sans nom pct : 8.7

| Fichier | Rôle | Taille (Mo) | SHA-256 |
| --- | --- | --- | --- |
| `donnees_brutes/osm_sante/overpass_reponse.json` | origine | 0.51 | `f5d42056cca444f5…` |
| `donnees_brutes/osm_sante/etablissements_sante.gpkg` | produit | 0.37 | `87d022bfbce9da50…` |

## Réseau routier circulable (niveau « complet »)

- **producteur** : Contributeurs OpenStreetMap, extrait Geofabrik
- **url** : https://download.geofabrik.de/africa/morocco-latest-free.shp.zip
- **mode** : automatique (extrait Geofabrik) — cache local réutilisé
- **licence** : ODbL 1.0 — © contributeurs OpenStreetMap
- **date telechargement** : 2026-10-28T19:49:25Z
- **date collecte** : 2026-10-28T19:53:34Z
- **crs origine** : EPSG:4326
- **crs sortie** : EPSG:26191
- **avertissement** : Tronçons découpés au contour régional, non topologisés : le graphe (nœuds aux intersections, ponts et tunnels via « layer ») se construit au pré-traitement (intersession 3).
- date donnees osm : 2026-10-27T21:23:59Z
- nb troncons : 130783
- longueur km : 53907
- types voies : {'residential': 53065, 'track': 44539, 'service': 12367, 'unclassified': 6191, 'tertiary': 4403, 'secondary': 2662, 'primary': 2521, 'living_street': 1964, 'trunk': 1113, 'motorway': 386}

| Fichier | Rôle | Taille (Mo) | SHA-256 |
| --- | --- | --- | --- |
| `donnees_brutes/osm_routes/morocco-261014-free.shp/gis_osm_roads_free_1.shp` | origine | 344.02 | `2aa0ced7952cec3a…` |
| `donnees_brutes/osm_routes/routes_casablanca_settat.gpkg` | produit | 57.26 | `29aa13dc6e12391f…` |

## Population maillée 100 m, 2020, version « constrained »

- **producteur** : WorldPop (University of Southampton)
- **url** : https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/MAR/mar_ppp_2020_constrained.tif
- **mode** : automatique — cache local réutilisé
- **licence** : CC BY 4.0 — WorldPop (Univ. of Southampton)
- **date telechargement** : 2026-10-28T19:02:43Z
- **date collecte** : 2026-10-28T19:44:05Z
- **crs origine** : EPSG:4326
- **crs sortie** : EPSG:26191 (copie EPSG:4326 conservée)
- population region 4326 : 7461204
- population region 26191 : 7461202
- ecart reprojection pct : -0.0

| Fichier | Rôle | Taille (Mo) | SHA-256 |
| --- | --- | --- | --- |
| `donnees_brutes/worldpop/mar_ppp_2020_constrained.tif` | origine | 1.19 | `0f3bbb317fb16c0a…` |
| `donnees_brutes/worldpop/worldpop_2020_casablanca_settat_4326.tif` | produit | 0.65 | `f8b4cfdd241eae5f…` |
| `donnees_brutes/worldpop/worldpop_2020_casablanca_settat_26191.tif` | produit | 0.69 | `e4e29b2eda9c049b…` |

## Population légale RGPH 2024 (régions, provinces, communes)

- **producteur** : Haut-Commissariat au Plan (HCP)
- **url** : https://www.hcp.ma/file/242342/
- **mode** : automatique — cache local réutilisé
- **licence** : HCP — publication officielle, réutilisation avec citation de la source
- **date telechargement** : 2026-10-21T21:11:25Z
- **date collecte** : 2026-10-22T14:45:55Z
- **crs origine** : sans objet (tableau)
- **crs sortie** : sans objet
- **avertissement** : Import brut (nombres au format texte « 1,234 ») : la conversion et la jointure aux communes relèvent du pré-traitement (intersession 3).
- nb pages pdf : 138
- pages region : [1, 2, 3, 6, 11, 16, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89]
- lignes tableaux brutes : 255
- nb lignes communes : 153

| Fichier | Rôle | Taille (Mo) | SHA-256 |
| --- | --- | --- | --- |
| `donnees_brutes/hcp/population_legale_rgph2024.pdf` | origine | 2.27 | `66149a1281afcdc2…` |
| `donnees_brutes/hcp/pages_region_casablanca_settat.txt` | produit | 0.04 | `b42779b6b831a96b…` |
| `donnees_brutes/hcp/tableaux_bruts_region.csv` | produit | 0.03 | `0cb5658b27c2c784…` |
