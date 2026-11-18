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
import re
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
# Rapprochement avec les lieux nommés OSM : 0,88 accepte « Tagourate » / « Douar Tagourant »
# mais refuse « Sidi Belkacem » / « Sidi Kacem » (0,87). Deux lieux distincts à moins de
# ECART_AMBIGU du meilleur score : rapprochement ambigu, refusé.
SEUIL_NOM_LIEU = 0.88
ECART_AMBIGU = 0.03
LIEUX_GEOFABRIK = DB / "osm_routes" / "morocco-latest-free.shp.zip"
LIEUX_OVERPASS = PROPRES / "lieux_osm_overpass.json"
# Abréviations du fichier du Ministère, développées avant comparaison (texte déjà normalisé)
ABREVIATIONS = [(r"\bod\b\.?", "oulad"), (r"\boulad\b|\bouled\b|\bawlad\b", "oulad"),
                (r"\bs\b\.?", "sidi"), (r"\bmy\b", "moulay"), (r"\bb\b\.?", "ben"),
                (r"\bbni\b", "beni"), (r"\b(el|al|la|douar|dr)\b", " ")]

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


def _coordonnee(v) -> float | None:
    v = str(v).strip().replace(",", ".")
    if v.upper() in ("", "NULL", "NAN", "NONE"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def appliquer_positions_manuelles(e, communes):
    """Positions saisies à la main (corrections/positions_essp*.csv).

    Même règle que le géocodage automatique : la position n'est acceptée que si elle
    tombe dans la commune déclarée (tolérance TOLERANCE_COMMUNE_M). Les positions
    refusées sont listées dans corrections/positions_rejetees_essp.csv, avec la commune
    où le point tombe réellement, pour être corrigées dans le fichier du lot.
    """
    fichiers = sorted(CORRECTIONS.glob("positions_essp*.csv")) if CORRECTIONS.exists() else []
    if not fichiers:
        return 0, pd.DataFrame()
    m = pd.concat([pd.read_csv(f, sep=";", dtype=str, encoding="utf-8-sig").assign(fichier=f.name)
                   for f in fichiers]).fillna("")
    m["lat_f"], m["lon_f"] = m["lat"].map(_coordonnee), m["lon"].map(_coordonnee)
    m = m[m["lat_f"].notna() & m["lon_f"].notna()]
    doublons = m[m["id_source"].duplicated(keep=False)]
    if len(doublons):
        print(f"    attention : positions saisies deux fois : {sorted(set(doublons['id_source']))}")
    poly = communes.set_index("code_hcp").geometry
    noms = communes.set_index("code_hcp")["nom"]
    n, rejets = 0, []
    for _, r in m.iterrows():
        idx = e.index[e["id_source"] == r["id_source"].strip()]
        if not len(idx):
            print(f"    position manuelle : {r['id_source']} inconnu")
            continue
        code = e.at[idx[0], "code_hcp"]
        pt = gpd.GeoSeries([Point(r["lon_f"], r["lat_f"])], crs=C.CRS_GEO).to_crs(CRS).iloc[0]
        dist = pt.distance(poly[code]) if code in poly.index else float("inf")
        if dist > TOLERANCE_COMMUNE_M:
            reelle = poly.index[poly.contains(pt)]
            rejets.append({
                "fichier": r["fichier"], "id_source": r["id_source"], "nom": e.at[idx[0], "nom"],
                "commune_declaree": noms.get(code, ""), "lat": r["lat"].strip(), "lon": r["lon"].strip(),
                "distance_commune_km": round(dist / 1000, 1),
                "commune_du_point": noms.get(reelle[0], "") if len(reelle) else "HORS RÉGION",
                "recherche": r.get("recherche", ""),
            })
            continue
        e.loc[idx, ["x", "y"]] = [pt.x, pt.y]
        e.loc[idx, "precision_geom"] = "manuel"
        e.loc[idx, "detail_geocodage"] = r.get("justification", "")
        n += 1
    rejets = pd.DataFrame(rejets)
    f_rejets = CORRECTIONS / "positions_rejetees_essp.csv"
    if len(rejets):
        rejets.sort_values(["fichier", "distance_commune_km"]).to_csv(
            f_rejets, sep=";", index=False, encoding="utf-8-sig")
    elif f_rejets.exists():
        f_rejets.unlink()
    return n, rejets


# ─────────────────────────────────────────────────────────────────────────────
# 5. Rapprochement des noms avec les lieux nommés d'OpenStreetMap
# ─────────────────────────────────────────────────────────────────────────────
def _nom_lieu(t) -> str:
    t = normaliser(t).replace(".", " ")
    for motif, rempl in ABREVIATIONS:
        t = re.sub(motif, rempl, t)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def _variantes(nom) -> set[str]:
    """« Haouzia (Tikni) » → {haouzia tikni, haouzia, tikni} ; « A-B » → aussi A et B."""
    nom = str(nom)
    v = {nom, *re.findall(r"\(([^)]*)\)", nom), re.sub(r"\(.*?\)", " ", nom)}
    for s in list(v):
        v |= set(re.split(r"[-/]", s))
    return {n for n in map(_nom_lieu, v) if len(n) >= 4}


def charger_lieux(sans_reseau: bool):
    """Lieux nommés OSM (villages, douars, quartiers) : couche places de l'extrait
    Geofabrik déjà téléchargé, complétée par Overpass (hameaux, lieux-dits) si possible."""
    morceaux = []
    if LIEUX_GEOFABRIK.exists():
        b = gpd.GeoSeries.from_xy([C.BBOX["ouest"], C.BBOX["est"]], [C.BBOX["sud"], C.BBOX["nord"]],
                                  crs=C.CRS_GEO).total_bounds
        g = gpd.read_file(f"zip://{LIEUX_GEOFABRIK.as_posix()}!gis_osm_places_free_1.shp", bbox=tuple(b))
        morceaux.append(g[["name", "fclass", "geometry"]].rename(columns={"fclass": "place"}))
    if not LIEUX_OVERPASS.exists() and not sans_reseau:
        _telecharger_lieux_overpass()
    if LIEUX_OVERPASS.exists():
        el = json.loads(LIEUX_OVERPASS.read_text(encoding="utf-8"))
        lignes = []
        for x in el:
            lat, lon = (x["lat"], x["lon"]) if "lat" in x else (x["center"]["lat"], x["center"]["lon"])
            for k in ("name", "name:fr", "name:en"):
                if x["tags"].get(k):
                    lignes.append({"name": x["tags"][k], "place": x["tags"].get("place"),
                                   "geometry": Point(lon, lat)})
        morceaux.append(gpd.GeoDataFrame(lignes, crs=C.CRS_GEO))
    if not morceaux:
        return None
    lieux = pd.concat([m.to_crs(CRS) for m in morceaux], ignore_index=True)
    lieux = lieux[lieux["name"].notna()].copy()
    lieux["cle"] = lieux["name"].map(_nom_lieu)
    lieux = lieux[lieux["cle"].str.len() >= 4]
    # même nom au même endroit (Geofabrik et Overpass) : une seule fois
    lieux["xy"] = [(round(p.x, -2), round(p.y, -2)) for p in lieux.geometry]
    return gpd.GeoDataFrame(lieux.drop_duplicates(["cle", "xy"]).drop(columns="xy"), crs=CRS)


def _telecharger_lieux_overpass():
    b = C.BBOX
    bb = f"{b['sud']},{b['ouest']},{b['nord']},{b['est']}"
    q = f"[out:json][timeout:280];(node[place][name]({bb});way[place][name]({bb}););out center tags;"
    for url in reversed(C.OVERPASS_URLS):
        try:
            r = requests.post(url, data={"data": q}, headers={"User-Agent": C.USER_AGENT}, timeout=300)
            r.raise_for_status()
            LIEUX_OVERPASS.write_text(json.dumps(r.json()["elements"], ensure_ascii=False), encoding="utf-8")
            return
        except Exception as ex:  # serveur saturé : on essaie le suivant
            print(f"    Overpass {url} : {str(ex)[:80]}")
    print("    lieux Overpass indisponibles : seuls les lieux Geofabrik sont utilisés")


def rapprocher_lieux(e, communes, lieux) -> pd.DataFrame:
    """Établissements encore sans position : on cherche, DANS leur commune, un lieu OSM
    dont le nom ressemble au leur (abréviations développées). Position = celle du lieu,
    precision_geom = geocodage_lieu, comme un douar trouvé par Nominatim."""
    poly = communes.set_index("code_hcp").geometry
    trouves = []
    for i in e.index[e["x"].isna()]:
        code = e.at[i, "code_hcp"]
        if code not in poly.index:
            continue
        cand = lieux[lieux.within(poly[code].buffer(TOLERANCE_COMMUNE_M))]
        scores = []
        for v in _variantes(e.at[i, "nom"]):
            for j, cle in zip(cand.index, cand["cle"]):
                scores.append((difflib.SequenceMatcher(None, v, cle).ratio(), j))
        if not scores:
            continue
        s, j = max(scores)
        if s < SEUIL_NOM_LIEU:
            continue
        rivaux = {k for sc, k in scores if sc >= s - ECART_AMBIGU
                  and cand.geometry[k].distance(cand.geometry[j]) > 1000}
        if rivaux:
            continue  # deux lieux différents portent un nom aussi proche : ambigu
        pt = cand.geometry[j]
        e.loc[i, ["x", "y"]] = [pt.x, pt.y]
        e.loc[i, "precision_geom"] = "geocodage_lieu"
        e.loc[i, "detail_geocodage"] = f"rapprochement OSM : {cand.at[j, 'name']} ({s:.2f})"
        trouves.append({"id_source": e.at[i, "id_source"], "nom": e.at[i, "nom"],
                        "lieu_osm": cand.at[j, "name"], "type": cand.at[j, "place"], "score": round(s, 2)})
    return pd.DataFrame(trouves)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Dernier recours : cœur habité de la commune
# ─────────────────────────────────────────────────────────────────────────────
def position_approx_commune(e, communes) -> int:
    """Centre de la population de la commune (moyenne des hexagones H3 pondérée par
    leurs habitants WorldPop), ramené sur l'hexagone habité le plus proche pour rester
    dans une zone réellement peuplée. precision_geom = approx_commune."""
    import pyogrio
    base = PROPRES / "base_sante.gpkg"
    if not base.exists() or "maille_h3" not in pyogrio.list_layers(base)[:, 0]:
        print("    base_sante.gpkg sans maille_h3 : lancez d'abord nettoyage.py")
        return 0
    h3 = gpd.read_file(base, layer="maille_h3", columns=["code_hcp", "population"])
    h3 = h3[h3["population"] > 0]
    h3["c"] = h3.geometry.centroid
    poly = communes.set_index("code_hcp").geometry
    n = 0
    for i in e.index[e["x"].isna()]:
        code = e.at[i, "code_hcp"]
        hx = h3[h3["code_hcp"] == code]
        if len(hx):
            w = hx["population"]
            moy = Point((hx["c"].x * w).sum() / w.sum(), (hx["c"].y * w).sum() / w.sum())
            pt = hx["c"].iloc[int(hx["c"].distance(moy).argmin())]
        elif code in poly.index:
            pt = poly[code].representative_point()
        else:
            continue
        e.loc[i, ["x", "y"]] = [pt.x, pt.y]
        e.loc[i, "precision_geom"] = "approx_commune"
        e.loc[i, "detail_geocodage"] = "centre de la population de la commune (WorldPop, H3)"
        n += 1
    return n


def _bilan_lots(rejets):
    """(fichier, positions saisies, positions refusées) pour chaque fichier de lot."""
    out = []
    for f in sorted(CORRECTIONS.glob("positions_essp*.csv")):
        d = pd.read_csv(f, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
        saisies = int((d["lat"].map(_coordonnee).notna() & d["lon"].map(_coordonnee).notna()).sum())
        refusees = int((rejets["fichier"] == f.name).sum()) if len(rejets) else 0
        out.append((f.name, saisies, refusees))
    return out


# ─────────────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sans-reseau", action="store_true",
                   help="n'interroge ni Nominatim ni Overpass (utilise seulement les caches)")
    p.add_argument("--sans-approximation", action="store_true",
                   help="ne place pas les établissements restants au centre habité de leur commune")
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
    n_manuel, rejets = appliquer_positions_manuelles(e, communes)

    print("[rapprochement avec les lieux OSM]")
    lieux = charger_lieux(a.sans_reseau)
    rapproches = rapprocher_lieux(e, communes, lieux) if lieux is not None else pd.DataFrame()
    print(f"    {len(rapproches)} établissements placés sur un lieu OSM de même nom "
          f"({0 if lieux is None else len(lieux)} lieux dans la région)")
    n_approx = 0
    if not a.sans_approximation:
        print("[centre habité de la commune]")
        n_approx = position_approx_commune(e, communes)
        print(f"    {n_approx} établissements placés au centre de la population de leur commune")

    # Liste des établissements sans position précise, à compléter à la main : sans
    # position, ou placés au centre de leur commune. Une saisie manuelle valide remplace
    # la position approchée. Seuls ceux de l'analyse (inclus_analyse) sont listés, triés
    # par province pour pouvoir répartir le travail entre les membres du groupe.
    CORRECTIONS.mkdir(exist_ok=True)
    reste = e[(e["x"].isna() | (e["precision_geom"] == "approx_commune"))
              & e["inclus_analyse"].astype(bool)].sort_values(["code_province", "commune_source", "nom"])
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
        ["geocodage_etablissement", "geocodage_lieu", "manuel", "approx_commune", "non_trouve"], fill_value=0)
    n_lieu_osm = len(rapproches)
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
          f"| geocodage_lieu | {rep['geocodage_lieu']} | douar ou quartier qui porte ce nom, dans la bonne commune : "
          f"Nominatim ({rep['geocodage_lieu'] - n_lieu_osm}) ou rapprochement avec les lieux OSM ({n_lieu_osm}) |",
          f"| manuel | {rep['manuel']} | position saisie à la main (corrections/positions_essp*.csv), vérifiée dans la commune |",
          f"| approx_commune | {rep['approx_commune']} | **approximative** : centre de la population de la commune (hexagones H3 pondérés par WorldPop) |",
          f"| non_trouve | {rep['non_trouve']} | sans position |",
          "", f"Établissements de l'analyse sans position précise (sans position ou `approx_commune`) : {len(reste)}, "
          "listés dans `corrections/a_positionner_essp.csv` ; une saisie manuelle valide remplace la position approchée "
          f"(les {int((~e['inclus_analyse'].astype(bool)).sum())} centres spécialisés et laboratoires ne sont pas listés).", "",
          "**Limite** : une position `approx_commune` peut être à plusieurs kilomètres du vrai centre dans les grandes "
          "communes rurales. Elle évite de compter comme non desservie la population d'un centre qui existe ; "
          "l'analyse d'accessibilité doit être testée avec et sans ces positions.", "",
          *(["**Rapprochements avec les lieux OSM** (seuil de ressemblance "
             f"{SEUIL_NOM_LIEU}, lieu dans la commune, rapprochements ambigus refusés)", "",
             "| id_source | Nom (Ministère) | Lieu OSM | Type | Score |", "| --- | --- | --- | --- | --- |",
             *[f"| {r.id_source} | {r.nom} | {r.lieu_osm} | {r.type} | {r.score} |" for r in rapproches.itertuples()], ""]
            if len(rapproches) else []),
          f"Points à plus de {TOLERANCE_COMMUNE_M} m de leur commune déclarée : {incoherents} (attendu : 0).", "",
          f"Points juste hors de leur commune, dans la bande de tolérance de {TOLERANCE_COMMUNE_M} m : "
          f"{len(en_bordure)}. Ils sont acceptés : la limite communale et le géocodage ont chacun "
          "une imprécision de quelques centaines de mètres.", "",
          *(["| id_source | Nom | Distance à la commune (m) |", "| --- | --- | --- |",
             *[f"| {r.id_source} | {r.nom} | {r.dist_commune_m} |" for r in en_bordure.itertuples()], ""]
            if len(en_bordure) else []),
          "## Positions manuelles refusées", "",
          (f"{len(rejets)} positions saisies à la main tombent à plus de {TOLERANCE_COMMUNE_M} m de "
           "leur commune déclarée : elles ne sont PAS appliquées. Détail (commune où tombe "
           "réellement le point) dans `corrections/positions_rejetees_essp.csv`." if len(rejets)
           else "Aucune."), "",
          *(["| Fichier | Saisies | Acceptées | Refusées |", "| --- | --- | --- | --- |",
             *[f"| {f} | {s} | {s - r} | {r} |" for f, s, r in _bilan_lots(rejets)], ""]
            if CORRECTIONS.exists() and any(CORRECTIONS.glob("positions_essp*.csv")) else []),
          *(["| Où tombe le point refusé | Nombre |", "| --- | --- |",
             *[f"| {k} | {v} |" for k, v in rejets["commune_du_point"].value_counts().head(8).items()], ""]
            if len(rejets) else []),
          "## Par province", "", "| Code | Total | Positionnés |", "| --- | --- | --- |",
          *[f"| {c} | {r.total} | {r.positionnes} |" for c, r in par_prov.iterrows()], ""]
    C.PREUVES.mkdir(exist_ok=True)
    (C.PREUVES / "rapport_geocodage.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\nCouche : {SORTIE}  ({len(g)} établissements positionnés, dont {n_manuel} à la main)")


if __name__ == "__main__":
    main()
