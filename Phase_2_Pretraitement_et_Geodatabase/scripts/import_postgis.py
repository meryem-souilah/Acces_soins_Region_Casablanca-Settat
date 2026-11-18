"""
import_postgis.py — Fusion des établissements et chargement de la géodatabase PostGIS

À lancer après nettoyage.py et geocodage_essp.py. Le script :

  1. fusionne les établissements OSM (base_sante.gpkg, couche etablissement) et ceux
     du Ministère de la Santé positionnés (essp_geocode.gpkg) dans UNE table au format
     de sql/Schema.sql (id_source, source, precision_geom…). Le résultat est aussi
     écrit dans base_sante.gpkg, couche etablissement_complet (pour QGIS) ;
  2. crée la base si besoin et exécute sql/Schema.sql (schéma « sante », recréé) ;
  3. charge les tables dans l'ordre des clés étrangères, par COPY ;
  4. calcule id_noeud (nœud routier le plus proche) des établissements et des hexagones ;
  5. contrôle le chargement (effectifs, SRID, géométries, clés) et passe les tests
     de sql/TestContraintes.sql (chacun doit être REFUSÉ par la base) ;
  6. (option --sauvegarde) écrit une sauvegarde pg_dump.

Sorties : donnees_propres/base_sante.gpkg  couche etablissement_complet
          preuves/rapport_import_postgis.md
          donnees_propres/acces_soins.backup  (avec --sauvegarde)

Connexion : le mot de passe n'est JAMAIS passé en argument. Le mettre dans la variable
d'environnement PGPASSWORD, dans un fichier pgpass, ou dans un fichier .env à la racine
du dépôt (ignoré par git) contenant la ligne PGPASSWORD=...

Usage :
    python scripts/import_postgis.py --gpkg-seulement            # fusion seule, sans base
    set PGPASSWORD=...  (PowerShell : $env:PGPASSWORD="...")
    python scripts/import_postgis.py --base acces_soins --user postgres --sauvegarde
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402  (avant geopandas : correctif PROJ)

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402

PROPRES = C.RACINE / "donnees_propres"
BASE_GPKG = PROPRES / "base_sante.gpkg"
ESSP_GPKG = PROPRES / "essp_geocode.gpkg"
SQL = C.RACINE / "sql"
SRID = 26191

# Ordre de chargement (clés étrangères) et colonnes de chaque table, hors clé auto
TABLES = {
    "province": ["code_province", "nom", "type_province"],
    "commune": ["code_hcp", "nom", "pop_2024", "code_province"],
    "noeud": ["id_noeud"],
    "troncon": ["type_voie", "longueur_m", "vitesse_kmh", "sens_unique", "noeud_depart", "noeud_arrivee"],
    "etablissement": ["id_source", "source", "nom", "secteur", "code_type", "code_niveau",
                      "niveau_source", "precision_geom", "code_hcp"],
    "maille_h3": ["h3_index", "resolution", "population", "code_hcp"],
}
TYPES_MSPS = {"CSU-1", "CSU-2", "CSR-1", "CSR-2", "DR", "LSP", "CRSR", "CDTMR"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fusion OSM + Ministère
# ─────────────────────────────────────────────────────────────────────────────
def fusionner() -> tuple[gpd.GeoDataFrame, dict]:
    osm = gpd.read_file(BASE_GPKG, layer="etablissement")
    essp = gpd.read_file(ESSP_GPKG, layer="etablissement_essp")
    for g, nom in ((osm, "base_sante.gpkg"), (essp, "essp_geocode.gpkg")):
        if g.crs is None or g.crs.to_epsg() != SRID:
            raise RuntimeError(f"{nom} : CRS {g.crs} au lieu de EPSG:{SRID}")

    a = pd.DataFrame({
        "id_source": osm["osm_id"].astype(str), "source": "osm", "nom": osm["nom"],
        "secteur": osm["secteur"], "code_type": osm["code_type"],
        "code_niveau": osm["code_niveau"].astype(int), "niveau_source": osm["niveau_source"],
        "precision_geom": "osm", "code_hcp": osm["code_hcp"], "geometry": osm.geometry,
    })
    # geocodage_essp.py range les centres dans un type générique (code_type = centre_sante
    # ou autre) et garde la catégorie officielle dans categorie_msps. Le schéma, lui, a un
    # type par catégorie du Ministère (CSU-1, DR…) et déclare centre_sante HORS analyse :
    # on charge donc la catégorie officielle, sinon tous les centres publics seraient exclus.
    inconnus = set(essp["categorie_msps"]) - TYPES_MSPS
    if inconnus:
        raise RuntimeError(f"catégories du Ministère absentes de type_etablissement : {sorted(inconnus)}")
    exclues = {"LSP", "CRSR", "CDTMR"}  # inclus_analyse = false dans Schema.sql
    incoherent = essp["inclus_analyse"].astype(bool) == essp["categorie_msps"].isin(exclues)
    if incoherent.any():
        raise RuntimeError("inclus_analyse du géocodage différent de celui du schéma pour "
                           f"{essp.loc[incoherent, 'id_source'].tolist()[:10]}")
    b = pd.DataFrame({
        "id_source": essp["id_source"].astype(str), "source": "msps", "nom": essp["nom"],
        "secteur": "public",  # liste officielle du Ministère : établissements publics
        "code_type": essp["categorie_msps"], "code_niveau": essp["code_niveau"].astype(int),
        "niveau_source": essp["niveau_source"], "precision_geom": essp["precision_geom"],
        "code_hcp": essp["code_hcp"], "geometry": essp.geometry,
    })
    e = gpd.GeoDataFrame(pd.concat([a, b], ignore_index=True), geometry="geometry", crs=f"EPSG:{SRID}")

    doublons = e["id_source"][e["id_source"].duplicated()].tolist()
    if doublons:
        raise RuntimeError(f"id_source en double : {doublons[:10]}")
    for col in ("code_type", "code_niveau", "code_hcp", "precision_geom"):
        if e[col].isna().any():
            raise RuntimeError(f"{int(e[col].isna().sum())} établissements sans {col}")
    if (e.geometry.isna() | e.geometry.is_empty).any():
        raise RuntimeError("établissement sans géométrie")

    stats = {"osm": len(a), "msps": len(b),
             "msps_precision": b["precision_geom"].value_counts().to_dict(),
             "msps_inclus": int(essp["inclus_analyse"].astype(bool).sum())}
    return e, stats


# ─────────────────────────────────────────────────────────────────────────────
# 2-4. Base PostGIS
# ─────────────────────────────────────────────────────────────────────────────
def connecter(a, base):
    import psycopg2
    return psycopg2.connect(host=a.host, port=a.port, user=a.user, dbname=base)


def creer_base_si_absente(a):
    # On interroge pg_database plutôt que d'analyser le message d'erreur : sous Windows,
    # un serveur en français renvoie un message en cp1252 que psycopg2 ne sait pas décoder.
    cx = connecter(a, "postgres")
    cx.autocommit = True
    with cx.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (a.base,))
        existe = cur.fetchone() is not None
        if not existe:
            cur.execute(f'CREATE DATABASE "{a.base}" ENCODING \'UTF8\'')
    cx.close()
    return not existe


def copier(cur, table, gdf, colonnes):
    """COPY rapide : la géométrie part en EWKB hexadécimal (avec SRID)."""
    df = pd.DataFrame({c: gdf[c] for c in colonnes})
    geoms = shapely.set_srid(gdf.geometry.values, SRID)
    df["geom"] = shapely.to_wkb(geoms, hex=True, include_srid=True)
    for c in df.columns:
        if df[c].dtype == bool or str(df[c].dtype) == "boolean":
            df[c] = df[c].map({True: "t", False: "f"})
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cur.copy_expert(f"COPY sante.{table} ({', '.join(df.columns)}) FROM STDIN "
                    "WITH (FORMAT csv, NULL '\\N')", buf)
    return len(df)


def charger(a, etab) -> dict:
    couches = {t: gpd.read_file(BASE_GPKG, layer=t) for t in TABLES if t != "etablissement"}
    couches["etablissement"] = etab
    # entiers nullables (pop_2024) : pas de « 123.0 » dans le COPY
    couches["commune"]["pop_2024"] = couches["commune"]["pop_2024"].astype("Int64")

    cx = connecter(a, a.base)
    with cx, cx.cursor() as cur:
        print("  schéma : sql/Schema.sql")
        cur.execute((SQL / "Schema.sql").read_text(encoding="utf-8"))
        n = {}
        for t, cols in TABLES.items():
            n[t] = copier(cur, t, couches[t], cols)
            print(f"  {t:14s} {n[t]:>7} lignes")

        print("  nœud le plus proche des établissements et des hexagones")
        for t in ("etablissement", "maille_h3"):
            centre = "ST_Centroid(x.geom)" if t == "maille_h3" else "x.geom"
            cur.execute(f"""
                UPDATE sante.{t} x SET id_noeud = (
                    SELECT n.id_noeud FROM sante.noeud n
                    ORDER BY n.geom <-> {centre} LIMIT 1)""")
    cx.autocommit = True
    with cx.cursor() as cur:
        cur.execute("VACUUM ANALYZE")
    cx.close()
    return n


def controler(a, attendu: dict) -> list[str]:
    cx = connecter(a, a.base)
    lignes = ["| Table | Lignes attendues | Lignes en base | SRID | Géométries invalides |",
              "| --- | --- | --- | --- | --- |"]
    ok = True
    with cx.cursor() as cur:
        for t in TABLES:
            cur.execute(f"SELECT count(*), min(ST_SRID(geom)), max(ST_SRID(geom)), "
                        f"count(*) FILTER (WHERE NOT ST_IsValid(geom)) FROM sante.{t}")
            n, s1, s2, inv = cur.fetchone()
            ok &= n == attendu[t] and s1 == s2 == SRID and inv == 0
            lignes.append(f"| {t} | {attendu[t]} | {n} | {s1 if s1 == s2 else f'{s1}–{s2}'} | {inv} |")

        verifs = {
            "Communes sans population": "SELECT count(*) FROM sante.commune WHERE pop_2024 IS NULL",
            "Population des communes (RGPH 2024)": "SELECT sum(pop_2024) FROM sante.commune",
            "Population des hexagones (WorldPop 2020)": "SELECT round(sum(population))::bigint FROM sante.maille_h3",
            "Établissements sans nœud routier": "SELECT count(*) FROM sante.etablissement WHERE id_noeud IS NULL",
            "Hexagones sans nœud routier": "SELECT count(*) FROM sante.maille_h3 WHERE id_noeud IS NULL",
            "Distance médiane établissement → nœud (m)":
                "SELECT round(percentile_cont(0.5) WITHIN GROUP (ORDER BY ST_Distance(e.geom, n.geom))::numeric) "
                "FROM sante.etablissement e JOIN sante.noeud n USING (id_noeud)",
            "Distance max établissement → nœud (m)":
                "SELECT round(max(ST_Distance(e.geom, n.geom))::numeric) "
                "FROM sante.etablissement e JOIN sante.noeud n USING (id_noeud)",
            "Établissements hors de leur commune (> 500 m)":
                "SELECT count(*) FROM sante.etablissement e JOIN sante.commune c USING (code_hcp) "
                "WHERE NOT ST_DWithin(e.geom, c.geom, 500)",
        }
        lignes += ["", "| Contrôle | Valeur |", "| --- | --- |"]
        for lib, q in verifs.items():
            cur.execute(q)
            v = cur.fetchone()[0]
            lignes.append(f"| {lib} | {v:,} |".replace(",", " ") if isinstance(v, int)
                          else f"| {lib} | {v} |")

        cur.execute("""SELECT e.source, e.code_niveau, t.inclus_analyse, count(*)
                       FROM sante.etablissement e JOIN sante.type_etablissement t USING (code_type)
                       GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""")
        lignes += ["", "**Établissements par source et niveau**", "",
                   "| Source | Niveau | Inclus dans l'analyse | Nombre |", "| --- | --- | --- | --- |"]
        lignes += [f"| {s} | {n} | {'oui' if i else 'non'} | {c} |" for s, n, i, c in cur.fetchall()]
    cx.close()
    if not ok:
        lignes.insert(0, "> **Écart détecté entre le GeoPackage et la base : voir le tableau.**\n")
    return lignes


def tests_contraintes(a) -> list[str]:
    """Chaque bloc BEGIN … ROLLBACK de TestContraintes.sql tente une écriture. Le test
    réussit si PostgreSQL la REFUSE, sauf pour les tests marqués « doit être ACCEPTÉ »."""
    import psycopg2
    texte = (SQL / "TestContraintes.sql").read_text(encoding="utf-8")
    blocs = re.findall(r"((?:--[^\n]*\n|\s)*)BEGIN;(.*?)ROLLBACK;", texte, flags=re.S)
    cx = connecter(a, a.base)
    lignes = ["| # | Test | Attendu | Obtenu | Message de PostgreSQL |", "| --- | --- | --- | --- | --- |"]
    n_ok = 0
    for k, (commentaire, corps) in enumerate(blocs, 1):
        titre = next((l.strip("- ").strip() for l in reversed(commentaire.splitlines())
                      if l.strip().startswith("-- Test")), f"Test {k}")
        doit_accepter = "doit être accepté" in titre.lower()
        titre = re.sub(r"^Test \d+\s*(\(doit être ACCEPTÉ\))?\s*:\s*(\(doit être ACCEPTÉ\))?\s*", "", titre)
        with cx.cursor() as cur:
            try:
                cur.execute("SET search_path = sante, public;" + corps)
                accepte, msg = True, ""
            except psycopg2.Error as ex:
                accepte, msg = False, (ex.pgerror or str(ex)).splitlines()[0].replace("|", "/")[:110]
        cx.rollback()
        ok = accepte == doit_accepter
        n_ok += ok
        lignes.append(f"| {k} | {titre} | {'accepté' if doit_accepter else 'refusé'} | "
                      f"{'✅' if ok else '❌'} {'accepté' if accepte else 'refusé'} | {msg} |")
    cx.close()
    return [f"{n_ok} / {len(blocs)} tests conformes au résultat attendu.", "", *lignes]


def sauvegarder(a) -> Path:
    pg_dump = shutil.which("pg_dump") or next(
        (str(p) for p in sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin/pg_dump.exe"), reverse=True)), None)
    if not pg_dump:
        raise RuntimeError("pg_dump introuvable : ajoutez le dossier bin de PostgreSQL au PATH")
    sortie = PROPRES / "acces_soins.backup"
    subprocess.run([pg_dump, "-h", a.host, "-p", str(a.port), "-U", a.user, "-d", a.base,
                    "-n", "sante", "-Fc", "-f", str(sortie)], check=True, env=os.environ.copy())
    return sortie


# ─────────────────────────────────────────────────────────────────────────────
def lire_env():
    """Variables PG* d'un fichier .env à la racine du dépôt (ignoré par git), sans écraser
    celles déjà définies. Exemple de ligne : PGPASSWORD=monmotdepasse"""
    f = C.RACINE.parent / ".env"
    if not f.exists():
        return
    for ligne in f.read_text(encoding="utf-8-sig").splitlines():
        cle, sep, val = ligne.strip().partition("=")
        if sep and cle.strip().startswith("PG"):
            os.environ.setdefault(cle.strip(), val.strip().strip('"').strip("'"))


def main():
    lire_env()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PGPORT", 5432)))
    p.add_argument("--user", default=os.environ.get("PGUSER", "postgres"))
    p.add_argument("--base", default=os.environ.get("PGDATABASE", "acces_soins"))
    p.add_argument("--gpkg-seulement", action="store_true", help="fusion dans le GeoPackage, sans PostGIS")
    p.add_argument("--sauvegarde", action="store_true", help="écrire donnees_propres/acces_soins.backup")
    a = p.parse_args()

    print("[fusion des établissements]")
    etab, st = fusionner()
    etab.to_file(BASE_GPKG, layer="etablissement_complet", driver="GPKG", engine="pyogrio")
    print(f"  {st['osm']} OSM + {st['msps']} Ministère = {len(etab)} → couche etablissement_complet")

    md = ["# Rapport de fusion et d'import PostGIS", "",
          f"Exécuté le {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} par `scripts/import_postgis.py`.", "",
          "## Fusion des établissements", "",
          "| Source | Établissements | Origine de la position |", "| --- | --- | --- |",
          f"| OpenStreetMap (nettoyage.py) | {st['osm']} | osm |",
          f"| Ministère de la Santé 2022 (geocodage_essp.py) | {st['msps']} | " +
          ", ".join(f"{k} {v}" for k, v in st["msps_precision"].items()) + " |",
          f"| **Total** (`etablissement_complet`) | **{len(etab)}** | |", "",
          "Les centres de santé OSM (`centre_sante`) restent hors analyse (`inclus_analyse = false`) : "
          "les soins primaires publics viennent de la liste du Ministère, ce qui évite de compter "
          "deux fois le même centre. Seuls les établissements du Ministère **positionnés** sont "
          "chargés (la géométrie est obligatoire) ; ceux qui restent à positionner sont listés "
          "dans `corrections/a_positionner_essp.csv`."]

    if a.gpkg_seulement:
        md += ["", "_Import PostGIS non lancé (`--gpkg-seulement`)._"]
    else:
        print(f"[PostGIS] {a.user}@{a.host}:{a.port}/{a.base}")
        if creer_base_si_absente(a):
            print(f"  base {a.base} créée")
        n = charger(a, etab)
        print("[contrôles]")
        md += ["", "## Chargement PostGIS", "",
               f"Base `{a.base}`, schéma `sante`, créé par `sql/Schema.sql`. Chargement par `COPY`, "
               "puis `id_noeud` = nœud routier le plus proche (index GiST, opérateur `<->`) pour les "
               "établissements et pour le centre de chaque hexagone.", "", *controler(a, n)]
        print("[tests de contraintes]")
        md += ["", "## Tests de contraintes (`sql/TestContraintes.sql`)", "", *tests_contraintes(a)]
        if a.sauvegarde:
            print("[sauvegarde pg_dump]")
            s = sauvegarder(a)
            md += ["", "## Sauvegarde", "",
                   f"`{s.relative_to(C.RACINE).as_posix()}` ({s.stat().st_size / 1e6:.0f} Mo, format custom). "
                   f"Restauration : `pg_restore -d {a.base} --clean --if-exists {s.name}`."]

    (C.PREUVES / "rapport_import_postgis.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
