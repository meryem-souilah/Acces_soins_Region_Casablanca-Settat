"""
geocodage_essp.py — Position des établissements de soins de santé primaires (MSPS)

Le fichier du Ministère de la Santé donne la commune et le nom de chaque
établissement, mais pas ses coordonnées. Ce script :

  1. rattache chaque établissement à une commune HCP (code_hcp) ;
  2. cherche sa position avec Nominatim (le géocodeur d'OpenStreetMap) ;
  3. n'accepte une position que si elle tombe DANS la bonne commune ;
  4. applique les positions saisies à la main pour les cas non trouvés ;
  5. note pour chaque établissement d'où vient sa position (precision_geom).

Entrées  : donnees_brutes/msps/essp_casablanca_settat_2022.xlsx
           donnees_brutes/limites/limites_casablanca_settat.gpkg (couche communes)
           corrections/communes_essp.csv     (facultatif) commune_source;code_hcp
           corrections/positions_essp*.csv   (facultatif) id_source;lat;lon;justification
                                             (un fichier par membre du groupe possible)
Sorties  : donnees_propres/essp_geocode.gpkg      couche etablissement_essp (EPSG:26191)
           donnees_propres/cache_nominatim.json   réponses déjà reçues (pas de 2e requête)
           corrections/a_positionner_essp.csv     établissements sans position (à compléter)
           preuves/rapport_geocodage.md

Règles d'usage de Nominatim respectées : 1 requête par seconde au plus, un
User-Agent qui identifie le projet, et un cache pour ne jamais redemander la
même chose. Compter 10 à 20 minutes au premier lancement, quelques secondes ensuite.

Usage :
    python scripts/geocodage_essp.py --sans-reseau    # communes seulement, sans géocoder
    python scripts/geocodage_essp.py                  # tout
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import sys
import time
from urllib.parse import quote_plus
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402  (avant geopandas : correctif PROJ)

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
from shapely.geometry import Point  # noqa: E402

from nettoyage import normaliser  # noqa: E402  (même normalisation que le nettoyage)

DB = C.DONNEES_BRUTES
PROPRES = C.RACINE / "donnees_propres"
CORRECTIONS = C.RACINE / "corrections"
ENTREE = DB / "msps" / "essp_casablanca_settat_2022.xlsx"
SORTIE = PROPRES / "essp_geocode.gpkg"
CACHE = PROPRES / "cache_nominatim.json"
CRS = C.CRS_METRIQUE

NOMINATIM = "https://nominatim.openstreetmap.org/search"
PAUSE_S = 1.1                 # politique Nominatim : 1 requête / seconde au plus
TOLERANCE_COMMUNE_M = 500     # un point à moins de 500 m de la limite est accepté
SEUIL_NOM_COMMUNE = 0.80      # ressemblance minimale entre deux noms de commune

# Types de réponse Nominatim qui désignent l'établissement lui-même
TYPES_ETABLISSEMENT = {"clinic", "hospital", "doctors", "healthcare", "dentist"}
# Types qui désignent seulement un lieu (douar, quartier, village)
TYPES_LIEU = {"village", "hamlet", "town", "city", "suburb", "neighbourhood", "quarter",
              "locality", "isolated_dwelling", "residential", "administrative", "municipality"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Rattachement aux communes HCP
# ─────────────────────────────────────────────────────────────────────────────
def charger_communes():
    f = DB / "limites" / "limites_casablanca_settat.gpkg"
    g = gpd.read_file(f, layer="communes").to_crs(CRS)
    g["cle"] = g["nom"].map(normaliser)
    return g


def rattacher_communes(e, communes):
    """code_hcp de chaque établissement : correction manuelle, sinon nom exact dans la
    province, sinon nom le plus ressemblant dans la province."""
    manuel = {}
    f = CORRECTIONS / "communes_essp.csv"
    if f.exists():
        m = pd.read_csv(f, sep=";", dtype=str).fillna("")
        manuel = dict(zip(m["commune_source"].str.strip(), m["code_hcp"].str.strip()))

    # Casablanca : les arrondissements de la ville relèvent tous de la commune Casablanca
    casa = communes[(communes["code_province"] == "06.141") & (communes["cle"] == "casablanca")]
    code_casa = casa["code_hcp"].iloc[0] if len(casa) else None

    codes, methodes = [], []
    for _, r in e.iterrows():
        src = str(r["commune_source"]).strip()
        if src in manuel and manuel[src]:
            codes.append(manuel[src]); methodes.append("correction manuelle"); continue
        if r["type_commune"] == "arrondissement" and code_casa:
            codes.append(code_casa); methodes.append("arrondissement de Casablanca"); continue
        cand = communes[communes["code_province"] == r["code_province"]]
        cle = normaliser(r["commune"])
        exact = cand[cand["cle"] == cle]
        if len(exact):
            codes.append(exact["code_hcp"].iloc[0]); methodes.append("nom identique"); continue
        proche = difflib.get_close_matches(cle, cand["cle"].tolist(), n=1, cutoff=SEUIL_NOM_COMMUNE)
        if proche:
            codes.append(cand.loc[cand["cle"] == proche[0], "code_hcp"].iloc[0])
            methodes.append(f"nom proche : {proche[0]}"); continue
        codes.append(None); methodes.append("non trouvée")
    e["code_hcp"], e["methode_commune"] = codes, methodes
    return e


# ─────────────────────────────────────────────────────────────────────────────
# 2. Géocodage
# ─────────────────────────────────────────────────────────────────────────────
class Geocodeur:
    def __init__(self, hors_ligne: bool):
        self.hors_ligne = hors_ligne
        self.cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = C.USER_AGENT
        self.n_requetes = 0
        self._dernier = 0.0

    def chercher(self, requete: str, viewbox: str) -> list:
        cle = f"{requete}|{viewbox}"
        if cle in self.cache:
            return self.cache[cle]
        if self.hors_ligne:
            return []
        attente = PAUSE_S - (time.time() - self._dernier)
        if attente > 0:
            time.sleep(attente)
        params = {"q": requete, "format": "jsonv2", "limit": 5, "countrycodes": "ma",
                  "viewbox": viewbox, "bounded": 1, "accept-language": "fr"}
        try:
            r = self.session.get(NOMINATIM, params=params, timeout=30)
            r.raise_for_status()
            res = r.json()
        except Exception as ex:
            print(f"    Nominatim : échec pour « {requete} » ({str(ex)[:80]})")
            return []  # pas mis en cache : on réessaiera au prochain lancement
        finally:
            self._dernier = time.time()
            self.n_requetes += 1
        self.cache[cle] = res
        if self.n_requetes % 20 == 0:
            self.sauver()
        return res

    def sauver(self):
        PROPRES.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")


def requetes_pour(r, nom_province):
    """Du plus précis au plus général. Le type d'établissement aide Nominatim."""
    nom, commune = str(r["nom"]).strip(), str(r["commune"]).strip()
    genre = "centre de santé" if str(r["categorie_msps"]).startswith("CS") else "dispensaire"
    return [f"{genre} {nom}, {commune}", f"{nom}, {commune}", f"{nom}, {nom_province}"]


