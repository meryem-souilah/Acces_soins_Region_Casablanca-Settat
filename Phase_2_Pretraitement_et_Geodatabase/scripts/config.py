"""
Configuration commune du projet « Accès aux soins — Casablanca-Settat ».

Toutes les URL, emprises et chemins sont centralisés ici :
un seul endroit à modifier si une source change d'adresse.
"""
import os
import sys
from pathlib import Path

# ── PROJ / GDAL : utiliser ceux de l'environnement conda ─────────────────────
# Sous Windows, l'installeur PostgreSQL/PostGIS définit PROJ_LIB vers sa propre
# base proj.db, plus ancienne : GDAL/rasterio échoue alors avec « The EPSG code
# is unknown … DATABASE.LAYOUT.VERSION.MINOR ». On force les données de l'env
# (paquets conda) ; à défaut on retire la variable étrangère, et les wheels pip
# (rasterio, pyogrio, pyproj) reprennent alors leur propre proj.db embarqué.
# sys.prefix couvre le cas où python.exe de l'env est lancé sans « conda activate ».
_prefixe = os.environ.get("CONDA_PREFIX") or sys.prefix
for _var, _sous in (("PROJ_DATA", ("Library", "share", "proj")),
                    ("PROJ_LIB", ("Library", "share", "proj")),
                    ("GDAL_DATA", ("Library", "share", "gdal"))):
    _cand = next((c for c in (Path(_prefixe, *_sous), Path(_prefixe, "share", _sous[-1]))
                  if c.exists()), None)
    if _cand is not None:
        os.environ[_var] = str(_cand)
    elif not str(Path(os.environ.get(_var, _prefixe))).lower().startswith(_prefixe.lower()):
        del os.environ[_var]

# ── Racine de la Phase 2 et lien vers donnees_brutes de la Phase 1 ───────────
RACINE = Path(__file__).resolve().parent.parent
DONNEES_BRUTES = RACINE.parent / "Phase_1_Acquisition_et_Collecte" / "donnees_brutes"
PREUVES = RACINE / "preuves"

# ── Emprise d'étude ──────────────────────────────────────────────────────────
# Rectangle englobant (large) de la région Casablanca-Settat, en WGS84.
# Il sert aux requêtes ; le découpage exact se fait ensuite avec le polygone
# régional (union des communes de la région).
BBOX = {"sud": 31.90, "ouest": -9.40, "nord": 33.95, "est": -6.40}

# CRS
CRS_GEO = "EPSG:4326"              # stockage / échange
CRS_METRIQUE = "EPSG:26191"        # Merchich / Nord Maroc (calculs de distances)

# Zone de démonstration (petit extrait du réseau routier, rapide en séance)
DEMO_ROUTES_CENTRE = (33.2655, -7.5875)   # (lat, lon) — centre de Berrechid
DEMO_ROUTES_RAYON_M = 3000

# ── Sources ──────────────────────────────────────────────────────────────────
# Ordre d'essai des serveurs Overpass : le serveur principal (overpass-api.de)
# est souvent saturé (erreur 502), on commence donc par un miroir.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

WORLDPOP_URLS = [
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/"
    "2020/BSGM/MAR/mar_ppp_2020_constrained.tif",
    "https://worldpop-public-data.soton.ac.uk/GIS/Population/"
    "Global_2000_2020_Constrained/2020/BSGM/MAR/mar_ppp_2020_constrained.tif",
]

# Limites communales : OpenStreetMap (admin_level=8), chaque commune porte son
# code géographique HCP (ref:MA:HCP), le même que dans le tableau de population
# légale. Le jeu COD-AB d'OCHA/HDX (cod-ab-mar) s'arrête aux provinces (admin2)
# et ne contient donc pas les communes.
CODE_HCP_REGION = "06"             # Casablanca-Settat (ref=6 sur la relation OSM)
ADMIN_LEVEL_COMMUNES = "8"

# Population légale RGPH 2024 par commune (décret n° 2.24.1009, publication HCP).
# file/242342 = tableaux par région, province et commune (PDF, 138 p.) ;
# file/242227 n'est que la note de synthèse (.docx), sans tableau communal.
HCP_POP_LEGALE_URL = "https://www.hcp.ma/file/242342/"
HCP_POP_LEGALE_PAGE = ("https://www.hcp.ma/Population-legale-du-Royaume-du-Maroc-repartie-par-"
                       "regions-provinces-et-prefectures-et-communes-selon-les-resultats-du_a3974.html")
HCP_RGPH_PLATEFORME = "https://resultats2024.rgphapps.ma"

# Réseau routier : extrait OSM quotidien de Geofabrik (une requête au lieu
# d'une centaine de tuiles Overpass)
GEOFABRIK_MAROC = "https://download.geofabrik.de/africa/morocco-latest-free.shp.zip"
GEOFABRIK_COUCHE_ROUTES = "gis_osm_roads_free_1.shp"
# Classes OSM circulables en voiture ; les pistes (track*) sont gardées car
# elles desservent une partie des douars ruraux. Exclus : chemins, escaliers…
ROUTES_FCLASS = [
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "living_street", "service", "track", "track_grade1", "track_grade2",
    "track_grade3", "track_grade4", "track_grade5",
]

USER_AGENT = "AccesSoinsCasablancaSettat/1.0 (https://github.com/meryem-souilah/Acces_soins_Region_Casablanca-Settat)"

# Secours automatique pour le contour régional (OSM via geoBoundaries, ODbL)
GEOBOUNDARIES_ADM1 = ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
                      "releaseData/gbOpen/MAR/ADM1/geoBoundaries-MAR-ADM1.geojson")

# Réseau routier : niveaux de détail (sous-ensembles de ROUTES_FCLASS)
ROUTES_FILTRES = {
    "complet": ROUTES_FCLASS,
    "principal": [f for f in ROUTES_FCLASS
                  if f not in ("residential", "living_street", "service") and not f.startswith("track")],
}

# Le site du HCP renvoie parfois une page web aux clients non navigateurs
EN_TETES_NAVIGATEUR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/128.0",
    "Accept": "application/pdf,*/*;q=0.8",
}


# Licences déclarées (reprises dans SOURCES.md et le rapport de preuve)
LICENCES = {
    "osm": "ODbL 1.0 — © contributeurs OpenStreetMap",
    "worldpop": "CC BY 4.0 — WorldPop (Univ. of Southampton)",
    "limites": "ODbL 1.0 — © contributeurs OpenStreetMap (codes communaux HCP)",
    "hcp_pop": "HCP — publication officielle, réutilisation avec citation de la source",
    "geoboundaries": "ODbL 1.0 — geoBoundaries (données OpenStreetMap)",
}
