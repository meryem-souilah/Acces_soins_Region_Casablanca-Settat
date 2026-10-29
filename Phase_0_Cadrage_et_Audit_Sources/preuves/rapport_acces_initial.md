# Rapport de preuve d'accès aux données

Exécuté le **2026-10-15 17:55:39 UTC** — Python 3.11.17 — emprise {'sud': 31.9, 'ouest': -9.4, 'nord': 33.95, 'est': -6.4}

| Source | Statut | Durée | Résultat clé |
|---|---|---|---|
| OpenStreetMap — établissements de santé (API Overpass) | ✅ OK | 14.9 s | 2360 |
| routes | ❌ ÉCHEC | 53.5 s | ResponseStatusCodeError: 'overpass-api.de' responded: 502 Bad Gateway # 502 Gateway Timeou |
| WorldPop 2020 constrained, 100 m (Maroc) — découpé sur l'emprise | ✅ OK | 7.1 s | 11210888 |
| limites | ❌ ÉCHEC | 0.6 s | RuntimeError: Téléchargement automatique impossible (404 Client Error: Not Found for url:  |
| hcp | ❌ ÉCHEC | 1.0 s | RuntimeError: Le fichier reçu n'est pas un PDF (page HTML ?) — téléchargez-le à la main et |

## osm

- **source** : OpenStreetMap — établissements de santé (API Overpass)
- **url** : https://overpass.kumi.systems/api/interpreter
- **licence** : ODbL 1.0 — © contributeurs OpenStreetMap
- **fichier** : osm_sante_echantillon.geojson
- **taille_mo** : 0.59
- **sha256** : 2f2c22fcac7edcffc7d899b6ea3add1eca98a1d0683289b2a0f6bcfacff91d91
- **crs** : EPSG:4326
- **nb_entites** : 2360
- **repartition** : {'pharmacy': 1971, 'hospital': 126, 'clinic': 77, 'doctors': 77, 'dentist': 62, 'laboratory': 28, 'yes': 6, 'physiotherapist': 4}
- **sans_nom_pct** : 6.3
- **date_osm** : 2026-07-24T11:04:51Z

## routes

- **Erreur** : ResponseStatusCodeError: 'overpass-api.de' responded: 502 Bad Gateway # 502 Gateway Timeout

This Overpass API server is currently at capacity. All query workers are busy
and the request queue is full.

## What to do

Retry your request using exponential backoff: wait a short interval, then retry.
If the request fails again, double the wait time and retry again.

## For heavy or automated use

This public endpoint is intended for browser-based and human-operated tools.
For automated or high-volume use, run a local Overpass API instance:

https://github.com/b1tw153/Overpass-API/blob/main/README.md


## worldpop

- **source** : WorldPop 2020 constrained, 100 m (Maroc) — découpé sur l'emprise
- **url** : https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/MAR/mar_ppp_2020_constrained.tif
- **licence** : CC BY 4.0 — WorldPop (Univ. of Southampton)
- **fichier** : worldpop_casablanca_settat.tif
- **taille_mo** : 1.19
- **sha256** : 0f3bbb317fb16c0a3ae710c6a8f2e9d8520e7c77f0ba0f49a80906688487cb8d
- **crs** : GEOGCS["WGS 84",DATUM["World Geodetic System 1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AXIS["Latitude",NORTH],AXIS["Longitude",EAST]]
- **resolution_deg** : [0.000833, 0.000833]
- **dimensions_px** : [2460, 3600]
- **pixels_habites** : 231583
- **population_rectangle** : 11210888
- **remarque** : Total sur le RECTANGLE englobant (déborde de la région) : le total régional exact sera calculé après découpage par le polygone HCP.

## limites

- **Erreur** : RuntimeError: Téléchargement automatique impossible (404 Client Error: Not Found for url: https://data.humdata.org/api/3/action/package_show?id=morocco-administrative-boundaries-populated-places). Téléchargez le fichier *_SHP.zip à la main depuis https://data.humdata.org/dataset/morocco-administrative-boundaries-populated-places puis relancez avec --limites-zip CHEMIN

## hcp

- **Erreur** : RuntimeError: Le fichier reçu n'est pas un PDF (page HTML ?) — téléchargez-le à la main et utilisez --hcp-pdf
