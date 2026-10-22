"""
collecte.py — Pipeline de collecte multi-sources (phase 1, intersession 2)

Une seule commande récupère toutes les sources du projet, les découpe sur la
région Casablanca-Settat, les reprojette dans un CRS unique (EPSG:26191) et
documente leur provenance. Aucune opération manuelle n'est nécessaire, sauf
si un serveur bloque les requêtes automatisées : le script le signale et
accepte alors un fichier déposé à la main (voir GUIDE_INSTALLATION.md).

Étapes (dans l'ordre, chacune dépend des précédentes) :
    limites   communes OSM (codes HCP) + contour régional, secours geoBoundaries
    sante     établissements de santé OSM (Overpass), découpés sur la région
    routes    réseau routier circulable de toute la région (extrait OSM Geofabrik)
    worldpop  population 100 m WorldPop 2020, découpée et reprojetée
    hcp       population légale RGPH 2024 (PDF HCP), lignes de la région

Sorties :
    donnees_brutes/<source>/...        fichiers originaux + couches régionales
    donnees_brutes/manifest.json       provenance machine (URL, date, SHA-256…)
    donnees_brutes/README.md           README de provenance (généré)
    SOURCES.md                         inventaire des sources (généré)

Usage :
    python scripts/collecte.py                     # tout, en réutilisant le cache
    python scripts/collecte.py --etapes sante routes
    python scripts/collecte.py --force             # retélécharge tout
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

DB = C.DONNEES_BRUTES
MANIFEST = DB / "manifest.json"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = C.USER_AGENT
CRS_CIBLE = C.CRS_METRIQUE  # EPSG:26191, CRS unique de toutes les couches produites


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────
def maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def info_fichier(p: Path) -> dict:
    return {"chemin": p.relative_to(C.RACINE).as_posix(),
            "taille_mo": round(p.stat().st_size / 1_048_576, 2),
            "sha256": sha256(p)}


def normaliser(txt: str) -> str:
    """minuscules, sans accents ni tirets : « Sidi-Bennour » → « sidi bennour »."""
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().replace("-", " ").replace("_", " ").split())


def telecharger(urls: list[str], dest: Path, entetes: dict | None = None,
                essais: int = 3, timeout: int = 300) -> str:
    """Télécharge depuis le premier miroir qui répond, avec réessais espacés."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    erreurs = []
    for url in urls:
        for n in range(1, essais + 1):
            try:
                print(f"    GET {url}" + (f" (essai {n})" if n > 1 else ""))
                with SESSION.get(url, stream=True, timeout=timeout, headers=entetes) as r:
                    r.raise_for_status()
                    total, recu = int(r.headers.get("content-length", 0)), 0
                    with open(tmp, "wb") as f:
                        for bloc in r.iter_content(1 << 20):
                            f.write(bloc)
                            recu += len(bloc)
                            if total:
                                print(f"\r      {recu / total:6.1%} de {total / 1e6:.1f} Mo",
                                      end="", flush=True)
                    if total:
                        print()
                tmp.replace(dest)
                return url
            except Exception as e:
                erreurs.append(f"{url}: {e}")
                print(f"    échec : {str(e).splitlines()[0][:120]}")
                time.sleep(5 * n)
    tmp.unlink(missing_ok=True)
    raise RuntimeError("aucun miroir n'a répondu — " + " | ".join(erreurs[-2:]))


def fichier_depose(dossier: Path, motifs: tuple[str, ...]) -> Path | None:
    """Un fichier téléchargé à la main et déposé dans le dossier de la source."""
    for motif in motifs:
        trouves = sorted(dossier.glob(motif)) if dossier.exists() else []
        if trouves:
            return trouves[0]
    return None


def requete_overpass(requete: str, dest: Path) -> str:
    """POST sur le premier serveur Overpass qui répond ; la réponse brute est conservée."""
    derniere = None
    for url in C.OVERPASS_URLS:
        for n in (1, 2):
            try:
                print(f"    POST {url}" + (" (essai 2)" if n == 2 else ""))
                r = SESSION.post(url, data={"data": requete}, timeout=300)
                r.raise_for_status()
                # Un dépassement de délai côté serveur renvoie un JSON partiel + « remark »
                remarque = r.json().get("remark", "")
                if "error" in remarque.lower():
                    raise RuntimeError(f"réponse incomplète : {remarque[:120]}")
                dest.write_bytes(r.content)
                return url
            except Exception as e:
                derniere = e
                print(f"    échec : {str(e).splitlines()[0][:120]}")
                time.sleep(10 * n)
    raise RuntimeError(f"Overpass indisponible ({derniere})")


def charger_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"projet": "Accès aux soins — région Casablanca-Settat",
            "crs_cible": CRS_CIBLE, "sources": {}}


