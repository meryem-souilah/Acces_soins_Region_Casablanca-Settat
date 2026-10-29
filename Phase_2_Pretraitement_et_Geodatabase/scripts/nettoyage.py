"""
nettoyage.py — Nettoyage et mise au format de la géodatabase

Lit les couches brutes produites par collecte.py, applique des règles de nettoyage
EXPLICITES et TRACÉES, et écrit des couches dont les colonnes correspondent exactement
aux tables de sql/schema.sql (prêtes pour l'import PostGIS).

Étapes (dans l'ordre) :
    communes        communes HCP : renommage, géométries valides, provinces dérivées
    etablissements  tags OSM → type → niveau par défaut, corrections de relecture,
                    attributs normalisés, doublons, commune d'appartenance
    routes          tronçons et nœuds : type de voie, vitesse, sens unique,
                    boucles, doublons, nœuds orphelins
    h3              grille H3 résolution 8 : population WorldPop + commune

Entrées  : donnees_brutes/...                 (collecte.py)
           corrections/niveaux_relecture.csv  (facultatif, rempli à la main)
Sorties  : donnees_propres/base_sante.gpkg    une couche par table du schéma
           corrections/a_relire_hopitaux.csv  liste à relire (générée)
           preuves/rapport_nettoyage.md       rapport avant / après
           preuves/journal_nettoyage.csv      une ligne par entité modifiée ou écartée

Usage :
    python scripts/nettoyage.py --dry-run                 # simulation : rapport seul
    python scripts/nettoyage.py                           # tout, écrit le GeoPackage
    python scripts/nettoyage.py --etapes etablissements --dry-run
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402  (avant geopandas : correctif PROJ)

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DB = C.DONNEES_BRUTES
PROPRES = C.RACINE / "donnees_propres"
CORRECTIONS = C.RACINE / "corrections"
SORTIE = PROPRES / "base_sante.gpkg"
CRS = C.CRS_METRIQUE
ORDRE = ["communes", "etablissements", "routes", "h3"]

# ─────────────────────────────────────────────────────────────────────────────
# Règles métier (modifiables ici, reprises dans le rapport)
# ─────────────────────────────────────────────────────────────────────────────
# Préfectures de la région ; les autres entités ADM2 sont des provinces.
PREFECTURES = ["casablanca", "mohammedia"]

# Niveau par défaut de chaque type : identique à type_etablissement.niveau_defaut
NIVEAU_DEFAUT = {"hopital": 2, "clinique": 2, "centre_sante": 1, "medecin": 1,
                 "dentiste": 1, "pharmacie": 1, "autre": 1}

# Motifs cherchés dans le nom (déjà mis en minuscules et sans accents par normaliser()).
# Le nom est testé AVANT le tag OSM : dans OSM, beaucoup de centres de santé et de
# cliniques sont tagués amenity=hospital.
MOTIF_PHARMACIE = re.compile(r"pharmacie|pharmacy|صيدلية")
MOTIF_DENTISTE = re.compile(r"dentaire|dentiste|dental|طب الاسنان")
MOTIF_AUTRE = re.compile(r"laborato|\blabo\b|analyses|\bkine|hemodialyse|dialyse|"
                         r"institut pasteur|radiologie|مختبر|باستور")
MOTIF_CENTRE = re.compile(r"centre (de )?sante|dispensaire|disponsaire|\bcs[ura]?\b|"
                          r"مركز (ال)?صحي|مستوصف")
MOTIF_HOPITAL = re.compile(r"hopital|hospital|centre hospitalier|\bchu\b|\bchp\b|\bchr\b|"
                           r"مستشفى|استشفائي")
MOTIF_CLINIQUE = re.compile(r"clinique|clinic|polyclinique|مصحة")
# Indice d'un niveau 3 : proposé dans la liste à relire, JAMAIS appliqué seul
MOTIF_NIVEAU3 = re.compile(r"\bchu\b|universitaire|regional|ibn rochd|20 aout|cheikh khalifa|mohammed vi|"
                           r"الجامعي|الجهوي")

# Doublons OSM : un même lieu saisi en point ET en polygone
DOUBLON_DISTANCE_M = 50

# Vitesses par défaut (km/h) quand maxspeed est absent — hypothèse documentée
VITESSE_DEFAUT = {"motorway": 120, "trunk": 100, "primary": 80, "secondary": 70,
                  "tertiary": 60, "unclassified": 50, "residential": 40,
                  "living_street": 20, "service": 20, "road": 40, "unknown": 30,
                  "track": 20}   # pistes : souvent le seul accès aux douars
VITESSE_LIEN = 50  # *_link (bretelles)
# Voies non circulables en voiture : retirées du graphe
VOIES_EXCLUES = {"footway", "path", "steps", "cycleway", "bridleway", "pedestrian"}
# Précision du rapprochement des sommets (m) pour reconnaître un point OSM partagé
ARRONDI_SOMMET_M = 0.01

H3_RESOLUTION = 8


# ─────────────────────────────────────────────────────────────────────────────
# Outils : normalisation, journal, rapport
# ─────────────────────────────────────────────────────────────────────────────
def normaliser(txt) -> str:
    if txt is None or (isinstance(txt, float) and np.isnan(txt)):
        return ""
    t = unicodedata.normalize("NFKD", str(txt))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().replace("-", " ").replace("_", " ").replace("'", " ").split())


def vide(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in ("", "None", "nan")


class Trace:
    """Journal ligne à ligne + tableaux avant/après pour le rapport."""

    def __init__(self):
        self.journal: list[dict] = []
        self.sections: list[tuple[str, list[str]]] = []

    def log(self, couche, ident, regle, avant="", apres=""):
        self.journal.append({"couche": couche, "id": ident, "regle": regle,
                             "avant": avant, "apres": apres})

    def section(self, titre, lignes):
        self.sections.append((titre, lignes))


def tableau(entetes, lignes):
    out = ["| " + " | ".join(entetes) + " |", "|" + " --- |" * len(entetes)]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in lignes]
    return out


def lire(fichier: Path, couche: str):
    if not fichier.exists():
        raise RuntimeError(f"fichier absent : {fichier} — lancez d'abord la collecte de cette source")
    return gpd.read_file(fichier, layer=couche)


# ─────────────────────────────────────────────────────────────────────────────
# Étape 1 — Communes et provinces
# ─────────────────────────────────────────────────────────────────────────────
def _colonne(df, prefixe, suffixes):
    for s in suffixes:
        for c in df.columns:
            if c.upper() == f"{prefixe}_{s}":
                return c
    return None


# Noms des provinces et préfectures selon leur code HCP (région 06, découpage 2015).
# Sert quand la couche communes ne porte que le code de province.
# À VÉRIFIER avec la commande du guide : nom des communes de chaque code.
PROVINCES_NOMS = {
    "06.111": "Benslimane", "06.117": "Berrechid", "06.141": "Casablanca",
    "06.181": "El Jadida", "06.355": "Médiouna", "06.371": "Mohammedia",
    "06.385": "Nouaceur", "06.461": "Settat", "06.467": "Sidi Bennour",
}


def _communes_hdx(brut):
    """Format HDX (COD-AB) : ADM3_PCODE, ADM3_FR, ADM2_PCODE, ADM2_FR."""
    c_code = _colonne(brut, "ADM3", ["PCODE"])
    c_nom = _colonne(brut, "ADM3", ["FR", "EN", "REF", "AR"])
    p_code = _colonne(brut, "ADM2", ["PCODE"])
    p_nom = _colonne(brut, "ADM2", ["FR", "EN", "REF", "AR"])
    if None in (c_code, c_nom, p_code, p_nom):
        return None
    g = brut.rename(columns={c_code: "code_hcp", c_nom: "nom", p_code: "code_province",
                             p_nom: "nom_province"})
    return g, "HDX (COD-AB)"


def _communes_normalisees(brut):
    """Format déjà aligné sur le schéma (collecte OSM) : code_hcp, code_province, nom."""
    if not {"code_hcp", "code_province", "nom"} <= set(brut.columns):
        return None
    g = brut.copy()
    inconnus = sorted(set(g["code_province"].astype(str)) - set(PROVINCES_NOMS))
    if inconnus:
        raise RuntimeError(f"codes de province sans nom dans PROVINCES_NOMS : {inconnus}")
    g["nom_province"] = g["code_province"].astype(str).map(PROVINCES_NOMS)
    return g, "colonnes déjà normalisées (code_hcp, code_province, nom)"


def etape_communes(t: Trace, res: dict):
    brut = lire(DB / "limites" / "limites_casablanca_settat.gpkg", "communes")
    n0 = len(brut)
    lu = _communes_hdx(brut) or _communes_normalisees(brut)
    if lu is None:
        raise RuntimeError("format de la couche communes non reconnu — colonnes présentes : "
                           f"{list(brut.columns)}")
    g, format_source = lu
    for col in ("code_hcp", "code_province", "nom"):
        vides = g[col].isna() | (g[col].astype(str).str.strip() == "")
        if vides.any():
            raise RuntimeError(f"{int(vides.sum())} communes sans « {col} » : à corriger à la source")

    g = g.to_crs(CRS)
    invalides = ~g.geometry.is_valid
    for i in g.index[invalides]:
        t.log("commune", g.at[i, "code_hcp"], "géométrie invalide corrigée (make_valid)")
    g["geometry"] = g.geometry.make_valid()
    # make_valid peut produire des collections : on ne garde que les polygones
    g["geometry"] = g.geometry.apply(_polygones)
    vides = g.geometry.is_empty | g.geometry.isna()
    for i in g.index[vides]:
        t.log("commune", g.at[i, "code_hcp"], "écartée : géométrie vide après correction")
    g = g[~vides]

    doublons = g["code_hcp"].duplicated(keep=False)
    if doublons.any():
        # même code sur plusieurs morceaux : on fusionne (une commune = une ligne)
        for code in g.loc[doublons, "code_hcp"].unique():
            t.log("commune", code, "morceaux de même code fusionnés")
        g = g.dissolve(by="code_hcp", as_index=False, aggfunc="first")

    commune = gpd.GeoDataFrame({
        "code_hcp": g["code_hcp"].astype(str),
        "nom": g["nom"].astype(str).str.strip(),
        "pop_2024": pd.array([pd.NA] * len(g), dtype="Int64"),
        "code_province": g["code_province"].astype(str),
    }, geometry=g.geometry.apply(_multi).values, crs=CRS)

    prov = g.dissolve(by="code_province", as_index=False, aggfunc="first")
    province = gpd.GeoDataFrame({
        "code_province": prov["code_province"].astype(str),
        "nom": prov["nom_province"].astype(str).str.strip(),
        "type_province": [("prefecture" if any(p in normaliser(n) for p in PREFECTURES)
                           else "province") for n in prov["nom_province"]],
    }, geometry=prov.geometry.make_valid().apply(_polygones).apply(_multi).values, crs=CRS)

    res["province"], res["commune"] = province, commune
    nb = commune.groupby("code_province").size()
    t.section("Communes et provinces", [
        f"Format de la couche source : {format_source}.", "",
        *tableau(["Contrôle", "Avant", "Après"], [
            ("Communes", n0, len(commune)),
            ("Géométries invalides", int(invalides.sum()), int((~commune.geometry.is_valid).sum())),
            ("Codes communaux en double", int(doublons.sum()), int(commune.code_hcp.duplicated().sum())),
            ("Provinces / préfectures dérivées", "—", len(province)),
        ]), "",
        *tableau(["Code", "Province", "Type", "Communes"],
                 [(c, n, ty, int(nb.get(c, 0))) for c, n, ty in
                  zip(province.code_province, province.nom, province.type_province)]), "",
        "`pop_2024` reste vide : la jointure avec les tableaux HCP est une étape à part "
        "(appariement des noms de communes).",
    ])


def _polygones(geom):
    from shapely.geometry import MultiPolygon, Polygon
    if geom is None or geom.is_empty:
        return geom
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    parts = [p for p in getattr(geom, "geoms", []) if isinstance(p, (Polygon, MultiPolygon))]
    polys = []
    for p in parts:
        polys.extend(p.geoms if isinstance(p, MultiPolygon) else [p])
    return MultiPolygon(polys) if polys else Polygon()


def _multi(geom):
    from shapely.geometry import MultiPolygon, Polygon
    return MultiPolygon([geom]) if isinstance(geom, Polygon) else geom


# ─────────────────────────────────────────────────────────────────────────────
# Étape 2 — Établissements de santé
# ─────────────────────────────────────────────────────────────────────────────
def classer(row) -> tuple[str, str]:
    """(code_type, règle appliquée) à partir du nom puis des tags OSM.

    Ordre : un nom explicite l'emporte sur le tag, car le tag amenity=hospital est
    souvent posé sur des centres de santé, des cliniques, voire des pharmacies.
    Un nom d'hôpital est testé avant un nom de clinique (« clinique Fedala - مستشفى
    مولاي عبد الله » est l'hôpital Moulay Abdellah).
    """
    am = normaliser(row.get("amenity"))
    hc = normaliser(row.get("healthcare"))
    nom = normaliser(" ".join(str(row.get(k) or "") for k in ("name", "name_fr", "name_ar")))
    # 1. le nom, quand il est explicite
    if MOTIF_PHARMACIE.search(nom):
        return "pharmacie", "nom de pharmacie"
    if MOTIF_DENTISTE.search(nom):
        return "dentiste", "nom de cabinet dentaire"
    if MOTIF_AUTRE.search(nom):
        return "autre", "nom de laboratoire, kiné, dialyse… (hors analyse)"
    if MOTIF_CENTRE.search(nom):
        return "centre_sante", "nom de centre de santé / dispensaire"
    if MOTIF_HOPITAL.search(nom):
        return "hopital", "nom d'hôpital"
    if MOTIF_CLINIQUE.search(nom):
        return "clinique", "nom de clinique"
    # 2. sinon, les tags OSM
    if am == "pharmacy" or hc == "pharmacy":
        return "pharmacie", "tag pharmacy"
    if am == "dentist" or hc == "dentist":
        return "dentiste", "tag dentist"
    if am == "hospital" or hc == "hospital":
        return "hopital", "tag hospital"
    if hc == "centre":
        return "centre_sante", "tag healthcare=centre"
    if am == "clinic" or hc == "clinic":
        return "clinique", "tag clinic"
    if am == "doctors" or hc == "doctor":
        return "medecin", "tag doctors"
    return "autre", f"non classé (amenity={am or '—'}, healthcare={hc or '—'})"


def _secteur(row):
    v = normaliser(row.get("operator_type"))
    if v in ("public", "government", "governmental", "state"):
        return "public"
    if v in ("private", "prive", "privee"):
        return "prive"
    if v in ("ngo", "association", "charity", "religious", "community"):
        return "associatif"
    op = normaliser(row.get("operator"))
    if "ministere" in op or "ministry" in op or "وزارة" in op:
        return "public"
    return None


def _entier(v):
    m = re.search(r"\d+", str(v)) if not vide(v) else None
    return int(m.group()) if m else None


def _booleen(v):
    v = normaliser(v)
    if v in ("yes", "true", "1", "oui"):
        return True
    if v in ("no", "false", "0", "non"):
        return False
    return None


def _remplissage(df, cols):
    return sum((~df[c].isna()).astype(int) for c in cols)


def etape_etablissements(t: Trace, res: dict):
    brut = lire(DB / "osm_sante" / "etablissements_sante.gpkg", "etablissements_sante")
    brut = brut.to_crs(CRS)
    n0 = len(brut)
    e = brut.copy()

    # 1. Géométrie : points non vides
    mauvais = e.geometry.isna() | e.geometry.is_empty | (e.geom_type != "Point")
    for i in e.index[mauvais]:
        t.log("etablissement", e.at[i, "osm_id"], "écarté : géométrie absente ou non ponctuelle")
    e = e[~mauvais]

    # 2. Type et niveau par défaut
    cl = e.apply(classer, axis=1, result_type="expand")
    e["code_type"], e["regle_type"] = cl[0], cl[1]
    e["code_niveau"] = e["code_type"].map(NIVEAU_DEFAUT).astype(int)
    e["niveau_source"] = "defaut_type"
    tag_seul = e.apply(lambda r: classer({"amenity": r.get("amenity"), "healthcare": r.get("healthcare")})[0], axis=1)
    differe = (e["code_type"] != tag_seul) & e["regle_type"].str.startswith("nom")
    for i in e.index[differe]:
        t.log("etablissement", e.at[i, "osm_id"], "type déduit du nom (contredit le tag)",
              f"{tag_seul[i]} (amenity={e.at[i, 'amenity']})", f"{e.at[i, 'code_type']} : {e.at[i, 'name']}")
    for i in e.index[e["code_type"] == "autre"]:
        t.log("etablissement", e.at[i, "osm_id"], "type « autre » (hors analyse)",
              e.at[i, "regle_type"], "autre")

    # 3. Attributs normalisés
    e["nom"] = [next((str(r[k]).strip() for k in ("name_fr", "name", "name_ar") if not vide(r.get(k))), None)
                for _, r in e.iterrows()]
    e["secteur"] = e.apply(_secteur, axis=1)
    e["nb_lits"] = e["beds"].map(_entier) if "beds" in e else None
    e["urgences"] = e["emergency"].map(_booleen) if "emergency" in e else None

    # 4. Doublons point / polygone
    avant_doublons = len(e)
    e, n_paires = _doublons(e, t)
    n_suppr = avant_doublons - len(e)

    # 5. Hors région (contrôle : collecte.py a déjà découpé)
    region = lire(DB / "limites" / "limites_casablanca_settat.gpkg", "region").to_crs(CRS)
    dedans = e.within(region.geometry.union_all().buffer(50))
    for i in e.index[~dedans]:
        t.log("etablissement", e.at[i, "osm_id"], "écarté : hors région")
    e = e[dedans]

    # 6. Commune d'appartenance (ST_Within, sinon commune la plus proche)
    commune = res.get("commune")
    if commune is None:
        commune = _communes_propres()
    j = gpd.sjoin(e, commune[["code_hcp", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    e["code_hcp"] = j["code_hcp"]
    hors = e["code_hcp"].isna()
    if hors.any():
        proche = gpd.sjoin_nearest(e[hors][["osm_id", "geometry"]], commune[["code_hcp", "geometry"]],
                                   how="left", distance_col="dist_m")
        proche = proche[~proche.index.duplicated(keep="first")]
        e.loc[hors, "code_hcp"] = proche["code_hcp"]
        for i, r in proche.iterrows():
            t.log("etablissement", r["osm_id"], "commune la plus proche (point hors de toute commune)",
                  "", f"{r['code_hcp']} à {r['dist_m']:.0f} m")

    # 7. Corrections de relecture (niveaux) et liste à relire
    n_corr = _appliquer_relecture(e, t)
    _liste_a_relire(e, commune)

    etab = gpd.GeoDataFrame(e[["osm_id", "nom", "secteur", "nb_lits", "urgences", "code_type",
                               "code_niveau", "niveau_source", "code_hcp"]].copy(),
                            geometry=e.geometry, crs=CRS).reset_index(drop=True)
    etab["nb_lits"] = etab["nb_lits"].astype("Int64")
    etab["urgences"] = etab["urgences"].astype("boolean")
    res["etablissement"] = etab

    rep_type = etab.groupby(["code_type", "code_niveau"]).size().reset_index(name="n")
    remplis = {c: f"{100 * etab[c].notna().mean():.0f} %" for c in ("nom", "secteur", "nb_lits", "urgences")}
    t.section("Établissements de santé", [
        *tableau(["Contrôle", "Avant", "Après"], [
            ("Entités", n0, len(etab)),
            ("Géométries absentes ou non ponctuelles", int(mauvais.sum()), 0),
            ("Paires de doublons point / polygone fusionnées", "—", n_paires),
            ("Entités supprimées comme doublons", "—", n_suppr),
            ("Hors région", int((~dedans).sum()), 0),
            ("Sans commune par inclusion (rattachées à la plus proche)", int(hors.sum()), 0),
            ("Niveaux corrigés par relecture", "—", n_corr),
        ]), "",
        "**Répartition par type et niveau**", "",
        *tableau(["Type", "Niveau", "Nombre"], rep_type.values.tolist()), "",
        "**Taux de remplissage des attributs** : " +
        ", ".join(f"`{k}` {v}" for k, v in remplis.items()) + ".",
    ])


def _doublons(e, t):
    """Même lieu saisi deux fois (point + polygone) : on garde la fiche la plus complète
    et on complète ses attributs vides avec ceux de l'autre."""
    e = e.reset_index(drop=True)
    attrs = ["nom", "secteur", "nb_lits", "urgences"]
    e["_score"] = _remplissage(e, attrs) + e["osm_id"].str.startswith(("way", "relation")).astype(int) * 0.5
    proches = gpd.sjoin(e[["code_type", "geometry"]],
                        e[["code_type", "geometry"]].set_geometry(e.geometry.buffer(DOUBLON_DISTANCE_M)),
                        predicate="within")
    proches = proches[(proches.index < proches["index_right"]) &
                      (proches["code_type_left"] == proches["code_type_right"])]
    supprimer, n = set(), 0
    for a, b in zip(proches.index, proches["index_right"]):
        if a in supprimer or b in supprimer:
            continue
        na, nb = normaliser(e.at[a, "nom"]), normaliser(e.at[b, "nom"])
        if na and nb and na != nb and na not in nb and nb not in na:
            continue  # deux lieux distincts côte à côte (ex. deux cabinets)
        garde, jette = (a, b) if e.at[a, "_score"] >= e.at[b, "_score"] else (b, a)
        for c in attrs:
            if vide(e.at[garde, c]) and not vide(e.at[jette, c]):
                e.at[garde, c] = e.at[jette, c]
        supprimer.add(jette)
        n += 1
        t.log("etablissement", e.at[jette, "osm_id"], "doublon supprimé",
              f"à moins de {DOUBLON_DISTANCE_M} m de", e.at[garde, "osm_id"])
    return e.drop(index=list(supprimer)).drop(columns="_score"), n