def geocoder(e, communes, geo: Geocodeur, noms_province):
    poly = communes.set_index("code_hcp").geometry
    xs, ys, precisions, details = [], [], [], []
    for n, (_, r) in enumerate(e.iterrows(), start=1):
        if n % 25 == 0:
            print(f"    {n}/{len(e)}")
        x = y = None
        precision, detail = "non_trouve", ""
        if r["code_hcp"] in poly.index:
            zone = poly[r["code_hcp"]]
            zone_tol = zone.buffer(TOLERANCE_COMMUNE_M)
            b = gpd.GeoSeries([zone_tol], crs=CRS).to_crs(C.CRS_GEO).total_bounds
            viewbox = f"{b[0]:.4f},{b[3]:.4f},{b[2]:.4f},{b[1]:.4f}"
            for q in requetes_pour(r, noms_province.get(r["code_province"], "")):
                trouve = None
                for res in geo.chercher(q, viewbox):
                    pt = gpd.GeoSeries([Point(float(res["lon"]), float(res["lat"]))],
                                       crs=C.CRS_GEO).to_crs(CRS).iloc[0]
                    if not pt.within(zone_tol):
                        continue  # hors de la commune annoncée : refusé
                    typ = res.get("type", "")
                    if typ in TYPES_ETABLISSEMENT or res.get("category") == "amenity":
                        trouve = (pt, "geocodage_etablissement", f"{q} → {res.get('display_name', '')[:90]}")
                        break
                    if trouve is None and typ in TYPES_LIEU:
                        trouve = (pt, "geocodage_lieu", f"{q} → {typ} : {res.get('display_name', '')[:80]}")
                if trouve and trouve[1] == "geocodage_etablissement":
                    break
                if trouve:
                    break
            if trouve:
                x, y, precision, detail = trouve[0].x, trouve[0].y, trouve[1], trouve[2]
        xs.append(x); ys.append(y); precisions.append(precision); details.append(detail)
    e["x"], e["y"], e["precision_geom"], e["detail_geocodage"] = xs, ys, precisions, details
    return e


