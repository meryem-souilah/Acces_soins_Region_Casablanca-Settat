# SOURCES.md — Inventaire des sources de données

> Les colonnes « Date de téléchargement » et « SHA-256 » se recopient depuis
> `preuves/rapport_acces.md` après exécution de `scripts/00_test_acces.py`.

| # | Donnée | Producteur / diffuseur | Accès | Format | CRS d'origine | Licence | Date de téléchargement | SHA-256 (échantillon) |
|---|---|---|---|---|---|---|---|---|
| 1 | Établissements de santé (`amenity=hospital/clinic/doctors/dentist/pharmacy`, `healthcare=*`) | Contributeurs OpenStreetMap | API Overpass — `overpass-api.de` (miroir `overpass.kumi.systems`) | JSON → GeoJSON | EPSG:4326 | ODbL 1.0 | _à compléter_ | _à compléter_ |
| 2 | Réseau routier (`network_type="drive"`) | Contributeurs OpenStreetMap | osmnx (Overpass) | GeoPackage | EPSG:4326 | ODbL 1.0 | _à compléter_ | _à compléter_ |
| 3 | Population maillée 100 m, 2020, *constrained* | WorldPop (Univ. of Southampton) | `data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/MAR/` | GeoTIFF | EPSG:4326 | CC BY 4.0 | _à compléter_ | _à compléter_ |
| 4 | Limites administratives niveaux 0-4 (communes = ADM3) | HCP, redistribué par OCHA (COD-AB) | data.humdata.org — `mar_admbnda_hcp_20230925_SHP.zip` | Shapefile | _à vérifier_ | voir page HDX | _à compléter_ | _à compléter_ |
| 5 | Population légale RGPH 2024 par commune | Haut-Commissariat au Plan | hcp.ma (PDF) ; plateforme resultats2024.rgphapps.ma | PDF (tableaux) | sans objet | publication officielle, citation de la source | _à compléter_ | _à compléter_ |

## Emprise

Région Casablanca-Settat. Requêtes sur le rectangle englobant
`sud 31.90, ouest -9.40, nord 33.95, est -6.40` (WGS84), puis découpage par le
polygone régional issu de la source 4.

## Projet de référence (inspiration, non réutilisé tel quel)

`github.com/marouane-ouaomar/morocco-healthcare-optimization` (licence MIT) :
même problématique à l'échelle nationale. Audit : grille de population synthétique
par défaut, distances euclidiennes, pas de géodatabase ni d'évaluation du modèle.
