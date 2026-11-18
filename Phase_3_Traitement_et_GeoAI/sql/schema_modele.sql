-- Phase 3, étape 2 — résultats du modèle Geo-AI (EPSG:26191). Recréées par scripts/04_modele.py.
SET search_path = sante, public;

DROP TABLE IF EXISTS prediction_h3, modele_geoai CASCADE;

-- Métadonnées : une ligne par modèle évalué (baselines comprises)
CREATE TABLE modele_geoai (
    id_modele          serial PRIMARY KEY,
    nom                text        NOT NULL,
    role               varchar(10) NOT NULL,          -- baseline / principal
    date_traitement    timestamptz NOT NULL DEFAULT now(),
    algorithme         text        NOT NULL,
    hyperparametres    jsonb,
    features           text[]      NOT NULL,
    cible              text        NOT NULL,
    decoupage          text        NOT NULL,
    n_train            integer     NOT NULL,
    n_test             integer     NOT NULL,
    seuil_decision     real        NOT NULL,
    -- métriques sur le jeu de test (classe positive = hors norme)
    precision_test     real, rappel_test real, f1_test real,
    f1_desservi_test   real,                           -- classe minoritaire
    f1_macro_test      real, exactitude_equilibree_test real,
    roc_auc_test       real, pr_auc_desservi_test real,
    rappel_pondere_pop_test real,                      -- part des HABITANTS hors norme détectés
    matrice_confusion  jsonb,                          -- {"vn":…, "fp":…, "fn":…, "vp":…}
    f1_macro_cv_spatial real, f1_macro_cv_aleatoire real,
    version_donnees    text,                           -- commit git du dépôt
    CONSTRAINT modele_role CHECK (role IN ('baseline', 'principal'))
);
COMMENT ON TABLE modele_geoai IS
    'Modèles de classification des hexagones H3 hors norme d''accès au premier recours (référentiel EPPIG 2016 : '
    '2,3 km / 30 min à pied) ; métriques calculées sur le jeu de test spatial (blocs H3 tenus à l''écart)';

-- Couche dérivée : prédiction par hexagone du modèle principal
CREATE TABLE prediction_h3 (
    h3_index        varchar(15) REFERENCES maille_h3 (h3_index) ON DELETE CASCADE,
    id_modele       integer     REFERENCES modele_geoai (id_modele) ON DELETE CASCADE,
    jeu             varchar(5)  NOT NULL,
    classe_reelle   smallint    NOT NULL,
    classe_predite  smallint    NOT NULL,
    probabilite     real        NOT NULL,
    erreur          varchar(2)  NOT NULL,               -- VP / VN / FP / FN
    geom            geometry(Polygon, 26191) NOT NULL,
    PRIMARY KEY (h3_index, id_modele),
    CONSTRAINT prediction_jeu CHECK (jeu IN ('train', 'test')),
    CONSTRAINT prediction_erreur CHECK (erreur IN ('VP', 'VN', 'FP', 'FN'))
);
CREATE INDEX prediction_h3_geom_gist ON prediction_h3 USING gist (geom);
