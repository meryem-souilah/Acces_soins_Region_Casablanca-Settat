# SOURCES.md — Inventaire des sources

Généré par `scripts/collecte.py` à partir de `donnees_brutes/manifest.json` : ne pas modifier à la main. Les empreintes SHA-256 des fichiers sont dans `donnees_brutes/README.md`.

- **Zone d'étude** : région Casablanca-Settat (code géographique HCP 06), contour = union des communes, 20 207 km²
- **CRS de toutes les couches produites** : EPSG:26191 (Merchich / Nord Maroc, en mètres)
- **Emprise** : rectangle englobant de chaque couche produite, mesuré sur le fichier (xmin, ymin, xmax, ymax)
- **Dernière collecte** : 2026-10-28T19:53:34Z
- **Rejouer** : `python scripts/collecte.py` puis `python scripts/controle_collecte.py`

## Synthèse

| # | Donnée | Producteur | Licence | Millésime | Téléchargée le | CRS origine → produit | Emprise (km) | Volume |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Limites administratives — communes (admin_level 8) et contour régional | Contributeurs OpenStreetMap (codes géographiques HCP : ref:MA:HCP) | ODbL 1.0 — © contributeurs OpenStreetMap (codes communaux HCP) | OSM au 2026-10-28 | 2026-10-21 | EPSG:4326 → EPSG:26191 | 216 × 168 | 153 communes, 9 provinces/préfectures |
| 2 | Établissements de santé (hôpitaux, cliniques, médecins, dentistes, pharmacies) | Contributeurs OpenStreetMap | ODbL 1.0 — © contributeurs OpenStreetMap | OSM au 2026-10-28 | 2026-10-28 | EPSG:4326 → EPSG:26191 | 182 × 156 | 1 591 établissements |
| 3 | Réseau routier circulable (niveau « complet ») | Contributeurs OpenStreetMap, extrait Geofabrik | ODbL 1.0 — © contributeurs OpenStreetMap | OSM au 2026-10-27 | 2026-10-28 | EPSG:4326 → EPSG:26191 | 213 × 166 | 130 783 tronçons, 53 907 km |
| 4 | Population maillée 100 m, 2020, version « constrained » | WorldPop (University of Southampton) | CC BY 4.0 — WorldPop (Univ. of Southampton) | 2020 (estimation modélisée WorldPop) | 2026-10-28 | EPSG:4326 → EPSG:26191 (copie EPSG:4326 conservée) | 219 × 175 | 7 461 202 hab. (pixels de 100 m) |
| 5 | Population légale RGPH 2024 (régions, provinces, communes) | Haut-Commissariat au Plan (HCP) | HCP — publication officielle, réutilisation avec citation de la source | RGPH 2024 (population au 1er septembre 2024, décret n° 2.24.1009) | 2026-10-21 | sans objet (tableau) → sans objet | région (tableau) | 255 lignes, dont 153 communes |

## Détail par source

### 1. Limites administratives — communes (admin_level 8) et contour régional

- **URL** : https://overpass.kumi.systems/api/interpreter
- **Mode d'acquisition** : automatique (API Overpass) — cache local réutilisé
- **Producteur** : Contributeurs OpenStreetMap (codes géographiques HCP : ref:MA:HCP)
- **Licence** : ODbL 1.0 — © contributeurs OpenStreetMap (codes communaux HCP)
- **Millésime des données** : OSM au 2026-10-28
- **Téléchargée le** : 2026-10-21T21:09:56Z — **collectée le** : 2026-10-28T19:43:16Z
- **CRS** : origine EPSG:4326 → produit EPSG:26191
- **Emprise** : EPSG:26191 : 156 993, 192 915, 373 437, 360 575 m — EPSG:4326 : -9.1041, 32.2775, -6.7429, 33.8363 (ouest, sud, est, nord)
- **Volume** : 153 communes, 9 provinces/préfectures
- **Sélection** : donnees_brutes/limites/requete_communes.overpassql
- **Fichiers produits** : `donnees_brutes/limites/limites_casablanca_settat.gpkg`
- **Remarque** : Le jeu COD-AB d'OCHA/HDX pour le Maroc s'arrête aux provinces (admin2) : les communes viennent d'OSM, jointes au HCP par leur code.

### 2. Établissements de santé (hôpitaux, cliniques, médecins, dentistes, pharmacies)