def region_polygone():
    """Contour régional produit par l'étape « limites » (EPSG:26191)."""
    import geopandas as gpd
    f = DB / "limites" / "limites_casablanca_settat.gpkg"
    if not f.exists():
        raise RuntimeError("contour régional absent : lancez d'abord l'étape « limites »")
    return gpd.read_file(f, layer="region")


# ─────────────────────────────────────────────────────────────────────────────
# Étape 1 — Limites administratives (contour régional + communes)
# ─────────────────────────────────────────────────────────────────────────────
def _polygone_relation(el: dict):
    """Polygone d'une relation OSM (« out geom ») : anneaux outer moins anneaux inner."""
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    def surface(roles: tuple[str, ...]):
        lignes = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                  for m in el.get("members", [])
                  if m["type"] == "way" and m.get("role", "") in roles and len(m.get("geometry", [])) > 1]
        return unary_union(list(polygonize(unary_union(lignes)))) if lignes else None

    ext, trous = surface(("outer", "")), surface(("inner",))
    return ext.difference(trous) if ext is not None and trous is not None else ext


def _communes_osm(force: bool, dossier: Path):
    """Communes de la région (admin_level=8) dont le code HCP commence par celui de la région."""
    import geopandas as gpd

    brut = dossier / "overpass_communes.json"
    requete = ("[out:json][timeout:300];\n"
               f'rel["boundary"="administrative"]["admin_level"="{C.ADMIN_LEVEL_COMMUNES}"]'
               f'["ref:MA:HCP"~"^{C.CODE_HCP_REGION}\\\\."]'
               f'({C.BBOX["sud"]},{C.BBOX["ouest"]},{C.BBOX["nord"]},{C.BBOX["est"]});\n'
               "out geom;")
    (dossier / "requete_communes.overpassql").write_text(requete, encoding="utf-8")
    url = "(réponse en cache)"
    if force or not brut.exists():
        url = requete_overpass(requete, brut)
    reponse = json.loads(brut.read_text(encoding="utf-8"))
    lignes = []
    for el in reponse.get("elements", []):
        t = el.get("tags", {})
        code = t.get("ref:MA:HCP", "").strip().rstrip(".")
        lignes.append({"code_hcp": code, "code_province": code[:6],
                       "nom": t.get("name:fr") or t.get("name"), "nom_ar": t.get("name:ar"),
                       "osm_id": f"relation/{el['id']}", "wikidata": t.get("wikidata"),
                       "geometry": _polygone_relation(el)})
    communes = gpd.GeoDataFrame(lignes, geometry="geometry", crs=C.CRS_GEO)
    vides = communes.geometry.isna() | communes.geometry.is_empty
    if vides.any():
        raise RuntimeError(f"{vides.sum()} communes sans géométrie : {communes[vides].nom.tolist()}")
    return communes.sort_values("code_hcp").reset_index(drop=True), brut, url, reponse


def etape_limites(force: bool) -> dict:
    import geopandas as gpd

    dossier = DB / "limites"
    dossier.mkdir(parents=True, exist_ok=True)
    sortie = dossier / "limites_casablanca_settat.gpkg"
    try:
        communes, brut, url, reponse = _communes_osm(force, dossier)
    except Exception as e:
        print(f"    communes OSM indisponibles ({str(e)[:120]})")
        communes = None

    if communes is not None:
        communes = communes.to_crs(CRS_CIBLE)
        communes["geometry"] = communes.geometry.make_valid()
        communes["surface_km2"] = (communes.area / 1e6).round(2)
        region = gpd.GeoDataFrame({"nom": ["Casablanca-Settat"], "code_hcp": [C.CODE_HCP_REGION]},
                                  # +/- 5 m referme les interstices entre communes voisines
                                  geometry=[communes.union_all().buffer(5).buffer(-5)],
                                  crs=CRS_CIBLE)
        source = {
            "titre": "Limites administratives — communes (admin_level 8) et contour régional",
            "producteur": "Contributeurs OpenStreetMap (codes géographiques HCP : ref:MA:HCP)",
            "url": url, "mode": "automatique (API Overpass)",
            "licence": C.LICENCES["limites"], "crs_origine": C.CRS_GEO,
            "date_donnees_osm": reponse.get("osm3s", {}).get("timestamp_osm_base"),
            "requete": "donnees_brutes/limites/requete_communes.overpassql",
            "fichiers_origine": [info_fichier(brut)],
            "nb_communes": len(communes),
            "provinces_retenues": sorted(communes["code_province"].unique()),
            "avertissement": "Le jeu COD-AB d'OCHA/HDX pour le Maroc s'arrête aux provinces "
                             "(admin2) : les communes viennent d'OSM, jointes au HCP par leur code.",
        }
    else:
        # Secours entièrement automatique : contour régional OSM (geoBoundaries),
        # sans communes. Signalé comme dégradé dans le manifeste.
        print("    secours : contour régional geoBoundaries (OSM), sans communes HCP")
        brut = dossier / "geoBoundaries-MAR-ADM1.geojson"
        if not brut.exists() or force:
            telecharger([C.GEOBOUNDARIES_ADM1], brut)
        adm1 = gpd.read_file(brut)
        region = adm1[adm1["shapeName"].map(normaliser).str.contains("casablanca")]
        if region.empty:
            raise RuntimeError("région introuvable dans geoBoundaries ADM1")
        crs_origine = adm1.crs.to_string()
        region = region.to_crs(CRS_CIBLE)[["shapeName", "geometry"]].rename(columns={"shapeName": "nom"})
        communes = None
        source = {
            "titre": "Contour régional (secours, sans communes)",
            "producteur": "geoBoundaries, d'après OpenStreetMap",
            "url": C.GEOBOUNDARIES_ADM1, "mode": "automatique (secours : Overpass indisponible)",
            "licence": C.LICENCES["geoboundaries"], "crs_origine": crs_origine,
            "fichiers_origine": [info_fichier(brut)],
            "avertissement": "Pas de communes : relancer « limites » quand Overpass répond.",
        }

    sortie.unlink(missing_ok=True)
    region.to_file(sortie, layer="region", driver="GPKG")
    if communes is not None:
        communes.to_file(sortie, layer="communes", driver="GPKG")
    surface = region.area.sum() / 1e6
    source.update({"crs_sortie": CRS_CIBLE, "fichiers_sortie": [info_fichier(sortie)],
                   "surface_region_km2": round(surface, 1),
                   "emprise_26191": [round(v) for v in region.total_bounds]})
    print(f"    région : {surface:,.0f} km²" +
          (f", {len(communes)} communes, {len(source['provinces_retenues'])} provinces"
           if communes is not None else ""))
    return source


