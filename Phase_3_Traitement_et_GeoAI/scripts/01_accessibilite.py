"""
01_accessibilite.py — Règles du référentiel, géotraitement vectoriel et analyse réseau
(Phase 3, étape 1)

Règles métier : « Référentiel de programmation des équipements publics et privés d'intérêt
général » (2016), chapitre santé (references/referentiel_EPPIG_2016_sante_uniquement.pdf).

  1. Normes du référentiel → sante.norme_referentiel ; paramètres de sante.niveau_soin.
  2. Scénarios d'accès → sante.scenario_acces :
       niveau 1 : 2,3 km / 30 min À PIED (seule norme de temps du référentiel, CSU) ;
       niveaux 2 et 3 : 15, 30, 45 min en voiture, HYPOTHÈSES (aucune norme de temps) ;
       niveau 1 en voiture 15 min : scénario de sensibilité.
  3. Buffers + overlays dans PostGIS : ST_Buffer (rayon du scénario), ST_Union par scénario,
     ST_Intersection avec la région → sante.zone_tampon.
  4. Analyse réseau : Dijkstra multi-source sur le graphe des tronçons, à pied (sans
     autoroutes, sans sens unique, 4,6 km/h) et en voiture (sens uniques, vitesses par
     type de voie) → sante.temps_acces.
  5. Bilans : population couverte par scénario, tampon contre réseau, provinces, équilibre
     des classes pour le modèle.

Sorties : sql/schema_phase3.sql exécuté ; preuves/rapport_accessibilite.md ;
          preuves/carte_temps_acces.png
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commun as K  # noqa: E402

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

SOURCE = ("Référentiel de programmation des équipements publics et privés d'intérêt général (2016), "
          "ch. 2 Les équipements de santé")
VITESSE_MARCHE_KMH = 4.6       # 2,3 km en 30 min : la norme CSU elle-même
VITESSE_REF_VOITURE_KMH = 40   # rayon des tampons « voiture » : distance en ligne droite pendant le seuil
VITESSE_RACCORD_VOITURE = 20   # centre de l'hexagone → route, route → établissement (piste)
VOIES_INTERDITES_PIETON = ("motorway", "motorway_link")
NIVEAUX = {1: "Soins de proximité", 2: "Hôpital de référence", 3: "Hôpital régional / CHU"}

NORMES = [
    # code, équipement, niveau, pop. seuil, échelle, distance, temps, localisation, page
    ("CSU-1", "Centre de santé urbain niveau 1", 1, 25000, "commune ou arrondissement", 2300, 30,
     "éviter voies ferrées, usines, grands axes, lignes HT, stations-service, décharges, zones inondables et industrielles ; proximité d'espaces verts",
     "p. 39-40, 79"),
    ("CSU-2", "Centre de santé urbain niveau 2", 1, 50000, "commune ou arrondissement", 2300, 30,
     "idem CSU-1", "p. 40, 79"),
    ("HPROX", "Hôpital de proximité (ancien hôpital local)", 2, 70000,
     "province ne justifiant pas un hôpital provincial", None, None,
     "éviter les éléments perturbateurs ; regroupement possible avec un centre de santé", "p. 39, 41, 79"),
    ("CHP", "Centre hospitalier provincial ou préfectoral", 2, 200000, "province / préfecture", None, None,
     "près des grands axes de circulation et d'évacuation ; éviter zones résidentielles et nuisances",
     "p. 39-40, 79"),
    ("CHR", "Centre hospitalier régional", 3, None, "région (un par région)", None, None,
     "idem CHP", "p. 39, 41, 79"),
    ("CHI", "Centre hospitalier interrégional", 3, 2000000, "au moins 2 régions", None, None,
     "idem CHP", "p. 41, 79"),
]


def scenarios():
    s = [("N1_MARCHE_30", 1, "marche", 30, VITESSE_MARCHE_KMH, 2300, True, "CSU-1",
          "norme du référentiel : accessibilité CSU 2,3 km / 30 mn")]
    s.append(("N1_VOITURE_15", 1, "voiture", 15, VITESSE_REF_VOITURE_KMH, 10000, False, None,
              "sensibilité : accès motorisé au premier recours"))
    for niv in (2, 3):
        for seuil in (15, 30, 45):
            s.append((f"N{niv}_VOITURE_{seuil}", niv, "voiture", seuil, VITESSE_REF_VOITURE_KMH,
                      seuil * VITESSE_REF_VOITURE_KMH * 1000 // 60, False, None,
                      "hypothèse : le référentiel ne fixe pas de temps d'accès aux hôpitaux "
                      "(scénarios 15/30/45 min du cadrage)"))
    return s


# ─────────────────────────────────────────────────────────────────────────────
def creer_schema(cx):
    with cx, cx.cursor() as cur:
        cur.execute((K.SQL / "schema_phase3.sql").read_text(encoding="utf-8"))
        execute_values(cur, "INSERT INTO sante.norme_referentiel VALUES %s",
                       [(*n, SOURCE) for n in NORMES])
        execute_values(cur, "INSERT INTO sante.scenario_acces VALUES %s", scenarios())
        # paramètres des niveaux (table de la Phase 2), désormais sourcés
        cur.execute("""
            UPDATE sante.niveau_soin SET seuil_acces_min = 30, pop_cible_par_etab = 25000,
                   source_norme = %(s)s || ', p. 40 et 79 : CSU, 25 000 hab., accessibilité 2,3 km / 30 mn'
             WHERE code_niveau = 1;
            UPDATE sante.niveau_soin SET seuil_acces_min = NULL, pop_cible_par_etab = 200000,
                   source_norme = %(s)s || ', p. 40 et 79 : hôpital provincial, 200 000 hab. ; aucun temps d''accès fixé'
             WHERE code_niveau = 2;
            UPDATE sante.niveau_soin SET seuil_acces_min = NULL, pop_cible_par_etab = NULL,
                   source_norme = %(s)s || ', p. 41 et 79 : un hôpital régional par région ; aucun temps d''accès fixé'
             WHERE code_niveau = 3;
        """, {"s": SOURCE})


def tampons(cx):
    t0 = time.time()
    with cx, cx.cursor() as cur:
        cur.execute("""
            INSERT INTO sante.zone_tampon (code_scenario, nb_etab, surface_km2, geom)
            WITH region AS (SELECT ST_Union(geom) AS geom FROM sante.commune),
                 etab AS (SELECT e.code_niveau, e.geom FROM sante.etablissement e
                          JOIN sante.type_etablissement t USING (code_type) WHERE t.inclus_analyse),
                 fusion AS (SELECT s.code_scenario, count(*) AS nb_etab,
                                   ST_Union(ST_Buffer(e.geom, s.rayon_tampon_m, 16)) AS geom
                            FROM sante.scenario_acces s JOIN etab e USING (code_niveau)
                            GROUP BY s.code_scenario)
            SELECT f.code_scenario, f.nb_etab, ST_Area(x.geom) / 1e6, x.geom
            FROM fusion f, region r,
                 LATERAL (SELECT ST_Multi(ST_CollectionExtract(ST_Intersection(f.geom, r.geom), 3)) AS geom) x
        """)
    return time.time() - t0


# ─────────────────────────────────────────────────────────────────────────────
def graphe(cx, mode):
    """Graphe orienté pondéré en minutes.
    voiture : sens uniques respectés, vitesse du tronçon ;
    marche  : autoroutes exclues, tous les tronçons dans les deux sens, 4,6 km/h."""
    tr = pd.read_sql("SELECT noeud_depart a, noeud_arrivee b, longueur_m, vitesse_kmh, sens_unique, type_voie "
                     "FROM sante.troncon", cx)
    if mode == "marche":
        tr = tr[~tr["type_voie"].isin(VOIES_INTERDITES_PIETON)].copy()
        tr["min"] = tr["longueur_m"] / 1000 / VITESSE_MARCHE_KMH * 60
        tr["sens_unique"] = False
    else:
        tr["min"] = tr["longueur_m"] / 1000 / tr["vitesse_kmh"] * 60
    retour = tr[~tr["sens_unique"]].rename(columns={"a": "b", "b": "a"})
    arcs = pd.concat([tr[["a", "b", "min"]], retour[["a", "b", "min"]]])
    arcs = arcs.groupby(["a", "b"], as_index=False)["min"].min()
    ids = pd.Index(np.unique(np.concatenate([arcs["a"], arcs["b"]])))
    return arcs, ids


def dijkstra_niveau(arcs, ids, etab):
    """Temps de chaque nœud VERS l'établissement le plus proche, raccordement compris :
    graphe inversé, super-nœud S relié à chaque nœud d'établissement par son temps de
    raccordement ; l'établissement retenu est celui dont part le plus court chemin."""
    n = len(ids)
    S = n
    lignes, cols, poids = list(ids.get_indexer(arcs["b"])), list(ids.get_indexer(arcs["a"])), list(arcs["min"])
    e = etab.assign(i=ids.get_indexer(etab["id_noeud"])).sort_values("raccord_min")
    e = e[e["i"] >= 0].drop_duplicates("i")
    lignes += [S] * len(e)
    cols += list(e["i"])
    poids += list(np.maximum(e["raccord_min"], 1e-6))
    g = csr_matrix((poids, (lignes, cols)), shape=(n + 1, n + 1))
    dist, pred = dijkstra(g, directed=True, indices=S, return_predecessors=True)
    racine = np.full(n + 1, -1, dtype=np.int64)
    etab_du_noeud = dict(zip(e["i"], e["id_etab"]))
    for i in np.argsort(dist):
        if i == S or not np.isfinite(dist[i]):
            continue
        p = pred[i]
        racine[i] = etab_du_noeud[i] if p == S else racine[p]
    return dist[:n], racine[:n]


