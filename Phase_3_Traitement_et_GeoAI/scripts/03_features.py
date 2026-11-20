"""
03_features.py — Variables de contexte des hexagones H3 (Phase 3, étape 2a)

Construit sante.feature_h3 : une ligne par hexagone habité, avec la cible du scénario
normatif N1_MARCHE_30 et des variables de CONTEXTE territorial.

Règle anti-fuite : aucune variable ne dépend de la position des établissements de santé
(ni distance, ni nombre, ni temps), ni de la distance de raccordement de l'hexagone au
réseau, qui entre directement dans le calcul du temps d'accès (la cible).

Variables :
  population      log_pop, log_pop_k1, log_pop_k2 (hexagone, voisinage H3 à 1 et 2 anneaux)
  commune         urbaine, log_pop_commune, log_densite_commune
  réseau routier  long_route_km, part_piste, nb_noeuds, vitesse_moy, dist_route_principale_m
                  (longueurs par ST_Intersection des tronçons avec l'hexagone)
  urbanisation    dist_ville_m (ville ou bourg OSM le plus proche), part_residentielle
  référentiel     nuisance_pct, pres_grand_axe (étape 1 bis)
  (pour le découpage seulement, pas des variables : bloc_h3_r5, code_province)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commun as K  # noqa: E402

import geopandas as gpd  # noqa: E402
import h3  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

GEOFABRIK = K.DEPOT / "Phase_1_Acquisition_et_Collecte" / "donnees_brutes" / "osm_routes" / "morocco-latest-free.shp.zip"
SCENARIO = "N1_MARCHE_30"
VOIES_PRINCIPALES = ("motorway", "trunk", "primary", "secondary")
RESOLUTION_BLOC = 5   # blocs H3 de ~250 km² pour le découpage spatial

FEATURES = ["log_pop", "log_pop_k1", "log_pop_k2", "urbaine", "log_pop_commune", "log_densite_commune",
            "long_route_km", "part_piste", "nb_noeuds", "vitesse_moy", "dist_route_principale_m",
            "dist_ville_m", "part_residentielle", "nuisance_pct", "pres_grand_axe"]

SQL_RESEAU = """
WITH hex AS (SELECT h3_index, geom FROM sante.maille_h3 WHERE population > 0),
seg AS (
    SELECT h.h3_index, t.type_voie, t.vitesse_kmh,
           ST_Length(ST_Intersection(t.geom, h.geom)) AS l
    FROM hex h JOIN sante.troncon t ON ST_Intersects(t.geom, h.geom))
SELECT h3_index,
       sum(l) / 1000 AS long_route_km,
       coalesce(sum(l) FILTER (WHERE type_voie LIKE 'track%%') / NULLIF(sum(l), 0), 0) AS part_piste,
       sum(l * vitesse_kmh) / NULLIF(sum(l), 0) AS vitesse_moy
FROM seg GROUP BY h3_index
"""

SQL_BASE = f"""
SELECT p.h3_index, p.code_hcp, c.code_province, p.pop_2024,
       (split_part(p.code_hcp, '.', 3) = '01') AS urbaine,
       c.pop_2024 AS pop_commune, ST_Area(c.geom) / 1e6 AS surface_commune_km2,
       a.nuisance_pct, a.pres_grand_axe,
       (SELECT count(*) FROM sante.noeud n WHERE ST_Within(n.geom, p.geom)) AS nb_noeuds,
       (SELECT ST_Distance(ST_Centroid(p.geom), t.geom) FROM sante.troncon t
         WHERE t.type_voie IN {VOIES_PRINCIPALES} ORDER BY t.geom <-> ST_Centroid(p.geom) LIMIT 1)
            AS dist_route_principale_m,
       coalesce((SELECT sum(ST_Area(ST_Intersection(p.geom, z.geom))) / ST_Area(p.geom)
                 FROM sante.contrainte_localisation z WHERE z.categorie = 'zone_residentielle'
                   AND ST_Intersects(p.geom, z.geom)), 0) AS part_residentielle,
       ST_X(ST_Centroid(p.geom)) AS x, ST_Y(ST_Centroid(p.geom)) AS y,
       t.temps_min,
       (t.temps_min > s.seuil_min) AS hors_norme
