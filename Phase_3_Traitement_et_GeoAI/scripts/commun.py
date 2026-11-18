"""Chemins et connexion à la base, communs aux scripts de la Phase 3.

La connexion réutilise celle de la Phase 2 : paramètres PG* de l'environnement ou du
fichier .env à la racine du dépôt (jamais de mot de passe dans le code).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent          # Phase_3_Traitement_et_GeoAI
DEPOT = RACINE.parent
PHASE2_SCRIPTS = DEPOT / "Phase_2_Pretraitement_et_Geodatabase" / "scripts"
sys.path.insert(0, str(PHASE2_SCRIPTS))

import config as C  # noqa: E402,F401  (correctif PROJ/GDAL avant geopandas)
from import_postgis import lire_env  # noqa: E402

SQL = RACINE / "sql"
PREUVES = RACINE / "preuves"
DONNEES = RACINE / "donnees"
CRS = "EPSG:26191"
SRID = 26191

lire_env()


def connexion():
    import psycopg2
    return psycopg2.connect(host=os.environ.get("PGHOST", "localhost"),
                            port=int(os.environ.get("PGPORT", 5432)),
                            user=os.environ.get("PGUSER", "postgres"),
                            dbname=os.environ.get("PGDATABASE", "acces_soins"))


def moteur():
    """Moteur SQLAlchemy (lecture avec geopandas.read_postgis)."""
    from sqlalchemy import create_engine
    return create_engine("postgresql+psycopg2://", creator=connexion)


def tableau(entetes, lignes):
    out = ["| " + " | ".join(entetes) + " |", "|" + " --- |" * len(entetes)]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in lignes]
    return out


def nombre(n) -> str:
    return f"{n:,.0f}".replace(",", " ")
