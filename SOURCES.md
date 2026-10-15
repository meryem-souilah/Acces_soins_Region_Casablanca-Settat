# SOURCES.md — Inventaire des sources de données

Toutes les données sont téléchargées dans `donnees_brutes/` (non versionné sur
GitHub en raison de leur taille). Les preuves d'accès (captures des pages de
téléchargement et de QGIS) sont dans `preuves/captures/`, et deux échantillons
réels sont versionnés dans `preuves/`.

> Dates au format AAAA-MM-JJ. Mettre à jour la date si une source est
> retéléchargée.

| # | Donnée | Producteur / diffuseur | Lien de téléchargement | Fichier | Format | CRS d'origine | Licence | Date de téléchargement | Dossier local |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Établissements de santé (`amenity=hospital/clinic/doctors/dentist/pharmacy`, `healthcare=*`) | Contributeurs OpenStreetMap | [overpass-turbo.eu](https://overpass-turbo.eu), requête `preuves/osm_requete.overpassql` | `osm_sante.geojson` | GeoJSON | EPSG:4326 | ODbL 1.0 | 2026-10-15 | `donnees_brutes/osm_sante/` |
| 2 | Réseau routier | Contributeurs OpenStreetMap, extrait Geofabrik | [download.geofabrik.de/africa/morocco.html](https://download.geofabrik.de/africa/morocco.html) | `morocco-latest-free.shp.zip` → `gis_osm_roads_free_1.*` | Shapefile | EPSG:4326 | ODbL 1.0 | 2026-10-15 | `donnees_brutes/osm_routes/` |
| 3 | Population maillée 100 m, 2020, *constrained* | WorldPop (Univ. of Southampton) | [mar_ppp_2020_constrained.tif](https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/MAR/mar_ppp_2020_constrained.tif) | `mar_ppp_2020_constrained.tif` | GeoTIFF | EPSG:4326 | CC BY 4.0 | 2026-10-15 | `donnees_brutes/worldpop/` |
| 4 | Limites administratives niveaux 0 à 4 (communes = adm3) | HCP, redistribué par OCHA (COD-AB) | [data.humdata.org — Morocco Subnational Administrative Boundaries](https://data.humdata.org/dataset/morocco-administrative-boundaries-populated-places) | `mar_admbnda_hcp_20230925_SHP.zip` | Shapefile | EPSG:4326 (à confirmer dans QGIS) | CC BY for Intergovernmental Organisations | 2026-10-15 | `donnees_brutes/limites_hcp/` |
| 5 | Population légale RGPH 2024 par commune | Haut-Commissariat au Plan | [hcp.ma — Population légale par régions, provinces et communes](https://www.hcp.ma/Population-legale-du-Royaume-du-Maroc-repartie-par-regions-provinces-et-prefectures-et-communes-selon-les-resultats-du_a3974.html) | PDF de la population légale | PDF (tableaux) | sans objet | Publication officielle, réutilisation avec citation de la source | 2026-10-15 | `donnees_brutes/rgph2024/` |

## Détails par source

**1. Établissements de santé (OSM).** Échantillon réel versionné :
`preuves/osm_sante_echantillon.geojson` (2 360 entités : 1 971 pharmacies,
126 hôpitaux, 77 cliniques, 77 cabinets médicaux, 62 dentistes, autres).
Date des données OSM la plus récente : 2026-07-24. 6,3 % des entités n'ont pas
de nom.

**2. Réseau routier (Geofabrik).** Extrait OSM de tout le Maroc mis à jour
quotidiennement (données au 2026-10-14). Seule la couche `gis_osm_roads_free_1`
est utilisée. Choisi à la place de l'API Overpass, saturée lors de nos tests
(erreur 502).

**3. WorldPop.** Résolution 0,000833° (environ 100 m). Échantillon découpé sur
l'emprise versionné : `preuves/worldpop_casablanca_settat.tif`.

**4. Limites administratives.** Version du 2023-09-25. Le polygone de la région
Casablanca-Settat (niveau adm1) sert au découpage de toutes les autres couches.

**5. RGPH 2024.** Les tableaux du PDF seront extraits et joints aux communes de
la source 4 (jointure par nom ou code de commune, à vérifier).

## Emprise

Région Casablanca-Settat. Les données sont d'abord sélectionnées sur le
rectangle englobant `sud 31.90, ouest -9.40, nord 33.95, est -6.40` (WGS84),
puis découpées par le polygone régional issu de la source 4.

CRS de calcul (distances, surfaces) : **EPSG:26191** (Merchich / Nord Maroc).

## Limites connues

- **Décalage temporel** : WorldPop date de 2020, le RGPH de 2024. Les effectifs
  RGPH 2024 serviront à recaler la population WorldPop par commune.
- **Complétude d'OSM** : forte proportion de pharmacies par rapport aux
  hôpitaux ; la couverture des établissements publics reste à vérifier.
- **Emprise** : le rectangle englobant déborde de la région ; le découpage par
  le polygone HCP est indispensable avant tout calcul.