def _appliquer_relecture(e, t) -> int:
    f = CORRECTIONS / "niveaux_relecture.csv"
    if not f.exists():
        return 0
    corr = pd.read_csv(f, sep=None, engine="python", dtype=str).fillna("")
    if not {"osm_id", "code_niveau"} <= set(corr.columns):
        raise RuntimeError(f"{f.name} doit contenir les colonnes osm_id et code_niveau")
    corr = corr[corr["code_niveau"].str.strip() != ""]
    idx = {o: i for i, o in zip(e.index, e["osm_id"])}
    n = 0
    for _, r in corr.iterrows():
        i = idx.get(r["osm_id"].strip())
        if i is None:
            print(f"    relecture : {r['osm_id']} introuvable (supprimé comme doublon ?)")
            continue
        nouveau = int(r["code_niveau"])
        if nouveau not in (1, 2, 3):
            raise RuntimeError(f"niveau {nouveau} invalide pour {r['osm_id']}")
        ancien = int(e.at[i, "code_niveau"])
        e.at[i, "code_niveau"], e.at[i, "niveau_source"] = nouveau, "relecture"
        n += 1
        t.log("etablissement", r["osm_id"], "niveau corrigé par relecture", ancien,
              f"{nouveau} — {r.get('justification', '')}")
    return n


