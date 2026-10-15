"""
Configuration commune du projet « Accès aux soins — Casablanca-Settat ».

Toutes les URL, emprises et chemins sont centralisés ici :
un seul endroit à modifier si une source change d'adresse.
"""
from pathlib import Path

# ── Racine du projet (dossier parent de scripts/) ────────────────────────────
RACINE = Path(__file__).resolve().parent.parent
DONNEES_BRUTES = RACINE / "donnees_brutes"
PREUVES = RACINE / "preuves"

# ── Emprise d'étude ──────────────────────────────────────────────────────────
# Rectangle englobant (large) de la région Casablanca-Settat, en WGS84.
# Il sert aux requêtes ; le découpage exact se fait ensuite avec le polygone
# régional issu des limites HCP.
BBOX = {"sud": 31.90, "ouest": -9.40, "nord": 33.95, "est": -6.40}
NOM_REGION = "Casablanca"          # motif cherché dans les attributs ADM1

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
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

WORLDPOP_URLS = [
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/"
    "2020/BSGM/MAR/mar_ppp_2020_constrained.tif",
    "https://worldpop-public-data.soton.ac.uk/GIS/Population/"
    "Global_2000_2020_Constrained/2020/BSGM/MAR/mar_ppp_2020_constrained.tif",
]

# Limites administratives HCP (COD-AB, redistribuées par OCHA sur HDX)
HDX_API = "https://data.humdata.org/api/3/action/package_show"
HDX_LIMITES_IDS = ["cod-ab-mar", "morocco-administrative-boundaries-populated-places"]
HDX_LIMITES_PAGE = ("https://data.humdata.org/dataset/"
                    "morocco-administrative-boundaries-populated-places")

# Population légale RGPH 2024 par commune (décret, publication HCP)
HCP_POP_LEGALE_URL = "https://hcp.ma/file/242227"
HCP_RGPH_PLATEFORME = "https://resultats2024.rgphapps.ma"

USER_AGENT = "geodata-ecole-ingenieurs/0.1 (projet pedagogique)"

# Licences déclarées (reprises dans SOURCES.md et le rapport de preuve)
LICENCES = {
    "osm": "ODbL 1.0 — © contributeurs OpenStreetMap",
    "worldpop": "CC BY 4.0 — WorldPop (Univ. of Southampton)",
    "limites": "HCP via OCHA/HDX — vérifier la licence affichée sur la page HDX",
    "hcp_pop": "HCP — publication officielle, réutilisation avec citation de la source",
}