def temps_acces(cx):
    t0 = time.time()
    h3 = pd.read_sql("""SELECT m.h3_index, m.id_noeud, ST_Distance(ST_Centroid(m.geom), n.geom) AS d
                        FROM sante.maille_h3 m JOIN sante.noeud n USING (id_noeud)""", cx)
    etab = pd.read_sql("""SELECT e.id_etab, e.code_niveau, e.id_noeud, ST_Distance(e.geom, n.geom) AS d
                          FROM sante.etablissement e JOIN sante.type_etablissement t USING (code_type)
                          JOIN sante.noeud n USING (id_noeud) WHERE t.inclus_analyse""", cx)
    calculs = {"voiture": [1, 2, 3], "marche": [1]}
    lignes, stats, info = [], {}, {}
    for mode, niveaux in calculs.items():
        arcs, ids = graphe(cx, mode)
        info[mode] = (len(ids), len(arcs))
        v_raccord = VITESSE_MARCHE_KMH if mode == "marche" else VITESSE_RACCORD_VOITURE
        ih = ids.get_indexer(h3["id_noeud"])  # -1 si le nœud n'est pas dans le graphe piéton
        r_h3 = h3["d"].to_numpy() / 1000 / v_raccord * 60
        for niv in niveaux:
            et = etab[etab["code_niveau"] == niv].assign(raccord_min=lambda x: x["d"] / 1000 / v_raccord * 60)
            dist, racine = dijkstra_niveau(arcs, ids, et)
            ok = ih >= 0
            t = np.full(len(h3), np.inf)
            t[ok] = dist[ih[ok]] + r_h3[ok]
            rac = np.full(len(h3), -1)
            rac[ok] = racine[ih[ok]]
            ok &= np.isfinite(t) & (rac >= 0)
            stats[(niv, mode)] = {"etab": len(et), "injoignables": int((~ok).sum())}
            lignes += list(zip(h3["h3_index"][ok].tolist(), [niv] * int(ok.sum()), [mode] * int(ok.sum()),
                               np.round(t[ok], 2).tolist(), rac[ok].tolist()))
    with cx, cx.cursor() as cur:
        execute_values(cur, "INSERT INTO sante.temps_acces (h3_index, code_niveau, mode, temps_min, id_etab) "
                       "VALUES %s", lignes, page_size=10000)
        cur.execute("ANALYZE sante.temps_acces")
    return time.time() - t0, info, stats


