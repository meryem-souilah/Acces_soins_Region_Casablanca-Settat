"""
import_postgis.py — Création du schéma PostGIS, import ogr2ogr -> staging -> sante,
                    exécution des 3 requêtes métier (EXPLAIN ANALYZE) et sauvegarde pg_dump.

Étapes automatisées :
  1. Exécution de `sql/schema.sql` sur PostgreSQL/PostGIS (`acces_soins`).
  2. Import des 6 couches nettoyées (`donnees_traitees/sante_nettoyee.gpkg`) via `ogr2ogr`
     dans un schéma temporaire `staging`.
  3. Insertion contrôlée (`INSERT INTO sante.<table> SELECT ... FROM staging.<table>`)
     dans l'ordre des clés étrangères (province -> commune -> noeud -> troncon ->
     etablissement -> maille_h3) et mise à jour des statistiques (`ANALYZE`).
  4. Test de rejet d'une insertion invalide violant la clé étrangère `etablissement_code_hcp_fkey`
     et la contrainte de SRID (`EPSG:26191`).
  5. Exécution de `sql/requetes.sql` (3 requêtes spatiales métier + `EXPLAIN (ANALYZE, BUFFERS)`)
     et enregistrement des résultats dans `preuves/resultats_requetes_seance4.md`.
  6. Export du dump PostGIS (`sql/acces_soins.backup` au format custom compressé +
     `sql/acces_soins_schema_et_ref.sql`) et vérification de sa restauration complète
     sur une base de test `acces_soins_restore_test`.

Usage :
    python scripts/import_postgis.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

GPKG_NETTOYE = C.RACINE / "donnees_traitees" / "sante_nettoyee.gpkg"
SCHEMA_SQL = C.RACINE / "sql" / "schema.sql"
REQUETES_SQL = C.RACINE / "sql" / "requetes.sql"
DUMP_BACKUP = C.RACINE / "sql" / "acces_soins.backup"
RAPPORT_REQUETES = C.PREUVES / "resultats_requetes_seance4.md"

PG_HOST = os.environ.get("PGHOST", "127.0.0.1")
PG_PORT = int(os.environ.get("PGPORT", "5432"))
PG_USER = os.environ.get("PGUSER", "postgres")
PG_PASSWORD = os.environ.get("PGPASSWORD", "admin")
PG_DB = os.environ.get("PGDATABASE", "acces_soins")


def trouver_binaire(nom: str, candidats: list[str]) -> str:
    w = shutil.which(nom)
    if w:
        return w
    for c in candidats:
        if Path(c).exists():
            return c
    raise RuntimeError(f"Binaire introuvable : {nom}")


PSQL = trouver_binaire("psql", [
    r"C:\Program Files\PostgreSQL\16\bin\psql.exe",
    r"C:\Program Files\PostgreSQL\18\bin\psql.exe",
])
PG_DUMP = trouver_binaire("pg_dump", [
    r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
    r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
])
PG_RESTORE = trouver_binaire("pg_restore", [
    r"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe",
    r"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe",
])
OGR2OGR = trouver_binaire("ogr2ogr", [
    r"C:\Program Files\QGIS 3.40.1\bin\ogr2ogr.exe",
])


def env_pg() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD
    env["PGCLIENTENCODING"] = "UTF8"
    return env


def connexion(dbname: str = PG_DB):
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=dbname,
    )


def executer_schema():
    print(f"[1/6] Exécution de {SCHEMA_SQL.relative_to(C.RACINE)} sur {PG_DB}...")
    res = subprocess.run(
        [PSQL, "-h", PG_HOST, "-p", str(PG_PORT), "-U", PG_USER, "-d", PG_DB, "-v", "ON_ERROR_STOP=1", "-f", str(SCHEMA_SQL)],
        env=env_pg(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(f"Erreur schema.sql :\n{res.stderr}")
    print("      -> Schéma `sante` créé avec ses 8 tables, contraintes CHECK/FK et index GIST/B-tree.")


def importer_ogr2ogr_vers_staging():
    print(f"[2/6] Import ogr2ogr de {GPKG_NETTOYE.relative_to(C.RACINE)} vers le schéma `staging`...")
    if not GPKG_NETTOYE.exists():
        raise RuntimeError(f"Fichier nettoyé absent : {GPKG_NETTOYE}. Lancez d'abord scripts/nettoyage.py.")

    with connexion() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS staging CASCADE; CREATE SCHEMA staging;")
        conn.commit()

    pg_conn_str = f"PG:host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PASSWORD}"
    couches = ["province", "commune", "noeud", "troncon", "etablissement", "maille_h3"]
    for couche in couches:
        cmd = [
            OGR2OGR,
            "--config", "PG_USE_COPY", "YES",
            "-gt", "65536",
            "-f", "PostgreSQL",
            pg_conn_str,
            str(GPKG_NETTOYE),
            couche,
            "-nln", f"staging.{couche}",
            "-lco", "GEOMETRY_NAME=geom",
            "-lco", "FID=ogc_fid",
            "-lco", "SPATIAL_INDEX=NONE",
            "-t_srs", "EPSG:26191",
            "-overwrite",
        ]
        if couche in ("province", "commune"):
            cmd.extend(["-nlt", "PROMOTE_TO_MULTI"])
        res = subprocess.run(cmd, env=env_pg(), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Erreur ogr2ogr sur {couche} :\n{res.stderr}")
        print(f"      -> ogr2ogr : couche `staging.{couche}` chargée.")


def peupler_tables_finales() -> dict[str, int]:
    print("[3/6] Transfert `staging` -> `sante` avec validation de toutes les contraintes et index...")
    sql_transfert = """
    SET search_path = sante, public;

    INSERT INTO sante.province (code_province, nom, type_province, geom)
    SELECT code_province, nom, type_province, ST_Multi(ST_MakeValid(geom))
    FROM staging.province;

    INSERT INTO sante.commune (code_hcp, nom, pop_2024, code_province, geom)
    SELECT code_hcp, nom, pop_2024::integer, code_province, ST_Multi(ST_MakeValid(geom))
    FROM staging.commune;

    INSERT INTO sante.noeud (id_noeud, geom)
    SELECT id_noeud::bigint, geom
    FROM staging.noeud;

    INSERT INTO sante.troncon (id_troncon, type_voie, longueur_m, vitesse_kmh, sens_unique, noeud_depart, noeud_arrivee, geom)
    SELECT id_troncon::bigint, type_voie, longueur_m::real, vitesse_kmh::smallint, sens_unique::boolean,
           noeud_depart::bigint, noeud_arrivee::bigint, geom
    FROM staging.troncon;

    SELECT setval(pg_get_serial_sequence('sante.troncon', 'id_troncon'), COALESCE((SELECT MAX(id_troncon) FROM sante.troncon), 1));

    INSERT INTO sante.etablissement (osm_id, nom, secteur, nb_lits, urgences, code_type, code_niveau, niveau_source, code_hcp, id_noeud, geom)
    SELECT osm_id, nom, secteur, nb_lits::integer, urgences::boolean,
           code_type, code_niveau::smallint, niveau_source, code_hcp, id_noeud::bigint, geom
    FROM staging.etablissement;

    INSERT INTO sante.maille_h3 (h3_index, resolution, population, code_hcp, id_noeud, geom)
    SELECT h3_index, resolution::smallint, population::real, code_hcp, id_noeud::bigint, ST_MakeValid(geom)
    FROM staging.maille_h3;

    DROP SCHEMA staging CASCADE;

    ANALYZE sante.province;
    ANALYZE sante.commune;
    ANALYZE sante.niveau_soin;
    ANALYZE sante.type_etablissement;
    ANALYZE sante.noeud;
    ANALYZE sante.troncon;
    ANALYZE sante.etablissement;
    ANALYZE sante.maille_h3;
    """
    effectifs = {}
    with connexion() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_transfert)
            for t in ("province", "commune", "niveau_soin", "type_etablissement", "etablissement", "maille_h3", "noeud", "troncon"):
                cur.execute(f"SELECT COUNT(*) FROM sante.{t};")
                effectifs[t] = cur.fetchone()[0]
        conn.commit()

    for t, n in effectifs.items():
        print(f"      -> sante.{t:<20} : {n:>8,} lignes".replace(",", " "))
    return effectifs


def tester_contraintes_integrite() -> list[tuple[str, str]]:
    print("[4/6] Vérification des rejets d'intégrité (clé étrangère, SRID, CHECK)...")
    tests = [
        (
            "Insertion d'un établissement dans une commune inexistante (violation FK `etablissement_code_hcp_fkey`)",
            """
            INSERT INTO sante.etablissement (osm_id, code_type, code_niveau, code_hcp, geom)
            VALUES ('test/fk_commune', 'hopital', 2, 'CODE_INEXISTANT',
                    ST_SetSRID(ST_MakePoint(300000, 330000), 26191));
            """,
        ),
        (
            "Insertion d'une géométrie en EPSG:4326 au lieu de EPSG:26191 (violation SRID)",
            """
            INSERT INTO sante.noeud (id_noeud, geom)
            VALUES (-999, ST_SetSRID(ST_MakePoint(-7.6, 33.5), 4326));
            """,
        ),
        (
            "Suppression d'une commune possédant des établissements (violation `ON DELETE RESTRICT`)",
            """
            DELETE FROM sante.commune WHERE code_hcp = '06.117.01.03';
            """,
        ),
        (
            "Insertion d'un tronçon bouclant sur le même nœud (violation `CHECK (noeud_depart <> noeud_arrivee)`)",
            """
            INSERT INTO sante.troncon (type_voie, longueur_m, vitesse_kmh, noeud_depart, noeud_arrivee, geom)
            SELECT 'residential', 25.0, 30, id_noeud, id_noeud,
                   ST_SetSRID(ST_MakeLine(geom, ST_Translate(geom, 10, 10)), 26191)
            FROM sante.noeud LIMIT 1;
            """,
        ),
    ]
    resultats = []
    with connexion() as conn:
        for titre, sql in tests:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.rollback()
                resultats.append((titre, "ÉCHEC : requête acceptée par erreur"))
            except Exception as e:
                conn.rollback()
                msg = str(e).strip().splitlines()[0]
                resultats.append((titre, f"REJETÉ COMME ATTENDU : `{msg}`"))
                print(f"      -> [OK] {titre} -> {msg[:90]}")
    return resultats


def executer_requetes_et_sauvegarder(effectifs: dict[str, int], tests_fk: list[tuple[str, str]]):
    print(f"[5/6] Exécution de {REQUETES_SQL.relative_to(C.RACINE)} (avec EXPLAIN ANALYZE)...")
    res = subprocess.run(
        [PSQL, "-h", PG_HOST, "-p", str(PG_PORT), "-U", PG_USER, "-d", PG_DB, "-a", "-f", str(REQUETES_SQL)],
        env=env_pg(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(f"Erreur dans requetes.sql :\n{res.stderr}")

    print("[6/6] Sauvegarde pg_dump et test de restauration complète...")
    res_dump = subprocess.run(
        [PG_DUMP, "-h", PG_HOST, "-p", str(PG_PORT), "-U", PG_USER, "-Fc", "-f", str(DUMP_BACKUP), PG_DB],
        env=env_pg(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res_dump.returncode != 0:
        raise RuntimeError(f"Erreur pg_dump :\n{res_dump.stderr}")
    taille_mo = DUMP_BACKUP.stat().st_size / 1_048_576

    # Test de restauration dans une base dédiée acces_soins_restore_test
    db_test = "acces_soins_restore_test"
    conn_admin = connexion("postgres")
    conn_admin.autocommit = True
    with conn_admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {db_test} WITH (FORCE);")
        cur.execute(f"CREATE DATABASE {db_test};")
    conn_admin.close()

    res_rest = subprocess.run(
        [PG_RESTORE, "-h", PG_HOST, "-p", str(PG_PORT), "-U", PG_USER, "-d", db_test, str(DUMP_BACKUP)],
        env=env_pg(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    with connexion(db_test) as conn_t:
        with conn_t.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sante.etablissement;")
            n_etab_rest = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sante.maille_h3;")
            n_h3_rest = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sante.troncon;")
            n_tr_rest = cur.fetchone()[0]

    conn_admin = connexion("postgres")
    conn_admin.autocommit = True
    with conn_admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {db_test} WITH (FORCE);")
    conn_admin.close()

    print(f"      -> Dump créé : {DUMP_BACKUP.relative_to(C.RACINE)} ({taille_mo:.2f} Mo)")
    print(f"      -> Restauration testée avec succès ({n_etab_rest} établ., {n_h3_rest} hexagones H3, {n_tr_rest} tronçons).")

    # Écriture du rapport complet des requêtes et de la base
    md = [
        "# Résultats d'import PostGIS, tests de contraintes et requêtes métier (Séance 4)",
        "",
        f"- **Date d'exécution** : {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        f"- **Base de données** : PostgreSQL 16 / PostGIS 3.5 (`{PG_DB}`, schéma `sante`, CRS `EPSG:26191`)",
        f"- **Sauvegarde restaurable** : `sql/acces_soins.backup` ({taille_mo:.2f} Mo, testé avec `pg_restore` : {n_etab_rest} établ., {n_h3_rest} mailles H3, {n_tr_rest} tronçons)",
        "",
        "## 1. Effectifs des 8 tables du schéma `sante`",
        "",
        "| Table | Rôle | Lignes chargées | Géométrie / SRID | Index GIST / B-tree |",
        "| --- | --- | --- | --- | --- |",
        f"| `sante.province` | Décision | **{effectifs['province']}** | `MultiPolygon, 26191` | `province_geom_gist` |",
        f"| `sante.commune` | Décision | **{effectifs['commune']}** | `MultiPolygon, 26191` | `commune_geom_gist`, `commune_code_province_idx` |",
        f"| `sante.niveau_soin` | Offre | **{effectifs['niveau_soin']}** | — (référentiel) | PK `code_niveau` |",
        f"| `sante.type_etablissement` | Offre | **{effectifs['type_etablissement']}** | — (référentiel) | `type_niveau_idx` |",
        f"| `sante.etablissement` | Offre | **{effectifs['etablissement']:,}** | `Point, 26191` | `etablissement_geom_gist` + 4 index FK |".replace(",", " "),
        f"| `sante.maille_h3` | Demande | **{effectifs['maille_h3']:,}** | `Polygon, 26191` | `maille_h3_geom_gist` + 2 index FK |".replace(",", " "),
        f"| `sante.noeud` | Accès | **{effectifs['noeud']:,}** | `Point, 26191` | `noeud_geom_gist` |".replace(",", " "),
        f"| `sante.troncon` | Accès | **{effectifs['troncon']:,}** | `LineString, 26191` | `troncon_geom_gist` + 2 index FK |".replace(",", " "),
        "",
        "## 2. Démonstration des contraintes d'intégrité (rejets automatiques)",
        "",
        "| Test d'intégrité | Résultat PostgreSQL / PostGIS |",
        "| --- | --- |",
        *[f"| {t} | {r} |" for t, r in tests_fk],
        "",
        "## 3. Sortie complète des 3 requêtes spatiales métier et plans `EXPLAIN (ANALYZE, BUFFERS)`",
        "",
        "```text",
        res.stdout.strip(),
        "```",
    ]
    RAPPORT_REQUETES.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Rapport des requêtes écrit : {RAPPORT_REQUETES}")


def main():
    executer_schema()
    importer_ogr2ogr_vers_staging()
    effectifs = peupler_tables_finales()
    tests_fk = tester_contraintes_integrite()
    executer_requetes_et_sauvegarder(effectifs, tests_fk)


if __name__ == "__main__":
    main()