# ─────────────────────────────────────────────────────────────────────────────
# Étape 2 — Établissements de santé (OpenStreetMap / Overpass)
# ─────────────────────────────────────────────────────────────────────────────
TAGS_SANTE = ["name", "name:fr", "name:ar", "amenity", "healthcare", "healthcare:speciality",
              "operator", "operator:type", "beds", "emergency", "opening_hours", "addr:city"]


def etape_sante(force: bool) -> dict:
    import geopandas as gpd
    from shapely.geometry import Point

    dossier = DB / "osm_sante"
    dossier.mkdir(parents=True, exist_ok=True)
    brut = dossier / "overpass_reponse.json"
    region = region_polygone()
    b = region.to_crs(C.CRS_GEO).total_bounds  # ouest, sud, est, nord
    bbox = f"{b[1]:.4f},{b[0]:.4f},{b[3]:.4f},{b[2]:.4f}"
    requete = (
        "[out:json][timeout:240];\n(\n"
        f'  nwr["amenity"~"^(hospital|clinic|doctors|dentist|pharmacy)$"]({bbox});\n'
        f'  nwr["healthcare"]({bbox});\n);\nout center tags;'
    )
    (dossier / "requete.overpassql").write_text(requete, encoding="utf-8")

    url_ok = "(réponse en cache)"
    if force or not brut.exists():
        url_ok = requete_overpass(requete, brut)

    reponse = json.loads(brut.read_text(encoding="utf-8"))
    lignes = []
    for el in reponse.get("elements", []):
        if el["type"] == "node":
            lon, lat = el["lon"], el["lat"]
        elif "center" in el:
            lon, lat = el["center"]["lon"], el["center"]["lat"]
        else:
            continue
        t = el.get("tags", {})
        ligne = {"osm_id": f'{el["type"]}/{el["id"]}', "geometry": Point(lon, lat)}
        ligne.update({k.replace(":", "_"): t.get(k) for k in TAGS_SANTE})
        lignes.append(ligne)
    gdf = gpd.GeoDataFrame(lignes, geometry="geometry", crs=C.CRS_GEO).to_crs(CRS_CIBLE)
    n_bbox = len(gdf)
    gdf = gdf[gdf.within(region.geometry.iloc[0])].reset_index(drop=True)

    sortie = dossier / "etablissements_sante.gpkg"
    sortie.unlink(missing_ok=True)
    gdf.to_file(sortie, layer="etablissements_sante", driver="GPKG")
    types = gdf["amenity"].fillna("healthcare=" + gdf["healthcare"].fillna("?"))
    print(f"    {len(gdf)} établissements dans la région ({n_bbox - len(gdf)} hors région écartés)")
    return {
        "titre": "Établissements de santé (hôpitaux, cliniques, médecins, dentistes, pharmacies)",
        "producteur": "Contributeurs OpenStreetMap", "url": url_ok,
        "mode": "automatique (API Overpass)", "licence": C.LICENCES["osm"],
        "crs_origine": C.CRS_GEO, "crs_sortie": CRS_CIBLE,
        "date_donnees_osm": reponse.get("osm3s", {}).get("timestamp_osm_base"),
        "requete": "donnees_brutes/osm_sante/requete.overpassql",
        "fichiers_origine": [info_fichier(brut)], "fichiers_sortie": [info_fichier(sortie)],
        "nb_entites_rectangle": n_bbox, "nb_entites_region": len(gdf),
        "repartition": types.value_counts().head(10).to_dict(),
        "sans_nom_pct": round(100 * gdf["name"].isna().mean(), 1) if len(gdf) else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Étape 3 — Réseau routier de toute la région (extrait OSM Geofabrik)
# ─────────────────────────────────────────────────────────────────────────────
def _extrait_geofabrik(dossier: Path, force: bool) -> tuple[str, Path, str, str]:
    """Couche routes de l'extrait Geofabrik : dossier décompressé ou zip, sinon téléchargement.

    Renvoie (chemin lisible par GDAL, fichier d'origine à hacher, url, date des données).
    """
    import re

    candidats = [] if force else sorted(
        [d for d in dossier.glob("morocco-*-free.shp") if (d / C.GEOFABRIK_COUCHE_ROUTES).exists()]
        + list(dossier.glob("morocco-*-free.shp.zip")), key=lambda p: p.stat().st_mtime)
    url = "(extrait déjà présent)"
    if candidats:
        extrait = candidats[-1]
    else:
        extrait = dossier / "morocco-latest-free.shp.zip"
        url = telecharger([C.GEOFABRIK_MAROC], extrait)  # ~500 Mo
    if extrait.is_dir():
        chemin, origine = str(extrait / C.GEOFABRIK_COUCHE_ROUTES), extrait / C.GEOFABRIK_COUCHE_ROUTES
        readme = (extrait / "README").read_text(encoding="utf-8", errors="replace")
    else:
        chemin, origine = f"zip://{extrait.resolve()}!{C.GEOFABRIK_COUCHE_ROUTES}", extrait
        with zipfile.ZipFile(extrait) as z:
            readme = z.read("README").decode("utf-8", errors="replace")
    date = re.search(r"as of (\S+?)\.?\s", readme)
    return chemin, origine, url, date.group(1) if date else "inconnue"


def etape_routes(force: bool, filtre_routes: str = "complet") -> dict:
    import geopandas as gpd

    dossier = DB / "osm_routes"
    dossier.mkdir(parents=True, exist_ok=True)
    sortie = dossier / "routes_casablanca_settat.gpkg"
    region = region_polygone()
    chemin, origine, url, date_osm = _extrait_geofabrik(dossier, force)
    classes = C.ROUTES_FILTRES[filtre_routes]

    print(f"    lecture {Path(chemin).name} (OSM au {date_osm}), réseau « {filtre_routes} »")
    liste = ", ".join(f"'{c}'" for c in classes)
    routes = gpd.read_file(chemin, bbox=tuple(region.to_crs(C.CRS_GEO).total_bounds),
                           where=f"fclass IN ({liste})")
    crs_origine = routes.crs.to_string()
    n_bbox = len(routes)
    routes = gpd.clip(routes.to_crs(CRS_CIBLE), region).explode(index_parts=False)
    routes = routes[routes.geom_type == "LineString"].reset_index(drop=True)
    routes["longueur_m"] = routes.length.round(1)
    sortie.unlink(missing_ok=True)
    routes.to_file(sortie, layer="troncons", driver="GPKG")
    km = routes["longueur_m"].sum() / 1000
    print(f"    {len(routes):,} tronçons dans la région ({n_bbox:,} dans le rectangle), {km:,.0f} km")
    return {
        "titre": f"Réseau routier circulable (niveau « {filtre_routes} »)",
        "filtre_osm": "fclass ∈ " + ", ".join(classes),
        "producteur": "Contributeurs OpenStreetMap, extrait Geofabrik",
        "url": url, "url_defaut": C.GEOFABRIK_MAROC,
        "date_fichier": datetime.fromtimestamp(origine.stat().st_mtime, timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "automatique (extrait Geofabrik)", "licence": C.LICENCES["osm"],
        "date_donnees_osm": date_osm, "crs_origine": crs_origine, "crs_sortie": CRS_CIBLE,
        "fichiers_origine": [info_fichier(origine)], "fichiers_sortie": [info_fichier(sortie)],
        "nb_troncons": len(routes), "longueur_km": round(km),
        "types_voies": routes["fclass"].value_counts().head(10).to_dict(),
        "avertissement": "Tronçons découpés au contour régional, non topologisés : le graphe "
                         "(nœuds aux intersections, ponts et tunnels via « layer ») se construit "
                         "au pré-traitement (intersession 3).",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Étape 4 — Population 100 m (WorldPop 2020 constrained)
# ─────────────────────────────────────────────────────────────────────────────
def etape_worldpop(force: bool) -> dict:
    import numpy as np
    import rasterio
    from rasterio.mask import mask
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    dossier = DB / "worldpop"
    dossier.mkdir(parents=True, exist_ok=True)
    national = dossier / "mar_ppp_2020_constrained.tif"
    url = "(fichier en cache)"
    if force or not national.exists():
        url = telecharger(C.WORLDPOP_URLS, national)

    region = region_polygone()
    sortie_geo = dossier / "worldpop_2020_casablanca_settat_4326.tif"
    sortie_m = dossier / "worldpop_2020_casablanca_settat_26191.tif"

    with rasterio.open(national) as src:
        nodata = src.nodata if src.nodata is not None else -99999.0
        data, transform = mask(src, list(region.to_crs(src.crs).geometry), crop=True,
                               nodata=nodata)
        profil = src.profile.copy()
        profil.update(height=data.shape[1], width=data.shape[2], transform=transform,
                      nodata=nodata, compress="deflate")
        crs_origine, res = src.crs.to_string(), src.res
    with rasterio.open(sortie_geo, "w", **profil) as dst:
        dst.write(data)
    total_geo = float(np.where(data > 0, data, 0).sum())

    # Reprojection en EPSG:26191 à 100 m. Resampling.sum conserve les effectifs
    # (la population d'un pixel source est répartie, pas moyennée).
    with rasterio.open(sortie_geo) as src:
        tr, w, h = calculate_default_transform(src.crs, CRS_CIBLE, src.width, src.height,
                                               *src.bounds, resolution=100)
        cible = np.full((h, w), nodata, dtype="float32")
        reproject(source=rasterio.band(src, 1), destination=cible, src_transform=src.transform,
                  src_crs=src.crs, src_nodata=nodata, dst_transform=tr, dst_crs=CRS_CIBLE,
                  dst_nodata=nodata, resampling=Resampling.sum)
        p2 = src.profile.copy()
        p2.update(crs=CRS_CIBLE, transform=tr, width=w, height=h, dtype="float32")
    with rasterio.open(sortie_m, "w", **p2) as dst:
        dst.write(cible, 1)
    total_m = float(np.where(cible > 0, cible, 0).sum())
    ecart = 100 * (total_m - total_geo) / total_geo if total_geo else 0.0
    print(f"    population région : {total_geo:,.0f} hab. (reprojection : écart {ecart:+.2f} %)")
    return {
        "titre": "Population maillée 100 m, 2020, version « constrained »",
        "millesime": "2020 (estimation modélisée WorldPop)",
        "producteur": "WorldPop (University of Southampton)", "url": url,
        "url_defaut": C.WORLDPOP_URLS[0],
        "date_fichier": datetime.fromtimestamp(national.stat().st_mtime, timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "automatique", "licence": C.LICENCES["worldpop"],
        "crs_origine": crs_origine, "crs_sortie": f"{CRS_CIBLE} (copie {C.CRS_GEO} conservée)",
        "resolution_origine_deg": [round(r, 6) for r in res], "resolution_sortie_m": 100,
        "fichiers_origine": [info_fichier(national)],
        "fichiers_sortie": [info_fichier(sortie_geo), info_fichier(sortie_m)],
        "population_region_4326": round(total_geo),
        "population_region_26191": round(total_m),
        "ecart_reprojection_pct": round(ecart, 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Étape 5 — Population légale RGPH 2024 (PDF HCP) : import brut des tableaux
# ─────────────────────────────────────────────────────────────────────────────
def etape_hcp(force: bool) -> dict:
    import csv
    import re

    import pdfplumber

    dossier = DB / "hcp"
    dossier.mkdir(parents=True, exist_ok=True)

    def est_pdf(p: Path) -> bool:
        with open(p, "rb") as f:
            return f.read(5) == b"%PDF-"

    pdf = next((p for p in sorted(dossier.glob("*.pdf")) if est_pdf(p)), None)
    mode, url = "automatique", "(fichier en cache)"
    if pdf is None or force:
        cible = dossier / "population_legale_rgph2024.pdf"
        try:
            telecharger([C.HCP_POP_LEGALE_URL], cible, entetes=C.EN_TETES_NAVIGATEUR, essais=2)
            if not est_pdf(cible):
                cible.unlink()
                raise RuntimeError("le serveur a renvoyé une page web, pas le PDF")
            pdf, url = cible, C.HCP_POP_LEGALE_URL
        except Exception as e:
            print(f"    hcp.ma inaccessible par script ({str(e)[:100]})")
            pdf = next((p for p in sorted(dossier.glob("*.pdf")) if est_pdf(p)), None)
            if pdf is None:
                raise RuntimeError("PDF HCP introuvable : téléchargez-le depuis "
                                   f"{C.HCP_POP_LEGALE_PAGE} (fichier PDF des tableaux, pas la "
                                   "note .docx) et déposez-le dans donnees_brutes/hcp/")
            mode = "dépôt manuel (hcp.ma refuse les requêtes automatisées)"

    # Une ligne appartient à la région si son code géographique (dernière colonne)
    # commence par le code HCP de la région : 06, 06.117, 06.117.01.03…
    code_region = re.compile(rf"^{C.CODE_HCP_REGION}(\.\d+)*\.?$")
    pages_txt = dossier / "pages_region_casablanca_settat.txt"
    tableaux_csv = dossier / "tableaux_bruts_region.csv"
    pages, n_lignes, n_communes = [], 0, 0
    with pdfplumber.open(pdf) as doc, \
            open(pages_txt, "w", encoding="utf-8") as ft, \
            open(tableaux_csv, "w", encoding="utf-8", newline="") as fc:
        ecrivain = csv.writer(fc)
        ecrivain.writerow(["page", "tableau", "ligne", "collectivite", "marocains", "etrangers",
                           "population", "menages", "collectivite_ar", "code_geographique"])
        nb_pages = len(doc.pages)
        for i, page in enumerate(doc.pages, start=1):
            lignes_page = []
            for t, tab in enumerate(page.extract_tables() or [], start=1):
                for l, ligne in enumerate(tab, start=1):
                    cellules = [(c or "").replace("\n", " ").strip() for c in ligne]
                    if cellules and code_region.match(cellules[-1]):
                        lignes_page.append([i, t, l] + cellules)
            if not lignes_page:
                continue
            pages.append(i)
            ft.write(f"\n===== page {i} =====\n{page.extract_text() or ''}\n")
            ecrivain.writerows(lignes_page)
            n_lignes += len(lignes_page)
            n_communes += sum(1 for x in lignes_page if x[3].startswith("Commune"))
    print(f"    {len(pages)} pages concernant la région, {n_lignes} lignes extraites "
          f"dont {n_communes} communes")
    return {
        "titre": "Population légale RGPH 2024 (régions, provinces, communes)",
        "millesime": "RGPH 2024 (population au 1er septembre 2024, décret n° 2.24.1009)",
        "producteur": "Haut-Commissariat au Plan (HCP)", "url": url, "mode": mode,
        "url_defaut": C.HCP_POP_LEGALE_URL,
        "date_fichier": datetime.fromtimestamp(pdf.stat().st_mtime, timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "licence": C.LICENCES["hcp_pop"], "crs_origine": "sans objet (tableau)",
        "crs_sortie": "sans objet",
        "fichiers_origine": [info_fichier(pdf)],
        "fichiers_sortie": [info_fichier(pages_txt), info_fichier(tableaux_csv)],
        "nb_pages_pdf": nb_pages, "pages_region": pages, "lignes_tableaux_brutes": n_lignes,
        "nb_lignes_communes": n_communes,
        "avertissement": "Import brut (nombres au format texte « 1,234 ») : la conversion et "
                         "la jointure aux communes relèvent du pré-traitement (intersession 3).",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Documentation générée : README de provenance + SOURCES.md
# ─────────────────────────────────────────────────────────────────────────────
ORDRE = ["limites", "sante", "routes", "worldpop", "hcp"]


def ecrire_documentation(m: dict) -> None:
    lignes = [
        "# Données brutes — README de provenance",
        "",
        "Ce fichier est **généré par `scripts/collecte.py`** à chaque exécution : ne pas le "
        "modifier à la main. La version machine est `manifest.json`.",
        "",
        f"- Projet : {m['projet']}",
        f"- Dernière collecte : {m.get('derniere_collecte', '?')}",
        f"- CRS de toutes les couches produites : **{m['crs_cible']}** (Merchich / Nord Maroc)",
        "- Rejouer : `python scripts/collecte.py` (cache réutilisé) ou `--force` (tout retélécharger)",
        "- Les fichiers volumineux ne sont pas versionnés (limite GitHub) : leur SHA-256 "
        "ci-dessous permet de vérifier qu'un nouveau téléchargement est identique.",
        "",
        "## Arborescence",
        "",
        "```",
        "donnees_brutes/",
        "├── limites/     overpass_communes.json → limites_casablanca_settat.gpkg (region, communes)",
        "├── osm_sante/   requete.overpassql, overpass_reponse.json → etablissements_sante.gpkg",
        "├── osm_routes/  extrait Geofabrik (morocco-*-free.shp) → routes_casablanca_settat.gpkg",
        "├── worldpop/    raster national → découpes 4326 et 26191",
        "├── hcp/         PDF RGPH 2024 → pages et lignes de la région (code 06…)",
        "├── manifest.json",
        "└── README.md",
        "```",
    ]
    for cle in ORDRE:
        s = m["sources"].get(cle)
        if not s:
            continue
        lignes += ["", f"## {s.get('titre', cle)}", ""]
        if s.get("statut") == "ECHEC":
            lignes.append(f"- **Statut : échec** — {s.get('erreur')}")
            continue
        for k in ("producteur", "url", "mode", "licence", "date_telechargement",
                  "date_collecte", "crs_origine",
                  "crs_sortie", "avertissement"):
            if s.get(k):
                lignes.append(f"- **{k.replace('_', ' ')}** : {s[k]}")
        for k, v in s.items():
            if k.startswith(("nb_", "population", "longueur", "surface", "ecart", "sans_nom",
                             "provinces", "pages_region", "lignes", "repartition", "types",
                             "date_donnees", "emprise")):
                lignes.append(f"- {k.replace('_', ' ')} : {v}")
        lignes += ["", "| Fichier | Rôle | Taille (Mo) | SHA-256 |", "| --- | --- | --- | --- |"]
        for role, cle_f in (("origine", "fichiers_origine"), ("produit", "fichiers_sortie")):
            for f in s.get(cle_f, []):
                lignes.append(f"| `{f['chemin']}` | {role} | {f['taille_mo']} | "
                              f"`{f['sha256'][:16]}…` |")
    (DB / "README.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    ecrire_sources(m)


# Couche de référence de chaque source, pour mesurer son emprise réelle
COUCHE_EMPRISE = {
    "limites": ("limites/limites_casablanca_settat.gpkg", "region"),
    "sante": ("osm_sante/etablissements_sante.gpkg", "etablissements_sante"),
    "routes": ("osm_routes/routes_casablanca_settat.gpkg", "troncons"),
    "worldpop": ("worldpop/worldpop_2020_casablanca_settat_26191.tif", None),
}


def emprise(cle: str):
    """Emprise du fichier produit : (xmin, ymin, xmax, ymax) en EPSG:26191 et en EPSG:4326."""
    if cle not in COUCHE_EMPRISE or not (DB / COUCHE_EMPRISE[cle][0]).exists():
        return None
    from pyproj import Transformer

    chemin, couche = COUCHE_EMPRISE[cle]
    if couche is None:
        import rasterio
        with rasterio.open(DB / chemin) as r:
            b = tuple(r.bounds)
    else:
        import pyogrio
        b = pyogrio.read_info(DB / chemin, layer=couche, force_total_bounds=True)["total_bounds"]
    geo = Transformer.from_crs(CRS_CIBLE, C.CRS_GEO, always_xy=True).transform_bounds(*b)
    return [round(v) for v in b], [round(v, 4) for v in geo]


def _n(v) -> str:
    return f"{v:,}".replace(",", " ") if isinstance(v, (int, float)) else str(v)


def volume(cle: str, s: dict) -> str:
    return {
        "limites": f"{_n(s.get('nb_communes'))} communes, "
                   f"{len(s.get('provinces_retenues', []))} provinces/préfectures",
        "sante": f"{_n(s.get('nb_entites_region'))} établissements",
        "routes": f"{_n(s.get('nb_troncons'))} tronçons, {_n(s.get('longueur_km'))} km",
        "worldpop": f"{_n(s.get('population_region_26191'))} hab. (pixels de 100 m)",
        "hcp": f"{_n(s.get('lignes_tableaux_brutes'))} lignes, dont "
               f"{_n(s.get('nb_lignes_communes'))} communes",
    }.get(cle, "—")


def millesime(s: dict) -> str:
    if s.get("millesime"):
        return s["millesime"]
    return f"OSM au {s['date_donnees_osm'][:10]}" if s.get("date_donnees_osm") else "—"


def ecrire_sources(m: dict) -> None:
    lim = emprise("limites")
    t = ["# SOURCES.md — Inventaire des sources", "",
         "Généré par `scripts/collecte.py` à partir de `donnees_brutes/manifest.json` : ne pas "
         "modifier à la main. Les empreintes SHA-256 des fichiers sont dans "
         "`donnees_brutes/README.md`.", "",
         "- **Zone d'étude** : région Casablanca-Settat (code géographique HCP 06), contour = "
         "union des communes" + (f", {_n(round(m['sources']['limites']['surface_region_km2']))} km²"
                                 if lim else ""),
         f"- **CRS de toutes les couches produites** : {m['crs_cible']} (Merchich / Nord Maroc, "
         "en mètres)",
         "- **Emprise** : rectangle englobant de chaque couche produite, mesuré sur le fichier "
         "(xmin, ymin, xmax, ymax)",
         f"- **Dernière collecte** : {m.get('derniere_collecte', '?')}",
         "- **Rejouer** : `python scripts/collecte.py` puis `python scripts/controle_collecte.py`",
         "", "## Synthèse", "",
         "| # | Donnée | Producteur | Licence | Millésime | Téléchargée le | CRS origine → produit "
         "| Emprise (km) | Volume |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    details = ["", "## Détail par source"]
    for i, cle in enumerate(ORDRE, start=1):
        s = m["sources"].get(cle)
        if not s:
            continue
        if s.get("statut") == "ECHEC":
            t.append(f"| {i} | {cle} | — | — | — | — | — | — | échec : "
                     f"{str(s.get('erreur', ''))[:80]} |")
            continue
        e = emprise(cle)
        if e:
            (x0, y0, x1, y1), (o, su, es, n) = e
            taille = f"{(x1 - x0) / 1000:.0f} × {(y1 - y0) / 1000:.0f}"
            txt_emprise = (f"EPSG:26191 : {_n(x0)}, {_n(y0)}, {_n(x1)}, {_n(y1)} m — "
                           f"EPSG:4326 : {o}, {su}, {es}, {n} (ouest, sud, est, nord)")
        else:
            taille = "région (tableau)"
            txt_emprise = ("tableau sans géométrie, limité à la région (codes 06…) ; il prend "
                           "l'emprise des communes par jointure sur le code géographique")
        crs = f"{s.get('crs_origine', '')} → {s.get('crs_sortie', '')}"
        t.append(f"| {i} | {s['titre']} | {s['producteur']} | {s['licence']} | {millesime(s)} | "
                 f"{str(s.get('date_telechargement', ''))[:10]} | {crs} | {taille} | "
                 f"{volume(cle, s)} |")
        details += ["", f"### {i}. {s['titre']}", "",
                    f"- **URL** : {s['url']}",
                    f"- **Mode d'acquisition** : {s.get('mode', '')}",
                    f"- **Producteur** : {s['producteur']}",
                    f"- **Licence** : {s['licence']}",
                    f"- **Millésime des données** : {millesime(s)}",
                    f"- **Téléchargée le** : {s.get('date_telechargement', '')} — "
                    f"**collectée le** : {s.get('date_collecte', '')}",
                    f"- **CRS** : origine {s.get('crs_origine', '')} → produit "
                    f"{s.get('crs_sortie', '')}",
                    f"- **Emprise** : {txt_emprise}",
                    f"- **Volume** : {volume(cle, s)}"]
        if s.get("requete") or s.get("filtre_osm"):
            details.append(f"- **Sélection** : {s.get('requete') or s.get('filtre_osm')}")
        details.append("- **Fichiers produits** : " +
                       ", ".join(f"`{f['chemin']}`" for f in s.get("fichiers_sortie", [])))
        if s.get("avertissement"):
            details.append(f"- **Remarque** : {s['avertissement']}")
    (C.RACINE / "SOURCES.md").write_text("\n".join(t + details) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--etapes", nargs="+", choices=ORDRE, default=ORDRE)
    p.add_argument("--force", action="store_true", help="retélécharger même si le cache existe")
    p.add_argument("--routes", choices=list(C.ROUTES_FILTRES), default="complet",
                   help="complet = toutes voies circulables et pistes ; principal = sans voies "
                        "résidentielles, de service ni pistes")
    a = p.parse_args()

    fonctions = {"limites": etape_limites, "sante": etape_sante,
                 "routes": lambda f: etape_routes(f, a.routes),
                 "worldpop": etape_worldpop, "hcp": etape_hcp}
    m = charger_manifest()
    t_total = time.time()
    for nom in [e for e in ORDRE if e in a.etapes]:
        print(f"\n[{nom}]")
        t0 = time.time()
        precedent = m["sources"].get(nom, {})
        try:
            s = fonctions[nom](a.force)
            s.update({"statut": "OK", "date_collecte": maintenant(),
                      "duree_s": round(time.time() - t0, 1)})
            # Cache réutilisé : on garde l'URL et la date du téléchargement réel
            url_defaut, date_fichier = s.pop("url_defaut", None), s.pop("date_fichier", None)
            if str(s.get("url", "")).startswith("("):
                s["mode"] = f"{s.get('mode', '')} — cache local réutilisé".strip(" —")
                s["url"] = precedent.get("url") if str(precedent.get("url", "")).startswith(
                    "http") else (url_defaut or s["url"])
                # La date du fichier sur disque fait foi ; à défaut, celle du manifeste
                anterieure = precedent.get("date_telechargement")
                s["date_telechargement"] = (date_fichier or (anterieure if anterieure != "inconnue"
                                                             else None) or "inconnue")
            else:
                s["date_telechargement"] = s["date_collecte"]
            print(f"  OK ({s['duree_s']} s)")
        except Exception as e:
            s = {"statut": "ECHEC", "erreur": f"{type(e).__name__}: {e}",
                 "date_collecte": maintenant(), "titre": nom}
            print(f"  ÉCHEC : {e}")
        m["sources"][nom] = s
        m["derniere_collecte"] = maintenant()
        MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str),
                            encoding="utf-8")
        ecrire_documentation(m)

    ok = [k for k, v in m["sources"].items() if v.get("statut") == "OK"]
    print(f"\n{len(ok)}/{len(m['sources'])} sources collectées en {time.time() - t_total:.0f} s "
          f"— voir donnees_brutes/README.md")
    sys.exit(0 if len(ok) == len(m["sources"]) else 1)


if __name__ == "__main__":
    main()