# ─────────────────────────────────────────────────────────────────────────────
def carte(sortie):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    eng = K.moteur()
    g = gpd.read_postgis("""SELECT t.code_niveau, t.mode, t.temps_min, m.geom FROM sante.temps_acces t
                            JOIN sante.maille_h3 m USING (h3_index) WHERE m.population > 0""", eng, geom_col="geom")
    prov = gpd.read_postgis("SELECT geom FROM sante.province", eng, geom_col="geom")
    etab = gpd.read_postgis("""SELECT e.code_niveau, e.geom FROM sante.etablissement e
                               JOIN sante.type_etablissement t USING (code_type) WHERE t.inclus_analyse""",
                            eng, geom_col="geom")
    couleurs = ["#1a9850", "#a6d96a", "#fee08b", "#f46d43", "#a50026"]
    panneaux = [(1, "marche", [0, 15, 30, 60, 120, 1e9], ["< 15", "15–30 (norme)", "30–60", "60–120", "> 120 min"],
                 "Niveau 1 à pied — norme CSU 2,3 km / 30 min"),
                (2, "voiture", [0, 15, 30, 45, 60, 1e9], ["< 15", "15–30", "30–45", "45–60", "> 60 min"],
                 "Niveau 2 en voiture (scénarios, sans norme)"),
                (3, "voiture", [0, 15, 30, 45, 60, 1e9], ["< 15", "15–30", "30–45", "45–60", "> 60 min"],
                 "Niveau 3 en voiture (scénarios, sans norme)")]
    fig, axes = plt.subplots(1, 3, figsize=(19, 7.5))
    cmap = ListedColormap(couleurs)
    for ax, (niv, mode, bornes, libelles, titre) in zip(axes, panneaux):
        g[(g["code_niveau"] == niv) & (g["mode"] == mode)].plot(
            ax=ax, column="temps_min", cmap=cmap, norm=BoundaryNorm(bornes, cmap.N), linewidth=0)
        prov.boundary.plot(ax=ax, color="#555", linewidth=0.5)
        etab[etab["code_niveau"] == niv].plot(ax=ax, color="black", markersize=2 if niv == 1 else 12)
        ax.set_title(titre, fontsize=11)
        ax.set_axis_off()
        ax.legend(handles=[mpatches.Patch(color=c, label=l) for c, l in zip(couleurs, libelles)],
                  loc="lower left", fontsize=8, frameon=False)
    fig.suptitle("Temps d'accès par le réseau vers l'établissement le plus proche — hexagones habités "
                 "(EPSG:26191)")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(sortie, dpi=130)
    plt.close(fig)


