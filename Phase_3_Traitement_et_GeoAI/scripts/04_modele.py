"""
04_modele.py — Modèle Geo-AI : apprentissage, évaluation, comparaison, import PostGIS
(Phase 3, étape 2b)

Problème : CLASSIFICATION binaire des hexagones H3 habités.
  cible  hors_norme = 1 si le centre de niveau 1 le plus proche est à plus de 30 min à pied
         (norme CSU du référentiel EPPIG 2016 : 2,3 km / 30 min), calculé à l'étape 1 ;
  entrée variables de contexte territorial (03_features.py), sans lien avec les établissements.
Question : le contexte d'un territoire suffit-il à reconnaître une zone hors norme, et
quels facteurs l'expliquent ? (repérage de zones à risque, appui au choix des sites)

Protocole :
  1. Découpage SPATIAL : 25 % des blocs H3 de résolution 5 (~250 km²) forment le jeu de test,
     tenu à l'écart jusqu'à l'évaluation finale (GroupShuffleSplit, graine fixe).
  2. Réglage des hyperparamètres par validation croisée spatiale sur l'entraînement
     (GroupKFold, 5 plis, groupes = blocs). La même CV avec plis ALÉATOIRES est calculée
     pour mesurer l'optimisme dû à l'autocorrélation spatiale.
  3. Modèles : classe majoritaire (baseline triviale), régression logistique sur 2 variables
     (baseline simple), forêt aléatoire, gradient boosting (HistGradientBoosting, principal).
  4. Évaluation sur le test : précision, rappel, F1 des deux classes, F1 macro, exactitude
     équilibrée, ROC-AUC, PR-AUC de la classe minoritaire, matrice de confusion, rappel
     pondéré par la population ; importance par permutation ; I de Moran des résidus.
  5. Import PostGIS : sante.modele_geoai (métadonnées), sante.prediction_h3 (couche dérivée).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commun as K  # noqa: E402

import h3  # noqa: E402
import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from psycopg2.extras import Json, execute_values  # noqa: E402
from sklearn.dummy import DummyClassifier  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, confusion_matrix,  # noqa: E402
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, GroupKFold, GroupShuffleSplit, KFold, cross_val_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from importlib import import_module  # noqa: E402

FEATURES = import_module("03_features").FEATURES
GRAINE = 42
PART_TEST = 0.25
SEUIL = 0.5
CIBLE = "hors_norme : temps à pied > 30 min vers le centre de niveau 1 le plus proche (scénario N1_MARCHE_30)"
VARIABLES_BASELINE = ["log_pop_k1", "dist_ville_m"]


def charger():
    df = pd.read_sql("SELECT * FROM sante.feature_h3", K.moteur())
    return df


def decouper(df):
    gss = GroupShuffleSplit(n_splits=1, test_size=PART_TEST, random_state=GRAINE)
    i_train, i_test = next(gss.split(df, df["hors_norme"], groups=df["bloc_h3_r5"]))
    return df.iloc[i_train].reset_index(drop=True), df.iloc[i_test].reset_index(drop=True)


def modeles():
    return {
        "classe_majoritaire": ("baseline", DummyClassifier(strategy="most_frequent"), None, ["log_pop"]),
        "logistique_2_variables": ("baseline", make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)), None, VARIABLES_BASELINE),
        "foret_aleatoire": ("principal", RandomForestClassifier(
            n_estimators=400, class_weight="balanced", n_jobs=-1, random_state=GRAINE),
            {"max_depth": [8, 16, None], "min_samples_leaf": [5, 20]}, FEATURES),
        "gradient_boosting": ("principal", HistGradientBoostingClassifier(
            class_weight="balanced", max_iter=400, early_stopping=False, random_state=GRAINE),
            {"learning_rate": [0.03, 0.1], "max_leaf_nodes": [15, 31], "min_samples_leaf": [20, 60],
             "l2_regularization": [0.0, 1.0]}, FEATURES),
    }


def metriques(y, p, proba, pop):
    vn, fp, fn, vp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    return {
        "precision_test": precision_score(y, p, zero_division=0), "rappel_test": recall_score(y, p, zero_division=0),
        "f1_test": f1_score(y, p, zero_division=0), "f1_desservi_test": f1_score(y, p, pos_label=0, zero_division=0),
        "f1_macro_test": f1_score(y, p, average="macro", zero_division=0),
        "exactitude_equilibree_test": balanced_accuracy_score(y, p),
        "roc_auc_test": roc_auc_score(y, proba) if len(set(proba)) > 1 else 0.5,
        "pr_auc_desservi_test": average_precision_score(1 - y, 1 - proba),
        "rappel_pondere_pop_test": float(pop[(y == 1) & (p == 1)].sum() / pop[y == 1].sum()),
        "matrice_confusion": {"vn": int(vn), "fp": int(fp), "fn": int(fn), "vp": int(vp)},
    }


def moran_residus(hexs, residus):
    """I de Moran des résidus (voisinage H3 à 1 anneau) : proche de 0 = erreurs sans structure spatiale."""
    idx = {h: i for i, h in enumerate(hexs)}
    z = residus - residus.mean()
    num, w = 0.0, 0
    for i, h in enumerate(hexs):
        for v in h3.grid_ring(h, 1):
            j = idx.get(v)
            if j is not None:
                num += z[i] * z[j]
                w += 1
    return float(len(z) / w * num / (z ** 2).sum()) if w else float("nan")


def version_git():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=K.DEPOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "inconnue"


# ─────────────────────────────────────────────────────────────────────────────
def figures(res, test, principal, importance):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import geopandas as gpd

    fig, axes = plt.subplots(1, len(res), figsize=(4.2 * len(res), 3.8))
    for ax, (nom, r) in zip(axes, res.items()):
        m = r["metriques"]["matrice_confusion"]
        mat = np.array([[m["vn"], m["fp"]], [m["fn"], m["vp"]]])
        ax.imshow(mat, cmap="Blues")
        for (i, j), v in np.ndenumerate(mat):
            ax.text(j, i, v, ha="center", va="center", color="white" if v > mat.max() / 2 else "black")
        ax.set_xticks([0, 1], ["prédit desservi", "prédit hors norme"], fontsize=8)
        ax.set_yticks([0, 1], ["desservi", "hors norme"], fontsize=8)
        ax.set_title(f"{nom}\nF1 macro {r['metriques']['f1_macro_test']:.2f}", fontsize=9)
    fig.suptitle("Matrices de confusion — jeu de test spatial")
    fig.tight_layout()
    fig.savefig(K.PREUVES / "matrice_confusion.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    imp = importance.sort_values("moyenne")
    ax.barh(imp.index, imp["moyenne"], xerr=imp["ecart_type"], color="#4575b4")
    ax.set_xlabel("baisse du F1 macro quand la variable est permutée (jeu de test)")
    ax.set_title(f"Importance par permutation — {principal}")
    fig.tight_layout()
    fig.savefig(K.PREUVES / "importance_variables.png", dpi=130)
    plt.close(fig)

    g = gpd.read_postgis("""SELECT p.jeu, p.erreur, p.probabilite, p.geom FROM sante.prediction_h3 p
                            JOIN sante.modele_geoai m USING (id_modele) WHERE m.nom = %(n)s""",
                         K.moteur(), geom_col="geom", params={"n": principal})
    prov = gpd.read_postgis("SELECT geom FROM sante.province", K.moteur(), geom_col="geom")
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    g.plot(ax=axes[0], column="probabilite", cmap="RdYlGn_r", vmin=0, vmax=1, linewidth=0, legend=True,
           legend_kwds={"label": "probabilité « hors norme »", "shrink": 0.6})
    axes[0].set_title("Probabilité prédite (tous les hexagones habités)")
    pal = {"VP": "#d73027", "VN": "#1a9850", "FP": "#fdae61", "FN": "#4575b4"}
    g[g["jeu"] == "train"].plot(ax=axes[1], color="#e0e0e0", linewidth=0)
    for k, c in pal.items():
        g[(g["jeu"] == "test") & (g["erreur"] == k)].plot(ax=axes[1], color=c, linewidth=0, label=k)
    import matplotlib.patches as mpatches
    axes[1].legend(handles=[mpatches.Patch(color="#e0e0e0", label="entraînement")] +
                   [mpatches.Patch(color=c, label={"VP": "vrai hors norme", "VN": "vrai desservi",
                                                   "FP": "faux hors norme", "FN": "hors norme manqué"}[k])
                    for k, c in pal.items()], loc="lower left", fontsize=8, frameon=False)
    axes[1].set_title("Jeu de test spatial : erreurs du modèle")
    for ax in axes:
        prov.boundary.plot(ax=ax, color="#555", linewidth=0.5)
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(K.PREUVES / "carte_predictions.png", dpi=130)
    plt.close(fig)


def importer(cx, df_all, train, test, res, principal, version):
    with cx, cx.cursor() as cur:
        cur.execute((K.SQL / "schema_modele.sql").read_text(encoding="utf-8"))
        ids = {}
        for nom, r in res.items():
            m = r["metriques"]
            cur.execute("""
                INSERT INTO sante.modele_geoai (nom, role, algorithme, hyperparametres, features, cible, decoupage,
                    n_train, n_test, seuil_decision, precision_test, rappel_test, f1_test, f1_desservi_test,
                    f1_macro_test, exactitude_equilibree_test, roc_auc_test, pr_auc_desservi_test,
                    rappel_pondere_pop_test, matrice_confusion, f1_macro_cv_spatial, f1_macro_cv_aleatoire,
                    version_donnees)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_modele""",
                (nom, r["role"], r["algorithme"], Json(r["hyperparametres"]), r["features"], CIBLE,
                 f"spatial : {PART_TEST:.0%} des blocs H3 r5 en test (GroupShuffleSplit, graine {GRAINE}) ; "
                 "réglage par GroupKFold 5 plis sur l'entraînement",
                 len(train), len(test), SEUIL,
                 *[float(m[k]) for k in ("precision_test", "rappel_test", "f1_test", "f1_desservi_test",
                                         "f1_macro_test", "exactitude_equilibree_test", "roc_auc_test",
                                         "pr_auc_desservi_test", "rappel_pondere_pop_test")],
                 Json(m["matrice_confusion"]), r.get("cv_spatial"), r.get("cv_aleatoire"), version))
            ids[nom] = cur.fetchone()[0]
        r = res[principal]
        lignes = []
        for jeu, d in (("train", train), ("test", test)):
            proba = r["estimateur"].predict_proba(d[FEATURES])[:, 1]
            pred = (proba >= SEUIL).astype(int)
            y = d["hors_norme"].to_numpy()
            err = np.where(pred == y, np.where(y == 1, "VP", "VN"), np.where(pred == 1, "FP", "FN"))
            lignes += list(zip(d["h3_index"], [ids[principal]] * len(d), [jeu] * len(d), y.tolist(),
                               pred.tolist(), proba.round(4).tolist(), err.tolist()))
        execute_values(cur, """INSERT INTO sante.prediction_h3 (h3_index, id_modele, jeu, classe_reelle,
                               classe_predite, probabilite, erreur, geom)
                               SELECT v.h, v.m, v.j, v.y, v.p, v.pr, v.e, m.geom
                               FROM (VALUES %s) v(h, m, j, y, p, pr, e) JOIN sante.maille_h3 m ON m.h3_index = v.h""",
                       lignes, page_size=5000)
    return ids


def rapport(df, train, test, res, principal, importance, moran, ids, duree, version):
    pct = lambda s: f"{100 * s.mean():.1f} %"  # noqa: E731
    lignes = []
    for nom, r in res.items():
        m = r["metriques"]
        lignes.append((nom, r["role"], f"{m['precision_test']:.3f}", f"{m['rappel_test']:.3f}", f"{m['f1_test']:.3f}",
                       f"{m['f1_desservi_test']:.3f}", f"**{m['f1_macro_test']:.3f}**",
                       f"{m['exactitude_equilibree_test']:.3f}", f"{m['roc_auc_test']:.3f}",
                       f"{m['pr_auc_desservi_test']:.3f}", f"{m['rappel_pondere_pop_test']:.3f}"))
    p = res[principal]
    md = ["# Rapport du modèle Geo-AI — zones hors norme d'accès au premier recours", "",
          f"Exécuté le {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} par `scripts/04_modele.py` ({duree:.0f} s), "
          f"données du commit `{version}`.", "",
          "## Formulation", "",
          "| | |", "| --- | --- |",
          "| Tâche | classification binaire supervisée |",
          "| Unité | hexagone H3 habité (résolution 8, ≈ 0,74 km²), EPSG:26191 |",
          f"| Cible | {CIBLE} ; norme du référentiel EPPIG 2016 (CSU : 2,3 km / 30 mn) |",
          "| Classe positive | hors norme (1) ; classe minoritaire : desservi (0) |",
          f"| Variables | {len(FEATURES)} variables de contexte : {', '.join(f'`{f}`' for f in FEATURES)} |",
          "| Exclues (fuite) | toute distance, tout nombre ou temps lié aux établissements ; la distance de "
          "raccordement de l'hexagone au réseau (elle entre dans le calcul de la cible) ; les coordonnées |", "",
          "## Jeux d'entraînement et de test", "",
          *K.tableau(["Jeu", "Hexagones", "Blocs H3 r5", "Hors norme", "Population 2024"], [
              ("entraînement", len(train), train["bloc_h3_r5"].nunique(), pct(train["hors_norme"]),
               K.nombre(train["pop_2024"].sum())),
              ("test", len(test), test["bloc_h3_r5"].nunique(), pct(test["hors_norme"]),
               K.nombre(test["pop_2024"].sum()))]), "",
          f"Découpage **spatial** : {PART_TEST:.0%} des blocs H3 de résolution 5 (≈ 250 km²) tenus à l'écart "
          f"(graine {GRAINE}), jamais utilisés pour le réglage. Un hexagone et ses voisins sont donc du même côté.", "",
          "## Résultats sur le jeu de test", "",
          *K.tableau(["Modèle", "Rôle", "Précision", "Rappel", "F1 hors norme", "F1 desservi", "F1 macro",
                      "Exactitude équilibrée", "ROC-AUC", "PR-AUC desservi", "Rappel pondéré population"], lignes), "",
          "Le F1 de la classe « hors norme » est trompeur ici (80 % des hexagones) : la classe majoritaire seule "
          "atteint déjà un F1 élevé sans rien apprendre. Les critères de comparaison sont le **F1 macro**, "
          "l'**exactitude équilibrée** et la **PR-AUC de la classe desservie**.", "",
          "Matrices de confusion : `preuves/matrice_confusion.png`. Carte des erreurs : `preuves/carte_predictions.png`.",
          "", "## Validation croisée : spatiale contre aléatoire (entraînement)", "",
          *K.tableau(["Modèle", "F1 macro, CV spatiale (GroupKFold)", "F1 macro, CV aléatoire (KFold)", "Écart"],
                     [(n, f"{r['cv_spatial']:.3f}", f"{r['cv_aleatoire']:.3f}",
                       f"{r['cv_aleatoire'] - r['cv_spatial']:+.3f}")
                      for n, r in res.items() if r.get("cv_spatial") is not None]), "",
          "L'écart mesure l'optimisme d'une validation aléatoire : des hexagones voisins, très semblables, se "
          "retrouvent des deux côtés. C'est la raison du découpage spatial.", "",
          f"## Modèle principal retenu : `{principal}`", "",
          f"- algorithme : {p['algorithme']} ;",
          f"- hyperparamètres (choisis par CV spatiale, critère F1 macro) : `{json.dumps(p['hyperparametres'])}` ;",
          f"- seuil de décision : {SEUIL} (non réglé sur le test) ;",
          f"- I de Moran des résidus sur le test (voisinage H3) : **{moran:.3f}** "
          "(0 = erreurs sans structure spatiale ; > 0 = erreurs regroupées).", "",
          "**Importance par permutation** (jeu de test, baisse du F1 macro, 10 répétitions) :", "",
          *K.tableau(["Variable", "Importance", "Écart-type"],
                     [(i, f"{r.moyenne:.3f}", f"{r.ecart_type:.3f}")
                      for i, r in importance.sort_values("moyenne", ascending=False).iterrows()]), "",
          "Figure : `preuves/importance_variables.png`.", "",
          "## PostGIS", "",
          f"- `sante.modele_geoai` : {len(ids)} modèles (date, algorithme, hyperparamètres, variables, découpage, "
          "métriques de test et de CV, commit des données) ;",
          f"- `sante.prediction_h3` : prédiction du modèle principal (id {ids[principal]}) pour les {len(df)} "
          "hexagones, jeu, probabilité, type d'erreur, géométrie en EPSG:26191.", "",
          "## Limites", "",
          "- La cible est calculée, pas observée : elle hérite des hypothèses de l'étape 1 (réseau piéton limité "
          "aux routes, vitesse uniforme de 4,6 km/h, 93 centres en position approchée).",
          "- WorldPop date de 2020 ; il est recalé sur le RGPH 2024 au niveau communal seulement.",
          "- Le modèle reconnaît des CONTEXTES de zone hors norme ; il ne remplace pas le calcul réseau, exact, "
          "dès que les établissements sont connus.",
          "- Classes déséquilibrées (80 / 20) : pondération `class_weight='balanced'`, seuil fixe à 0,5."]
    return "\n".join(md) + "\n"


def main():
    t0 = time.time()
    df = charger()
    train, test = decouper(df)
    print(f"[découpage] train {len(train)} ({train['bloc_h3_r5'].nunique()} blocs), "
          f"test {len(test)} ({test['bloc_h3_r5'].nunique()} blocs)")
    gkf = GroupKFold(n_splits=5)
    res = {}
    for nom, (role, est, grille, variables) in modeles().items():
        print(f"[{nom}]")
        X, y, g = train[variables], train["hors_norme"], train["bloc_h3_r5"]
        if grille:
            gs = GridSearchCV(est, grille, scoring="f1_macro", cv=gkf, n_jobs=-1)
            gs.fit(X, y, groups=g)
            est, hp = gs.best_estimator_, gs.best_params_
        else:
            est.fit(X, y)
            hp = {k: v for k, v in est.get_params().items() if isinstance(v, (int, float, str, bool)) or v is None} \
                if nom == "classe_majoritaire" else {"variables": variables, "class_weight": "balanced"}
        cv_s = cross_val_score(est, X, y, groups=g, cv=gkf, scoring="f1_macro").mean()
        cv_a = cross_val_score(est, X, y, cv=KFold(5, shuffle=True, random_state=GRAINE), scoring="f1_macro").mean()
        proba = est.predict_proba(test[variables])[:, 1]
        m = metriques(test["hors_norme"].to_numpy(), (proba >= SEUIL).astype(int), proba, test["pop_2024"].to_numpy())
        res[nom] = {"role": role, "estimateur": est, "hyperparametres": {k: (v if not isinstance(v, np.generic)
                    else v.item()) for k, v in hp.items()}, "features": variables, "metriques": m,
                    "algorithme": type(est[-1] if hasattr(est, "steps") else est).__name__,
                    "cv_spatial": float(cv_s), "cv_aleatoire": float(cv_a)}
        print(f"   F1 macro test {m['f1_macro_test']:.3f} | CV spatiale {cv_s:.3f} | CV aléatoire {cv_a:.3f}")

    principaux = [n for n, r in res.items() if r["role"] == "principal"]
    principal = max(principaux, key=lambda n: res[n]["cv_spatial"])   # choisi sur la CV, pas sur le test
    est = res[principal]["estimateur"]
    print(f"[principal : {principal}] importance par permutation, Moran")
    pi = permutation_importance(est, test[FEATURES], test["hors_norme"], scoring="f1_macro",
                                n_repeats=10, random_state=GRAINE, n_jobs=-1)
    importance = pd.DataFrame({"moyenne": pi.importances_mean, "ecart_type": pi.importances_std}, index=FEATURES)
    residus = test["hors_norme"].to_numpy() - est.predict_proba(test[FEATURES])[:, 1]
    moran = moran_residus(test["h3_index"].tolist(), residus)

    K.DONNEES.mkdir(exist_ok=True)
    joblib.dump({"modele": est, "features": FEATURES, "seuil": SEUIL}, K.DONNEES / "modele_principal.joblib")
    version = version_git()
    cx = K.connexion()
    print("[import PostGIS]")
    ids = importer(cx, df, train, test, res, principal, version)
    print("[figures, rapport]")
    figures(res, test, principal, importance)
    md = rapport(df, train, test, res, principal, importance, moran, ids, time.time() - t0, version)
    (K.PREUVES / "rapport_modele.md").write_text(md, encoding="utf-8")
    cx.close()
    print(md)


if __name__ == "__main__":
    main()