def appliquer_positions_manuelles(e):
    # Tous les fichiers positions_essp*.csv : chaque membre du groupe peut remplir le sien
    fichiers = sorted(CORRECTIONS.glob("positions_essp*.csv")) if CORRECTIONS.exists() else []
    if not fichiers:
        return 0
    m = pd.concat([pd.read_csv(f, sep=";", dtype=str, encoding="utf-8-sig") for f in fichiers]).fillna("")
    doublons = m[m["id_source"].duplicated(keep=False) & (m["lat"] != "")]
    if len(doublons):
        print(f"    attention : positions saisies deux fois : {sorted(set(doublons['id_source']))}")
    m = m[(m["lat"].str.strip() != "") & (m["lon"].str.strip() != "")]
    n = 0
    for _, r in m.iterrows():
        idx = e.index[e["id_source"] == r["id_source"].strip()]
        if not len(idx):
            print(f"    position manuelle : {r['id_source']} inconnu")
            continue
        pt = gpd.GeoSeries([Point(float(r["lon"].replace(",", ".")), float(r["lat"].replace(",", ".")))],
                           crs=C.CRS_GEO).to_crs(CRS).iloc[0]
        e.loc[idx, ["x", "y"]] = [pt.x, pt.y]
        e.loc[idx, "precision_geom"] = "manuel"
        e.loc[idx, "detail_geocodage"] = r.get("justification", "")
        n += 1
    return n