def rapport(cx, t_tampon, t_reseau, info, stats):
    cov = pd.read_sql("""SELECT code_scenario, code_niveau, mode, seuil_min, normatif, code_province,
                                pop_2024, couvert_reseau, couvert_tampon, temps_min
                         FROM sante.v_couverture_h3 WHERE pop_2024 > 0""", cx)
    sc = pd.read_sql("SELECT * FROM sante.scenario_acces ORDER BY code_niveau, mode DESC, seuil_min", cx)
    prov = pd.read_sql("SELECT code_province, nom FROM sante.province", cx).set_index("code_province")["nom"]
    total = pd.read_sql("SELECT sum(pop_2024) FROM sante.v_maille_pop", cx).iloc[0, 0]
    pct = lambda a, b: f"{100 * a / b:.1f} %" if b else "—"  # noqa: E731

    md = ["# Rapport d'accessibilité — règles du référentiel, géotraitement et réseau", "",
          f"Exécuté le {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} par `scripts/01_accessibilite.py`. "
          f"Couches en {K.CRS}.", "",
          "## Règles métier", "",
          f"Source : *{SOURCE}* (`references/referentiel_EPPIG_2016_sante_uniquement.pdf`), table "
          "`norme_referentiel`.", "",
          *K.tableau(["Norme", "Équipement", "Niveau", "Seuil de population", "Accessibilité", "Page"],
                     [(n[0], n[1], n[2], K.nombre(n[3]) if n[3] else "—",
                       f"{n[5] / 1000:.1f} km / {n[6]} min" if n[5] else "non fixée", n[8]) for n in NORMES]), "",
          "**Conséquence** : seul le premier recours a une norme d'accès (2,3 km / 30 min, sous-entendu à pied : "
          "4,6 km/h). Pour les hôpitaux, le référentiel raisonne en population desservie (province, région), "
          "pas en temps : les seuils en voiture restent des hypothèses, signalées comme telles.", "",
          "## Scénarios", "",
          *K.tableau(["Scénario", "Niveau", "Mode", "Seuil", "Rayon du tampon", "Statut"],
                     [(r.code_scenario, r.code_niveau, r.mode, f"{r.seuil_min} min",
                       f"{r.rayon_tampon_m / 1000:g} km", "**normatif**" if r.normatif else "hypothèse")
                      for r in sc.itertuples()]), "",
          f"Raccordement centre d'hexagone → route et route → établissement : {VITESSE_MARCHE_KMH} km/h à pied, "
          f"{VITESSE_RACCORD_VOITURE} km/h en voiture. Couverture stricte : un établissement ne couvre que "
          "son niveau.", "",
          "## Géotraitement vectoriel (PostGIS)", "",
          f"`ST_Buffer` (rayon du scénario) → `ST_Union` par scénario → `ST_Intersection` avec la région : table "
          f"`zone_tampon` ({t_tampon:.0f} s). Couverture à vol d'oiseau : centre de l'hexagone dans la zone.", "",
          "## Analyse réseau", "",
          *K.tableau(["Mode", "Nœuds", "Arcs", "Règles"], [
              ("voiture", K.nombre(info["voiture"][0]), K.nombre(info["voiture"][1]),
               "sens uniques respectés, vitesse du tronçon"),
              ("marche", K.nombre(info["marche"][0]), K.nombre(info["marche"][1]),
               f"autoroutes exclues, double sens, {VITESSE_MARCHE_KMH} km/h")]), "",
          f"Dijkstra multi-source (graphe inversé, super-nœud relié aux établissements) : {t_reseau:.0f} s. "
          "Table `temps_acces` : temps et établissement le plus proche par hexagone, niveau et mode.", "",
          *K.tableau(["Niveau", "Mode", "Établissements", "Hexagones injoignables"],
                     [(n, m, s["etab"], s["injoignables"]) for (n, m), s in stats.items()]), "",
          f"## Population couverte (population 2024 : {K.nombre(total)})", ""]
    lignes = []
    for r in sc.itertuples():
        d = cov[cov["code_scenario"] == r.code_scenario]
        p = d["pop_2024"].sum()
        rr = d.loc[d["couvert_reseau"], "pop_2024"].sum()
        tp = d.loc[d["couvert_tampon"], "pop_2024"].sum()
        faux = d.loc[d["couvert_tampon"] & ~d["couvert_reseau"], "pop_2024"].sum()
        lignes.append((r.code_scenario, "oui" if r.normatif else "non", pct(tp, p), pct(rr, p),
                       K.nombre(p - rr), K.nombre(faux)))
    md += [*K.tableau(["Scénario", "Normatif", "Couverte (tampon)", "Couverte (réseau)",
                       "Non couverte (réseau)", "Dans le tampon mais hors d'atteinte par le réseau"], lignes), "",
           "La dernière colonne mesure l'erreur d'une analyse à vol d'oiseau.", "",
           "## Par province — scénario normatif N1_MARCHE_30", ""]
    d = cov[cov["code_scenario"] == "N1_MARCHE_30"]
    g = d.groupby("code_province").apply(lambda x: pd.Series({
        "habitants": x["pop_2024"].sum(), "non": x.loc[~x["couvert_reseau"], "pop_2024"].sum(),
        "moy": np.average(x["temps_min"], weights=x["pop_2024"])}), include_groups=False)
    md += [*K.tableau(["Province", "Population", "Hors norme (> 30 min à pied)", "Part", "Temps moyen pondéré"],
                      [(prov[c], K.nombre(r.habitants), K.nombre(r.non), pct(r.non, r.habitants),
                        f"{r.moy:.0f} min") for c, r in g.sort_values("non", ascending=False).iterrows()]), "",
           "## Équilibre des classes (hexagones habités) — choix de la cible du modèle", ""]
    eq = cov.groupby("code_scenario").agg(n=("couvert_reseau", "size"),
                                         blancs=("couvert_reseau", lambda s: int((~s).sum())))
    md += K.tableau(["Scénario", "Hexagones habités", "Zones blanches (réseau)", "Part"],
                    [(s, r.n, r.blancs, pct(r.blancs, r.n)) for s, r in eq.loc[sc["code_scenario"]].iterrows()])
    md += ["", "Carte : `preuves/carte_temps_acces.png`."]
    return "\n".join(md) + "\n"


def main():
    K.PREUVES.mkdir(exist_ok=True)
    cx = K.connexion()
    print("[référentiel, scénarios]")
    creer_schema(cx)
    print("[tampons : buffer, union, intersection]")
    t_tampon = tampons(cx)
    print("[réseau : Dijkstra multi-source, voiture et marche]")
    t_reseau, info, stats = temps_acces(cx)
    print("[carte et rapport]")
    carte(K.PREUVES / "carte_temps_acces.png")
    md = rapport(cx, t_tampon, t_reseau, info, stats)
    (K.PREUVES / "rapport_accessibilite.md").write_text(md, encoding="utf-8")
    cx.close()
    print(md)


if __name__ == "__main__":
    main()
