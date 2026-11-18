"""
02_contraintes_localisation.py — Critères de localisation du référentiel (Phase 3, étape 1 bis)

Le référentiel (p. 39, « Critères de localisation des équipements de santé ») demande :
  CSU et hôpital de proximité : éviter voies ferrées, usines, grands axes routiers, lignes
      à haute tension, stations d'essence, décharges, zones inondables, zones industrielles ;
  hôpitaux provinciaux et régionaux : implantation encouragée près des grands axes de
      circulation et d'évacuation ; éviter les zones résidentielles et les nuisances.

Traduction par overlays dans PostGIS :
  1. objets OSM (extrait Geofabrik de la Phase 1) chargés dans sante.osm_contrainte ;
  2. ST_Buffer de la distance de la règle → ST_Union par catégorie → ST_Intersection avec la
     région → sante.contrainte_localisation ;
  3. pour chaque hexagone H3 : part de surface en zone de nuisance (ST_Intersection /
     ST_Area), proximité d'un grand axe → sante.aptitude_h3 (apte_csu, apte_hopital).

Le référentiel ne chiffre aucune distance : celles d'ici sont des hypothèses, documentées.
Non disponibles dans OSM (extrait Geofabrik) : lignes à haute tension, zones inondables.

Sorties : sante.osm_contrainte, sante.contrainte_localisation, sante.aptitude_h3,
          preuves/rapport_contraintes.md, preuves/carte_contraintes.png
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commun as K  # noqa: E402

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

GEOFABRIK = K.DEPOT / "Phase_1_Acquisition_et_Collecte" / "donnees_brutes" / "osm_routes" / "morocco-latest-free.shp.zip"
BBOX = (K.C.BBOX["ouest"], K.C.BBOX["sud"], K.C.BBOX["est"], K.C.BBOX["nord"])
NUISANCE_M = 100            # hypothèse : distance d'éloignement des nuisances
GRAND_AXE_ACCES_M = 2000    # hypothèse : « à proximité des grands axes » pour les hôpitaux
SEUIL_NUISANCE = 0.5        # un hexagone est apte s'il est à moins de 50 % en zone de nuisance
SEUIL_RESIDENTIEL = 0.5

# catégorie : (couche Geofabrik, classes OSM, équipements visés, effet, distance, règle du référentiel)
CATEGORIES = {
    "voie_ferree": ("gis_osm_railways_free_1", ["rail"], "CSU, hôpitaux", "exclure", NUISANCE_M,
                    "éviter les lignes de chemins de fer"),
    "industrie": ("gis_osm_landuse_a_free_1", ["industrial", "quarry"], "CSU, hôpitaux", "exclure", NUISANCE_M,
                  "éviter usines, zones et unités industrielles"),
    "decharge": ("gis_osm_landuse_a_free_1", ["landfill"], "CSU, hôpitaux", "exclure", NUISANCE_M,
                 "éviter les décharges de déchets"),
    "station_service": ("gis_osm_traffic_free_1|gis_osm_traffic_a_free_1", ["fuel"], "CSU, hôpitaux", "exclure",
                        NUISANCE_M, "éviter les stations d'essence"),
    "grand_axe_nuisance": ("gis_osm_roads_free_1", ["motorway", "motorway_link", "trunk", "trunk_link"],
                           "CSU, hôpital de proximité", "exclure", NUISANCE_M,
                           "éviter les grands axes routiers (bruit, pollution)"),
    "zone_residentielle": ("gis_osm_landuse_a_free_1", ["residential"], "hôpitaux provinciaux et régionaux",
                           "exclure", 0, "éviter la proximité avec les zones résidentielles"),
    "grand_axe_acces": ("gis_osm_roads_free_1", ["motorway", "trunk", "primary"],
                        "hôpitaux provinciaux et régionaux", "favoriser", GRAND_AXE_ACCES_M,
                        "implantation encouragée à proximité des grands axes de circulation et d'évacuation"),
}
NUISANCES_CSU = ["voie_ferree", "industrie", "decharge", "station_service", "grand_axe_nuisance"]
NUISANCES_HOPITAL = ["voie_ferree", "industrie", "decharge", "station_service"]


def charger_osm():
    """Objets OSM des catégories, en EPSG:26191, dans sante.osm_contrainte."""
    morceaux = []
    for cat, (couches, classes, *_rest) in CATEGORIES.items():
        for couche in couches.split("|"):
            g = gpd.read_file(f"zip://{GEOFABRIK.as_posix()}!{couche}.shp", bbox=BBOX)
            g = g[g["fclass"].isin(classes)]
            morceaux.append(gpd.GeoDataFrame({"categorie": cat, "fclass": g["fclass"], "osm_id": g["osm_id"]},
                                             geometry=g.geometry, crs=g.crs))
    osm = pd.concat([m.to_crs(K.CRS) for m in morceaux], ignore_index=True)
    osm = gpd.GeoDataFrame(osm, geometry="geometry", crs=K.CRS).rename_geometry("geom")
    osm.to_postgis("osm_contrainte", K.moteur(), schema="sante", if_exists="replace", index=False)
    return osm["categorie"].value_counts()


def overlays(cx):
    t0 = time.time()
    with cx, cx.cursor() as cur:
        cur.execute("CREATE INDEX ON sante.osm_contrainte USING gist (geom)")
        cur.execute("TRUNCATE sante.contrainte_localisation, sante.aptitude_h3")
        for cat, (couches, classes, equip, effet, dist, regle) in CATEGORIES.items():
            cur.execute("""
                INSERT INTO sante.contrainte_localisation
                SELECT %(cat)s, %(equip)s, %(effet)s, %(dist)s, count(*), %(src)s, %(regle)s,
                       ST_Multi(ST_CollectionExtract(ST_Intersection(
                           ST_Union(CASE WHEN %(dist)s > 0 THEN ST_Buffer(o.geom, %(dist)s, 8)
                                         ELSE ST_MakeValid(o.geom) END),
                           (SELECT ST_Union(geom) FROM sante.commune)), 3))
                FROM sante.osm_contrainte o WHERE o.categorie = %(cat)s
            """, {"cat": cat, "equip": equip, "effet": effet, "dist": dist, "regle": regle,
                  "src": f"OSM Geofabrik {couches} : {', '.join(classes)}"})
        # découpage en petits polygones : les intersections avec 25 000 hexagones restent rapides
        cur.execute("""
            DROP TABLE IF EXISTS tmp_contrainte;
            CREATE TEMP TABLE tmp_contrainte AS
            SELECT categorie, ST_Subdivide(geom, 256) AS geom FROM sante.contrainte_localisation;
            CREATE INDEX ON tmp_contrainte USING gist (geom);
            ANALYZE tmp_contrainte;
        """)
        cur.execute("""
            INSERT INTO sante.aptitude_h3 (h3_index, nuisance_pct, pres_grand_axe, apte_csu, apte_hopital)
            WITH part AS (
                SELECT m.h3_index,
                       coalesce(sum(ST_Area(ST_Intersection(m.geom, c.geom)))
                                FILTER (WHERE c.categorie = ANY(%(csu)s)), 0) / ST_Area(m.geom) AS n_csu,
                       coalesce(sum(ST_Area(ST_Intersection(m.geom, c.geom)))
                                FILTER (WHERE c.categorie = ANY(%(hop)s)), 0) / ST_Area(m.geom) AS n_hop,
                       coalesce(sum(ST_Area(ST_Intersection(m.geom, c.geom)))
                                FILTER (WHERE c.categorie = 'zone_residentielle'), 0) / ST_Area(m.geom) AS resid,
                       bool_or(c.categorie = 'grand_axe_acces') AS axe
                FROM sante.maille_h3 m
                LEFT JOIN tmp_contrainte c ON ST_Intersects(m.geom, c.geom)
                GROUP BY m.h3_index, m.geom)
            SELECT h3_index, least(n_csu, 1), coalesce(axe, false),
                   n_csu < %(sn)s,
                   coalesce(axe, false) AND n_hop < %(sn)s AND resid < %(sr)s
            FROM part
        """, {"csu": NUISANCES_CSU, "hop": NUISANCES_HOPITAL, "sn": SEUIL_NUISANCE, "sr": SEUIL_RESIDENTIEL})
        # ST_Union de sous-polygones qui se chevauchent : la part peut dépasser 1 → bornée
    return time.time() - t0


def carte(sortie):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    eng = K.moteur()
    c = gpd.read_postgis("SELECT categorie, effet, geom FROM sante.contrainte_localisation", eng, geom_col="geom")
    a = gpd.read_postgis("""SELECT a.apte_csu, a.apte_hopital, m.population, m.geom FROM sante.aptitude_h3 a
                            JOIN sante.maille_h3 m USING (h3_index) WHERE m.population > 0""", eng, geom_col="geom")
    prov = gpd.read_postgis("SELECT geom FROM sante.province", eng, geom_col="geom")
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    ax = axes[0]
    couleurs = {"grand_axe_acces": "#c7e9c0", "zone_residentielle": "#fdd0a2", "industrie": "#6a51a3",
                "voie_ferree": "#252525", "station_service": "#e31a1c", "decharge": "#8c510a",
                "grand_axe_nuisance": "#fb6a4a"}
    for cat in couleurs:
        c[c["categorie"] == cat].plot(ax=ax, color=couleurs[cat], linewidth=0)
    prov.boundary.plot(ax=ax, color="#555", linewidth=0.5)
    ax.legend(handles=[mpatches.Patch(color=v, label=k.replace("_", " ")) for k, v in couleurs.items()],
              loc="lower left", fontsize=8, frameon=False)
    ax.set_title("Contraintes de localisation (référentiel p. 39)")
    ax.set_axis_off()
    ax = axes[1]
    a["classe"] = a["apte_csu"].astype(int) + 2 * a["apte_hopital"].astype(int)
    pal = {0: "#bdbdbd", 1: "#74add1", 2: "#fdae61", 3: "#1a9850"}
    for k, col in pal.items():
        a[a["classe"] == k].plot(ax=ax, color=col, linewidth=0)
    prov.boundary.plot(ax=ax, color="#555", linewidth=0.5)
    ax.legend(handles=[mpatches.Patch(color=pal[0], label="inapte"), mpatches.Patch(color=pal[1], label="apte CSU"),
                       mpatches.Patch(color=pal[2], label="apte hôpital"),
                       mpatches.Patch(color=pal[3], label="apte CSU et hôpital")],
              loc="lower left", fontsize=8, frameon=False)
    ax.set_title("Aptitude des hexagones habités à accueillir un établissement")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(sortie, dpi=130)
    plt.close(fig)


def rapport(cx, n_osm, duree):
    c = pd.read_sql("""SELECT categorie, equipements, effet, distance_m, nb_objets, regle, surface
                       FROM (SELECT *, ST_Area(geom) / 1e6 AS surface FROM sante.contrainte_localisation) x
                       ORDER BY effet, categorie""", cx)
    a = pd.read_sql("""SELECT a.*, p.pop_2024 FROM sante.aptitude_h3 a JOIN sante.v_maille_pop p USING (h3_index)
                       WHERE p.pop_2024 > 0""", cx)
    md = ["# Rapport — critères de localisation du référentiel", "",
          f"Exécuté le {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} par `scripts/02_contraintes_localisation.py` "
          f"({duree:.0f} s). Couches en {K.CRS}.", "",
          "Règles : référentiel EPPIG 2016, p. 39 (« Critères de localisation des équipements de santé »). "
          "Le référentiel ne chiffre aucune distance : "
          f"**{NUISANCE_M} m** d'éloignement des nuisances et **{GRAND_AXE_ACCES_M / 1000:g} km** pour la proximité "
          "des grands axes sont des hypothèses de travail.", "",
          "## Overlays (PostGIS)", "",
          "`ST_Buffer` (distance de la règle) → `ST_Union` par catégorie → `ST_Intersection` avec la région : table "
          "`contrainte_localisation`. Puis, pour chaque hexagone, `ST_Intersection` / `ST_Area` avec les zones : "
          "table `aptitude_h3`.", "",
          *K.tableau(["Catégorie", "Règle du référentiel", "Équipements", "Effet", "Distance", "Objets OSM", "Surface"],
                     [(r.categorie, r.regle, r.equipements, r.effet, f"{r.distance_m} m", r.nb_objets,
                       f"{r.surface:,.0f} km²".replace(",", " ")) for r in c.itertuples()]), "",
          "**Non disponibles** (absents de l'extrait OSM Geofabrik) : lignes à haute tension, zones inondables. "
          "La proximité « encouragée » des espaces verts n'est pas utilisée (critère de confort, pas d'exclusion).", "",
          "## Aptitude des hexagones", "",
          f"- **apte CSU** : moins de {SEUIL_NUISANCE:.0%} de l'hexagone en zone de nuisance (voies ferrées, industrie, "
          "décharges, stations-service, grands axes) ;",
          f"- **apte hôpital** : à moins de {GRAND_AXE_ACCES_M / 1000:g} km d'une autoroute, voie express ou route "
          f"principale, moins de {SEUIL_NUISANCE:.0%} en zone de nuisance et moins de {SEUIL_RESIDENTIEL:.0%} en zone "
          "résidentielle.", "",
          *K.tableau(["", "Hexagones habités", "Population 2024"], [
              ("total", len(a), K.nombre(a["pop_2024"].sum())),
              ("apte CSU", int(a["apte_csu"].sum()), K.nombre(a.loc[a["apte_csu"], "pop_2024"].sum())),
              ("apte hôpital", int(a["apte_hopital"].sum()), K.nombre(a.loc[a["apte_hopital"], "pop_2024"].sum())),
          ]), "",
          "Ces couches serviront à écarter les sites candidats non conformes au référentiel (étape d'implantation) "
          "et de variables de contexte pour le modèle.", "",
          "Carte : `preuves/carte_contraintes.png`."]
    return "\n".join(md) + "\n"


def main():
    cx = K.connexion()
    t0 = time.time()
    print("[objets OSM]")
    n_osm = charger_osm()
    print(n_osm.to_string())
    print("[overlays : buffer, union, intersection]")
    overlays(cx)
    print("[carte et rapport]")
    carte(K.PREUVES / "carte_contraintes.png")
    md = rapport(cx, n_osm, time.time() - t0)
    (K.PREUVES / "rapport_contraintes.md").write_text(md, encoding="utf-8")
    cx.close()
    print(md)


if __name__ == "__main__":
    main()