# ─────────────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sans-reseau", action="store_true",
                   help="n'interroge pas Nominatim (utilise seulement le cache)")
    a = p.parse_args()

    if not ENTREE.exists():
        sys.exit(f"{ENTREE} absent : déposez-y le fichier essp_casablanca_settat_2022.xlsx")
    e = pd.read_excel(ENTREE, sheet_name=0, dtype={"code_province": str})
    communes = charger_communes()
    from nettoyage import PROVINCES_NOMS

    print("[communes]")
    e = rattacher_communes(e, communes)
    sans_commune = e["code_hcp"].isna()
    print(f"    {int((~sans_commune).sum())}/{len(e)} établissements rattachés à une commune")

    print("[géocodage]" + (" (cache seulement)" if a.sans_reseau else ""))
    geo = Geocodeur(hors_ligne=a.sans_reseau)
    try:
        e = geocoder(e, communes, geo, PROVINCES_NOMS)
    finally:
        geo.sauver()
    n_manuel = appliquer_positions_manuelles(e)

    # Liste des établissements encore sans position, à compléter à la main.
    # Seuls ceux qui entrent dans l'analyse (inclus_analyse) sont listés, triés par
    # province pour pouvoir répartir le travail entre les membres du groupe.
    CORRECTIONS.mkdir(exist_ok=True)
    reste = e[e["x"].isna() & e["inclus_analyse"].astype(bool)].sort_values(
        ["code_province", "commune_source", "nom"])
    noms_com = communes.set_index("code_hcp")["nom"]
    with open(CORRECTIONS / "a_positionner_essp.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id_source", "code_province", "delegation", "commune", "commune_hcp", "nom",
                    "categorie_msps", "recherche", "lat", "lon", "justification"])
        for _, r in reste.iterrows():
            q = quote_plus(f"centre de santé {r['nom']} {r['commune']} Maroc")
            w.writerow([r["id_source"], r["code_province"], r["delegation"], r["commune_source"],
                        noms_com.get(r["code_hcp"], "NON RATTACHÉE"), r["nom"], r["categorie_msps"],
                        f"https://www.google.com/maps/search/?api=1&query={q}", "", "", ""])

    # Couche finale : seulement les établissements positionnés
    ok = e[e["x"].notna()].copy()
    g = gpd.GeoDataFrame(ok[["id_source", "nom", "categorie_msps", "code_type", "code_niveau",
                             "inclus_analyse", "code_hcp", "precision_geom"]],
                         geometry=gpd.points_from_xy(ok["x"], ok["y"]), crs=CRS)
    g["source"] = "msps"
    g["niveau_source"] = "defaut_type"
    # contrôle : le point est-il bien dans sa commune ?
    # Distance de chaque point à SA commune : 0 = dedans ; <= tolérance = accepté en bordure
    poly = communes.set_index("code_hcp").geometry
    g["dist_commune_m"] = [round(pt.distance(poly[c]), 1) if c in poly.index else None
                           for pt, c in zip(g.geometry, g["code_hcp"])]
    en_bordure = g[(g["dist_commune_m"] > 0) & (g["dist_commune_m"] <= TOLERANCE_COMMUNE_M)]
    incoherents = int((g["dist_commune_m"] > TOLERANCE_COMMUNE_M).sum())
    PROPRES.mkdir(exist_ok=True)
    g.to_file(SORTIE, layer="etablissement_essp", driver="GPKG")

    # Rapport
    rep = e["precision_geom"].value_counts().reindex(
        ["geocodage_etablissement", "geocodage_lieu", "manuel", "non_trouve"], fill_value=0)
    par_prov = e.assign(pos=e["x"].notna()).groupby("code_province").agg(
        total=("id_source", "size"), positionnes=("pos", "sum"))
    meth = e["methode_commune"].str.split(" :").str[0].value_counts()
    md = ["# Rapport de géocodage des établissements de soins de santé primaires", "",
          f"Exécuté le {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} par "
          f"`scripts/geocodage_essp.py`. Requêtes Nominatim envoyées : {geo.n_requetes} "
          f"(les autres réponses viennent du cache).", "",
          "## Rattachement aux communes HCP", "",
          "| Méthode | Établissements |", "| --- | --- |",
          *[f"| {k} | {v} |" for k, v in meth.items()], "",
          "## Origine des positions", "",
          "| precision_geom | Établissements | Signification |", "| --- | --- | --- |",
          f"| geocodage_etablissement | {rep['geocodage_etablissement']} | Nominatim a trouvé l'établissement lui-même |",
          f"| geocodage_lieu | {rep['geocodage_lieu']} | Nominatim a trouvé le douar ou le quartier qui porte ce nom |",
          f"| manuel | {rep['manuel']} | position saisie à la main (corrections/positions_essp.csv) |",
          f"| non_trouve | {rep['non_trouve']} | sans position : à compléter dans corrections/a_positionner_essp.csv |",
          "", f"Établissements de l'analyse encore sans position : {len(reste)} "
          f"(les {int((~e['inclus_analyse'].astype(bool)).sum())} centres spécialisés et laboratoires ne sont pas listés).", "",
          f"Points à plus de {TOLERANCE_COMMUNE_M} m de leur commune déclarée : {incoherents} (attendu : 0).", "",
          f"Points juste hors de leur commune, dans la bande de tolérance de {TOLERANCE_COMMUNE_M} m : "
          f"{len(en_bordure)}. Ils sont acceptés : la limite communale et le géocodage ont chacun "
          "une imprécision de quelques centaines de mètres.", "",
          *(["| id_source | Nom | Distance à la commune (m) |", "| --- | --- | --- |",
             *[f"| {r.id_source} | {r.nom} | {r.dist_commune_m} |" for r in en_bordure.itertuples()], ""]
            if len(en_bordure) else []),
          "## Par province", "", "| Code | Total | Positionnés |", "| --- | --- | --- |",
          *[f"| {c} | {r.total} | {r.positionnes} |" for c, r in par_prov.iterrows()], ""]
    C.PREUVES.mkdir(exist_ok=True)
    (C.PREUVES / "rapport_geocodage.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nCouche : {SORTIE}  ({len(g)} établissements positionnés, dont {n_manuel} à la main)")


if __name__ == "__main__":
    main()