- **URL** : https://overpass-api.de/api/interpreter
- **Mode d'acquisition** : automatique (API Overpass)
- **Producteur** : Contributeurs OpenStreetMap
- **Licence** : ODbL 1.0 — © contributeurs OpenStreetMap
- **Millésime des données** : OSM au 2026-10-28
- **Téléchargée le** : 2026-10-28T19:44:03Z — **collectée le** : 2026-10-28T19:44:03Z
- **CRS** : origine EPSG:4326 → produit EPSG:26191
- **Emprise** : EPSG:26191 : 158 964, 202 151, 341 165, 358 132 m — EPSG:4326 : -9.0819, 32.3614, -7.0873, 33.8099 (ouest, sud, est, nord)
- **Volume** : 1 591 établissements
- **Sélection** : donnees_brutes/osm_sante/requete.overpassql
- **Fichiers produits** : `donnees_brutes/osm_sante/etablissements_sante.gpkg`

### 3. Réseau routier circulable (niveau « complet »)

- **URL** : https://download.geofabrik.de/africa/morocco-latest-free.shp.zip
- **Mode d'acquisition** : automatique (extrait Geofabrik) — cache local réutilisé
- **Producteur** : Contributeurs OpenStreetMap, extrait Geofabrik
- **Licence** : ODbL 1.0 — © contributeurs OpenStreetMap
- **Millésime des données** : OSM au 2026-10-27
- **Téléchargée le** : 2026-10-28T19:49:25Z — **collectée le** : 2026-10-28T19:53:34Z
- **CRS** : origine EPSG:4326 → produit EPSG:26191
- **Emprise** : EPSG:26191 : 157 566, 194 144, 371 005, 360 274 m — EPSG:4326 : -9.0978, 32.2888, -6.7689, 33.8332 (ouest, sud, est, nord)
- **Volume** : 130 783 tronçons, 53 907 km
- **Sélection** : fclass ∈ motorway, motorway_link, trunk, trunk_link, primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, unclassified, residential, living_street, service, track, track_grade1, track_grade2, track_grade3, track_grade4, track_grade5
- **Fichiers produits** : `donnees_brutes/osm_routes/routes_casablanca_settat.gpkg`
- **Remarque** : Tronçons découpés au contour régional, non topologisés : le graphe (nœuds aux intersections, ponts et tunnels via « layer ») se construit au pré-traitement (intersession 3).

### 4. Population maillée 100 m, 2020, version « constrained »

- **URL** : https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/MAR/mar_ppp_2020_constrained.tif
- **Mode d'acquisition** : automatique — cache local réutilisé
- **Producteur** : WorldPop (University of Southampton)
- **Licence** : CC BY 4.0 — WorldPop (Univ. of Southampton)
- **Millésime des données** : 2020 (estimation modélisée WorldPop)
- **Téléchargée le** : 2026-10-28T19:02:43Z — **collectée le** : 2026-10-28T19:44:05Z
- **CRS** : origine EPSG:4326 → produit EPSG:26191 (copie EPSG:4326 conservée)
- **Emprise** : EPSG:26191 : 155 276, 190 070, 373 976, 365 270 m — EPSG:4326 : -9.1244, 32.2513, -6.7368, 33.8787 (ouest, sud, est, nord)
- **Volume** : 7 461 202 hab. (pixels de 100 m)
- **Fichiers produits** : `donnees_brutes/worldpop/worldpop_2020_casablanca_settat_4326.tif`, `donnees_brutes/worldpop/worldpop_2020_casablanca_settat_26191.tif`

### 5. Population légale RGPH 2024 (régions, provinces, communes)

- **URL** : https://www.hcp.ma/file/242342/
- **Mode d'acquisition** : automatique — cache local réutilisé
- **Producteur** : Haut-Commissariat au Plan (HCP)
- **Licence** : HCP — publication officielle, réutilisation avec citation de la source
- **Millésime des données** : RGPH 2024 (population au 1er septembre 2024, décret n° 2.24.1009)
- **Téléchargée le** : 2026-10-21T21:11:25Z — **collectée le** : 2026-10-22T14:45:55Z
- **CRS** : origine sans objet (tableau) → produit sans objet
- **Emprise** : tableau sans géométrie, limité à la région (codes 06…) ; il prend l'emprise des communes par jointure sur le code géographique
- **Volume** : 255 lignes, dont 153 communes
- **Fichiers produits** : `donnees_brutes/hcp/pages_region_casablanca_settat.txt`, `donnees_brutes/hcp/tableaux_bruts_region.csv`
- **Remarque** : Import brut (nombres au format texte « 1,234 ») : la conversion et la jointure aux communes relèvent du pré-traitement (intersession 3).