FROM sante.v_maille_pop p
JOIN sante.commune c USING (code_hcp)
JOIN sante.aptitude_h3 a USING (h3_index)
JOIN sante.scenario_acces s ON s.code_scenario = '{SCENARIO}'
JOIN sante.temps_acces t ON t.h3_index = p.h3_index AND t.code_niveau = s.code_niveau AND t.mode = s.mode
                        AND t.couverture = s.couverture
WHERE p.pop_2024 > 0
"""


def voisinage(df, k):
    """Population du voisinage H3 (anneaux 0..k), hexagones inhabités compris (0)."""
    pop = dict(zip(df["h3_index"], df["pop_2024"]))
    return [sum(pop.get(v, 0.0) for v in h3.grid_disk(c, k)) for c in df["h3_index"]]


def dist_villes(df):
    lieux = gpd.read_file(f"zip://{GEOFABRIK.as_posix()}!gis_osm_places_free_1.shp",
                          bbox=(K.C.BBOX["ouest"], K.C.BBOX["sud"], K.C.BBOX["est"], K.C.BBOX["nord"]))
    villes = lieux[lieux["fclass"].isin(["city", "town"])].to_crs(K.CRS)
    pts = gpd.GeoDataFrame(df[["h3_index"]], geometry=gpd.points_from_xy(df["x"], df["y"]), crs=K.CRS)
    j = gpd.sjoin_nearest(pts, villes[["geometry"]], distance_col="d")
    return j[~j.index.duplicated()]["d"].reindex(pts.index).to_numpy(), len(villes)


def main():
    t0 = time.time()
    cx = K.connexion()
    print("[variables de base, réseau]")
    df = pd.read_sql(SQL_BASE, cx)
    res = pd.read_sql(SQL_RESEAU, cx)
    df = df.merge(res, on="h3_index", how="left")
    df[["long_route_km", "part_piste"]] = df[["long_route_km", "part_piste"]].fillna(0)
    df["vitesse_moy"] = df["vitesse_moy"].fillna(0)
    print("[voisinage H3, villes]")
    df["log_pop"] = np.log1p(df["pop_2024"])
    df["log_pop_k1"] = np.log1p(voisinage(df, 1))
    df["log_pop_k2"] = np.log1p(voisinage(df, 2))
    df["log_pop_commune"] = np.log1p(df["pop_commune"])
    df["log_densite_commune"] = np.log1p(df["pop_commune"] / df["surface_commune_km2"])
    df["dist_ville_m"], n_villes = dist_villes(df)
    df["bloc_h3_r5"] = [h3.cell_to_parent(c, RESOLUTION_BLOC) for c in df["h3_index"]]
    df["urbaine"] = df["urbaine"].astype(int)
    df["pres_grand_axe"] = df["pres_grand_axe"].astype(int)
    df["hors_norme"] = df["hors_norme"].astype(int)

    sortie = df[["h3_index", "code_province", "bloc_h3_r5", "pop_2024", "temps_min", "hors_norme", *FEATURES]]
    with cx, cx.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS sante.feature_h3 CASCADE")
    sortie.to_sql("feature_h3", K.moteur(), schema="sante", index=False)
    with cx, cx.cursor() as cur:
        cur.execute("""ALTER TABLE sante.feature_h3 ADD PRIMARY KEY (h3_index),
                       ADD FOREIGN KEY (h3_index) REFERENCES sante.maille_h3 (h3_index) ON DELETE CASCADE;
                       COMMENT ON TABLE sante.feature_h3 IS
                       'Variables de contexte des hexagones habités et cible hors_norme du scénario N1_MARCHE_30 '
                       '(> 30 min à pied du centre de niveau 1 le plus proche). Aucune variable liée aux établissements.'""")
    cx.close()
    print(f"{len(sortie)} hexagones, {len(FEATURES)} variables, {n_villes} villes OSM, "
          f"{df['bloc_h3_r5'].nunique()} blocs H3 r5, {time.time() - t0:.0f} s")
    print(sortie[FEATURES + ["hors_norme"]].describe().T[["mean", "min", "max"]].round(2).to_string())


if __name__ == "__main__":
    main()