def _liste_a_relire(e, commune):
    """Hôpitaux et cliniques : niveau proposé, à confirmer à la main."""
    CORRECTIONS.mkdir(exist_ok=True)
    h = e[e["code_type"].isin(["hopital", "clinique"])].copy()
    noms = commune.set_index("code_hcp")["nom"]
    lignes = []
    for _, r in h.sort_values(["code_type", "nom"], na_position="last").iterrows():
        indice = MOTIF_NIVEAU3.search(normaliser(r["nom"]))
        lignes.append({"osm_id": r["osm_id"], "nom": r["nom"] or "", "type": r["code_type"],
                       "commune": noms.get(r["code_hcp"], ""), "nb_lits": "" if pd.isna(r["nb_lits"]) else int(r["nb_lits"]),
                       "secteur": r["secteur"] or "", "niveau_actuel": int(r["code_niveau"]),
                       "niveau_propose": 3 if indice else "",
                       "indice": indice.group() if indice else ""})
    with open(CORRECTIONS / "a_relire_hopitaux.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]) if lignes else ["osm_id"], delimiter=";")
        w.writeheader()
        w.writerows(lignes)


def _communes_propres():
    """Communes nettoyées : celles du GeoPackage, sinon recalculées (sans les journaliser)."""
    import pyogrio
    if SORTIE.exists() and "commune" in pyogrio.list_layers(SORTIE)[:, 0]:
        return gpd.read_file(SORTIE, layer="commune")
    tmp: dict = {}
    etape_communes(Trace(), tmp)
    return tmp["commune"]


# ─────────────────────────────────────────────────────────────────────────────
# Étape 3 — Réseau routier
# ─────────────────────────────────────────────────────────────────────────────
def _premier(v):
    """Les listes OSM ont été stockées en texte : « ['primary', 'secondary'] » → primary."""
    if vide(v):
        return None
    s = str(v)
    if s.startswith("["):
        m = re.findall(r"'([^']*)'|\"([^\"]*)\"", s)
        vals = [a or b for a, b in m]
        return vals[0] if vals else None
    return s


def _vitesse(maxspeed, type_voie):
    v = _entier(_premier(maxspeed)) if not vide(maxspeed) else None
    if v and 5 <= v <= 140:
        return v, "maxspeed OSM"
    base = (type_voie or "").replace("_link", "")
    if base.startswith("track"):  # track_grade1 … track_grade5
        base = "track"
    if (type_voie or "").endswith("_link"):
        return VITESSE_LIEN, "défaut bretelle"
    return VITESSE_DEFAUT.get(base, 30), "défaut selon le type de voie"


def _routes_osmnx(f):
    """Graphe osmnx : tronçons avec u, v et couche de nœuds (identifiants OSM)."""
    tr = lire(f, "troncons").to_crs(CRS)
    nd = lire(f, "noeuds").to_crs(CRS)
    tr["type_voie"] = tr["highway"].map(_premier).fillna("road")
    tr["sens_unique"] = tr["oneway"].map(lambda v: _booleen(v) is True) if "oneway" in tr else False
    tr = tr.explode(index_parts=False)
    tr = tr[tr.geom_type == "LineString"].copy()
    return tr, nd.rename(columns={"osmid": "id"}), len(tr), "graphe osmnx"


def _routes_geofabrik(f, t):
    """Lignes Geofabrik (fclass, oneway F/T/B) sans nœuds : on construit la topologie.

    Deux voies OSM sont reliées si elles partagent un point OSM. On coupe donc chaque
    ligne aux sommets partagés avec une autre ligne et à ses extrémités : ces points
    deviennent les nœuds du graphe. Un pont qui passe au-dessus d'une route sans point
    commun ne crée PAS de croisement, comme dans la réalité.
    """
    import shapely
    from shapely.geometry import LineString

    tr = lire(f, "troncons").to_crs(CRS)
    n0 = len(tr)
    tr["type_voie"] = tr["fclass"].astype(str)
    exclues = tr["type_voie"].isin(VOIES_EXCLUES)
    for ty, n in tr.loc[exclues, "type_voie"].value_counts().items():
        t.log("troncon", "—", f"voie non circulable retirée ({ty})", "", int(n))
    tr = tr[~exclues].explode(index_parts=False)
    tr = tr[tr.geom_type == "LineString"].reset_index(drop=True)

    # Tous les sommets de toutes les lignes, arrondis pour reconnaître les points partagés
    coords, ligne = shapely.get_coordinates(tr.geometry.values, return_index=True)
    som = pd.DataFrame({"x": np.round(coords[:, 0] / ARRONDI_SOMMET_M).astype("int64"),
                        "y": np.round(coords[:, 1] / ARRONDI_SOMMET_M).astype("int64"),
                        "ligne": ligne})
    som["cle"] = som.groupby(["x", "y"], sort=False).ngroup()
    nb_lignes = som.drop_duplicates(["cle", "ligne"]).groupby("cle").size()
    som["partage"] = som["cle"].map(nb_lignes) >= 2
    premier = som.groupby("ligne").cumcount() == 0
    dernier = som.groupby("ligne").cumcount(ascending=False) == 0
    som["coupe"] = som["partage"] | premier | dernier

    # Découpe : un segment va d'un point de coupe au suivant sur la même ligne
    segs, attrs = [], []
    cols = ["type_voie", "maxspeed", "oneway"]
    valeurs = tr[cols].to_numpy()
    for li, grp in som.groupby("ligne", sort=False):
        pos = np.flatnonzero(grp["coupe"].to_numpy())
        cles = grp["cle"].to_numpy()
        xy = coords[grp.index.to_numpy()]
        for a, b in zip(pos[:-1], pos[1:]):
            segs.append((LineString(xy[a:b + 1]), cles[a], cles[b]))
            attrs.append(valeurs[li])
    seg = gpd.GeoDataFrame(pd.DataFrame(attrs, columns=cols),
                           geometry=[g for g, _, _ in segs], crs=CRS)
    seg["u"] = [u for _, u, _ in segs]
    seg["v"] = [v for _, _, v in segs]
    # oneway Geofabrik : F = sens du tracé, T = sens inverse, B = deux sens
    inverse = seg["oneway"].astype(str) == "T"
    seg.loc[inverse, "geometry"] = seg.loc[inverse, "geometry"].reverse()
    seg.loc[inverse, ["u", "v"]] = seg.loc[inverse, ["v", "u"]].to_numpy()
    seg["sens_unique"] = seg["oneway"].astype(str).isin(["F", "T"])

    # Nœuds : un par point de coupe, identifiant entier (pas d'identifiant OSM ici)
    pts = som[som["coupe"]].drop_duplicates("cle")
    nd = gpd.GeoDataFrame({"id": pts["cle"].to_numpy() + 1},
                          geometry=gpd.points_from_xy(coords[pts.index, 0], coords[pts.index, 1]),
                          crs=CRS)
    seg["u"] += 1
    seg["v"] += 1
    return seg, nd, n0, f"lignes Geofabrik ({int(exclues.sum())} voies non circulables retirées)"


def etape_routes(t: Trace, res: dict):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    import pyogrio

    f = DB / "osm_routes" / "routes_casablanca_settat.gpkg"
    if not f.exists():
        lire(f, "troncons")  # message « fichier absent »
    couches = pyogrio.list_layers(f)[:, 0]
    if "noeuds" in couches:
        tr, nd, n0_tr, format_source = _routes_osmnx(f)
    else:
        tr, nd, n0_tr, format_source = _routes_geofabrik(f, t)
    n0_nd = len(nd)

    vit = [_vitesse(m, ty) for m, ty in zip(tr["maxspeed"] if "maxspeed" in tr else [None] * len(tr),
                                           tr["type_voie"])]
    tr["vitesse_kmh"] = [v for v, _ in vit]
    n_defaut = sum(1 for _, s in vit if s != "maxspeed OSM")
    tr["longueur_m"] = tr.geometry.length.round(1)

    boucles = tr["u"] == tr["v"]
    nulles = tr["longueur_m"] <= 0
    tr = tr[~boucles & ~nulles]
    # arêtes parallèles entre les deux mêmes nœuds : on garde la plus courte, seule
    # utile au calcul. Une voie à double sens est la même de u vers v et de v vers u.
    tr = tr.sort_values("longueur_m")
    cle_a = np.where(tr["sens_unique"], tr["u"], np.minimum(tr["u"], tr["v"]))
    cle_b = np.where(tr["sens_unique"], tr["v"], np.maximum(tr["u"], tr["v"]))
    paralleles = pd.DataFrame({"a": cle_a, "b": cle_b, "s": tr["sens_unique"].to_numpy()},
                              index=tr.index).duplicated(keep="first")
    tr = tr[~paralleles]

    # Composantes connexes : un îlot de routes isolé du reste rendrait injoignables
    # les hexagones ou les centres qui s'y raccordent. On garde la plus grande.
    ids = pd.Index(pd.unique(pd.concat([tr["u"], tr["v"]])))
    iu, iv = ids.get_indexer(tr["u"]), ids.get_indexer(tr["v"])
    m = coo_matrix((np.ones(len(tr)), (iu, iv)), shape=(len(ids), len(ids)))
    n_comp, etiq = connected_components(m, directed=False)
    principale = np.bincount(etiq).argmax()
    dans = etiq[iu] == principale
    km_hors = tr.loc[~dans, "longueur_m"].sum() / 1000
    km_tot = tr["longueur_m"].sum() / 1000
    tr = tr[dans]

    utilises = pd.unique(pd.concat([tr["u"], tr["v"]]))
    nd = nd.drop_duplicates("id")
    orphelins = ~nd["id"].isin(utilises)
    nd = nd[~orphelins]

    t.log("troncon", "—", "boucles supprimées (départ = arrivée)", "", int(boucles.sum()))
    t.log("troncon", "—", "arêtes parallèles supprimées (plus courte gardée)", "", int(paralleles.sum()))
    t.log("troncon", "—", "tronçons hors du réseau principal connexe supprimés", "", int((~dans).sum()))
    t.log("noeud", "—", "nœuds orphelins supprimés", "", int(orphelins.sum()))

    res["noeud"] = gpd.GeoDataFrame({"id_noeud": nd["id"].astype("int64")},
                                    geometry=nd.geometry.values, crs=CRS)
    res["troncon"] = gpd.GeoDataFrame({
        "type_voie": tr["type_voie"].str[:30], "longueur_m": tr["longueur_m"],
        "vitesse_kmh": tr["vitesse_kmh"].astype("int16"), "sens_unique": tr["sens_unique"].astype(bool),
        "noeud_depart": tr["u"].astype("int64"), "noeud_arrivee": tr["v"].astype("int64"),
    }, geometry=tr.geometry.values, crs=CRS)

    km = res["troncon"].longueur_m.sum() / 1000
    types = res["troncon"].groupby("type_voie").agg(n=("longueur_m", "size"),
                                                   km=("longueur_m", lambda s: round(s.sum() / 1000)),
                                                   v=("vitesse_kmh", "median"))
    t.section("Réseau routier", [
        f"Format de la couche source : {format_source}.", "",
        *tableau(["Contrôle", "Avant", "Après"], [
            ("Lignes de la source", n0_tr, "—"),
            ("Tronçons du graphe (après découpe aux croisements)", "—", len(res["troncon"])),
            ("Nœuds", n0_nd, len(res["noeud"])),
            ("Boucles (départ = arrivée)", int(boucles.sum()), 0),
            ("Tronçons de longueur nulle", int(nulles.sum()), 0),
            ("Arêtes parallèles", int(paralleles.sum()), 0),
            ("Composantes connexes", n_comp, 1),
            ("Longueur hors du réseau principal connexe (îlots retirés)",
             f"{km_hors:,.0f} km ({100 * km_hors / max(km_tot, 1e-9):.1f} %)".replace(",", " "), 0),
            ("Nœuds orphelins", int(orphelins.sum()), 0),
            ("Tronçons sans vitesse OSM (vitesse par défaut)",
             f"{n_defaut} ({100 * n_defaut / max(len(vit), 1):.0f} %)", "—"),
        ]), "",
        f"Longueur totale du graphe : {km:,.0f} km.".replace(",", " "), "",
        *tableau(["Type de voie", "Tronçons", "km", "Vitesse médiane (km/h)"],
                 [(i, int(r.n), int(r.km), int(r.v)) for i, r in types.sort_values("km", ascending=False).iterrows()]),
        "", "Vitesses par défaut appliquées : " +
        ", ".join(f"{k} {v}" for k, v in VITESSE_DEFAUT.items()) + f", bretelles {VITESSE_LIEN} km/h. "
        "Voies retirées (non circulables en voiture) : " + ", ".join(sorted(VOIES_EXCLUES)) + ".",
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Étape 4 — Grille H3 et population
# ─────────────────────────────────────────────────────────────────────────────
def etape_h3(t: Trace, res: dict):
    import h3
    import rasterio
    from pyproj import Transformer
    from shapely.geometry import Polygon

    region = lire(DB / "limites" / "limites_casablanca_settat.gpkg", "region")
    poly = region.to_crs(C.CRS_GEO).geometry.union_all()
    cellules = set(h3.geo_to_cells(poly.__geo_interface__, H3_RESOLUTION))

    # Population : chaque pixel WorldPop (26191) est affecté à l'hexagone de son centre
    raster = DB / "worldpop" / "worldpop_2020_casablanca_settat_26191.tif"
    if not raster.exists():
        raise RuntimeError("raster WorldPop 26191 absent : relancez collecte.py --etapes worldpop")
    with rasterio.open(raster) as src:
        d = src.read(1, masked=True).filled(0).astype("float64")
        lignes, cols = np.nonzero(d > 0)
        xs, ys = rasterio.transform.xy(src.transform, lignes, cols)
        pop_pix = d[lignes, cols]
    total_raster = float(pop_pix.sum())
    lon, lat = Transformer.from_crs(CRS, C.CRS_GEO, always_xy=True).transform(np.array(xs), np.array(ys))
    idx = [h3.latlng_to_cell(la, lo, H3_RESOLUTION) for la, lo in zip(lat, lon)]
    pop = pd.Series(pop_pix).groupby(pd.Series(idx)).sum()
    # Hexagones de bordure : leur centre est hors de la région mais ils contiennent des
    # habitants de la région. On les ajoute pour ne perdre aucun habitant.
    bordure = set(pop.index) - cellules
    cellules |= bordure

    cel = sorted(cellules)
    geoms = [Polygon([(lo, la) for la, lo in h3.cell_to_boundary(c)]) for c in cel]
    g = gpd.GeoDataFrame({"h3_index": cel, "resolution": H3_RESOLUTION,
                          "population": [round(float(pop.get(c, 0.0)), 2) for c in cel]},
                         geometry=geoms, crs=C.CRS_GEO).to_crs(CRS)

    # Commune : celle qui contient le centre de l'hexagone
    commune = res.get("commune")
    if commune is None:
        commune = _communes_propres()
    centres = g.copy()
    centres["geometry"] = g.geometry.centroid
    j = gpd.sjoin(centres, commune[["code_hcp", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    g["code_hcp"] = j["code_hcp"]
    sans = g["code_hcp"].isna()
    if sans.any():
        p = gpd.sjoin_nearest(centres[sans][["geometry"]], commune[["code_hcp", "geometry"]], how="left")
        p = p[~p.index.duplicated(keep="first")]
        g.loc[sans, "code_hcp"] = p["code_hcp"]
    res["maille_h3"] = g

    total = g.population.sum()
    t.section("Grille H3 (résolution 8)", [
        *tableau(["Contrôle", "Valeur"], [
            ("Hexagones couvrant la région", len(g)),
            ("Hexagones habités (population > 0)", int((g.population > 0).sum())),
            ("Population du raster WorldPop", f"{total_raster:,.0f}".replace(",", " ")),
            ("Population affectée aux hexagones", f"{total:,.0f}".replace(",", " ")),
            ("dont hexagones de bordure ajoutés (centre hors région, mais habités)", len(bordure)),
            ("Écart de population raster / hexagones",
             f"{100 * (total - total_raster) / max(total_raster, 1):+.2f} %"),
            ("Hexagones dont le centre tombe hors de toute commune (commune la plus proche)",
             int(sans.sum())),
        ]),
    ])
    t.log("maille_h3", "—", "hexagones rattachés à la commune la plus proche", "", int(sans.sum()))


# ─────────────────────────────────────────────────────────────────────────────
def ecrire_rapport(t: Trace, etapes, dry, erreurs):
    C.PREUVES.mkdir(parents=True, exist_ok=True)
    md = ["# Rapport de nettoyage", "",
          f"Exécuté le {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} par `scripts/nettoyage.py`"
          f" — étapes : {', '.join(etapes)}.", "",
          ("**SIMULATION (`--dry-run`) : aucun fichier de données n'a été écrit.**" if dry else
           f"Sortie : `{SORTIE.relative_to(C.RACINE).as_posix()}`."), "",
          f"Toutes les couches sont en {CRS}. Le détail entité par entité est dans "
          "`preuves/journal_nettoyage.csv`."]
    for e in erreurs:
        md += ["", f"> **Échec de l'étape {e[0]}** : {e[1]}"]
    for titre, lignes in t.sections:
        md += ["", f"## {titre}", "", *lignes]
    (C.PREUVES / "rapport_nettoyage.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    with open(C.PREUVES / "journal_nettoyage.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["couche", "id", "regle", "avant", "apres"], delimiter=";")
        w.writeheader()
        w.writerows(t.journal)
    return "\n".join(md)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--etapes", nargs="+", choices=ORDRE, default=ORDRE)
    p.add_argument("--dry-run", action="store_true", help="simulation : rapport sans écrire les données")
    a = p.parse_args()

    etapes = [e for e in ORDRE if e in a.etapes]
    fonctions = {"communes": etape_communes, "etablissements": etape_etablissements,
                 "routes": etape_routes, "h3": etape_h3}
    t, res, erreurs = Trace(), {}, []
    for nom in etapes:
        print(f"\n[{nom}]")
        try:
            fonctions[nom](t, res)
            print("  OK")
        except Exception as ex:
            erreurs.append((nom, f"{type(ex).__name__}: {ex}"))
            print(f"  ÉCHEC : {ex}")

    if not a.dry_run and res:
        PROPRES.mkdir(exist_ok=True)
        for couche, gdf in res.items():  # remplace seulement les couches recalculées
            gdf.to_file(SORTIE, layer=couche, driver="GPKG", engine="pyogrio")
            print(f"  écrit : {couche} ({len(gdf)} lignes)")
    print("\n" + ecrire_rapport(t, etapes, a.dry_run, erreurs))
    sys.exit(1 if erreurs else 0)


if __name__ == "__main__":
    main()