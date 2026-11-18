-- Phase 3 — tables dérivées du schéma « sante » (EPSG:26191).
-- Recréées par scripts/01_accessibilite.py ; les tables de la Phase 2 ne sont pas
-- modifiées, sauf les paramètres de niveau_soin renseignés depuis le référentiel.
--
-- Source des règles métier : « Référentiel de programmation des équipements publics et
-- privés d'intérêt général » (2016), chapitre 2 « Les équipements de santé », p. 39-41
-- et récapitulatif p. 79 (references/referentiel_EPPIG_2016_sante_uniquement.pdf).
SET search_path = sante, public;

DROP VIEW  IF EXISTS v_capacite_province, v_capacite_commune, v_couverture_h3, v_maille_pop CASCADE;
DROP TABLE IF EXISTS aptitude_h3, contrainte_localisation, temps_acces, zone_tampon,
                     scenario_acces, norme_referentiel CASCADE;


-- 1. Les normes du référentiel, telles qu'écrites (une ligne par équipement)
CREATE TABLE norme_referentiel (
    code_norme        varchar(10) PRIMARY KEY,
    equipement        text        NOT NULL,
    code_niveau       smallint    REFERENCES niveau_soin (code_niveau),
    pop_seuil_min     integer,                 -- « seuil minimum » d'habitants
    echelle_desserte  text,                    -- commune / province / région
    acces_distance_m  integer,                 -- accessibilité : distance
    acces_temps_min   smallint,                -- accessibilité : temps
    regle_localisation text,
    page              text        NOT NULL,
    source            text        NOT NULL
);
COMMENT ON TABLE norme_referentiel IS
    'Normes de programmation des équipements de santé, reprises du référentiel EPPIG 2016 sans interprétation';


-- 2. Scénarios d'accès : normatif (sourcé) ou hypothèse (aucune norme de temps)
CREATE TABLE scenario_acces (
    code_scenario     varchar(20) PRIMARY KEY,
    code_niveau       smallint    NOT NULL REFERENCES niveau_soin (code_niveau),
    mode              varchar(10) NOT NULL,
    seuil_min         smallint    NOT NULL,
    vitesse_kmh       real        NOT NULL,
    rayon_tampon_m    integer     NOT NULL,
    normatif          boolean     NOT NULL,
    code_norme        varchar(10) REFERENCES norme_referentiel (code_norme),
    justification     text        NOT NULL,
    CONSTRAINT scenario_mode CHECK (mode IN ('marche', 'voiture')),
    CONSTRAINT scenario_normatif_source CHECK (NOT normatif OR code_norme IS NOT NULL)
);
COMMENT ON TABLE scenario_acces IS
    'normatif = règle du référentiel (niveau 1 : 2,3 km / 30 min à pied) ; sinon hypothèse de travail '
    '(niveaux 2 et 3 : le référentiel ne fixe aucun temps d''accès)';


-- 3. Géotraitement vectoriel : tampons fusionnés par scénario, découpés sur la région
CREATE TABLE zone_tampon (
    code_scenario  varchar(20) PRIMARY KEY REFERENCES scenario_acces (code_scenario),
    nb_etab        integer NOT NULL,
    surface_km2    real    NOT NULL,
    geom           geometry(MultiPolygon, 26191) NOT NULL
);
CREATE INDEX zone_tampon_geom_gist ON zone_tampon USING gist (geom);


-- 4. Analyse réseau : temps vers l'établissement le plus proche, par niveau et par mode
CREATE TABLE temps_acces (
    h3_index     varchar(15) REFERENCES maille_h3 (h3_index) ON DELETE CASCADE,
    code_niveau  smallint    REFERENCES niveau_soin (code_niveau),
    mode         varchar(10),
    temps_min    real        NOT NULL,
    id_etab      integer     NOT NULL REFERENCES etablissement (id_etab) ON DELETE CASCADE,
    PRIMARY KEY (h3_index, code_niveau, mode),
    CONSTRAINT temps_positif CHECK (temps_min >= 0),
    CONSTRAINT temps_mode CHECK (mode IN ('marche', 'voiture'))
);
CREATE INDEX temps_acces_etab_idx ON temps_acces (id_etab);


-- 5. Critères de localisation : zones à éviter (nuisances) et proximité des grands axes
CREATE TABLE contrainte_localisation (
    categorie     varchar(30) PRIMARY KEY,
    equipements   text        NOT NULL,          -- à qui s'applique la règle
    effet         varchar(10) NOT NULL,          -- exclure / favoriser
    distance_m    integer     NOT NULL,
    nb_objets     integer     NOT NULL,
    source_osm    text        NOT NULL,
    regle         text        NOT NULL,
    geom          geometry(MultiPolygon, 26191) NOT NULL,
    CONSTRAINT contrainte_effet CHECK (effet IN ('exclure', 'favoriser'))
);
CREATE INDEX contrainte_localisation_gist ON contrainte_localisation USING gist (geom);

CREATE TABLE aptitude_h3 (
    h3_index        varchar(15) PRIMARY KEY REFERENCES maille_h3 (h3_index) ON DELETE CASCADE,
    nuisance_pct    real    NOT NULL,   -- part de l'hexagone dans une zone de nuisance
    pres_grand_axe  boolean NOT NULL,
    apte_csu        boolean NOT NULL,
    apte_hopital    boolean NOT NULL
);


-- 6. Population 2024 par hexagone : WorldPop (répartition) recalé sur le RGPH 2024 (total communal)
CREATE VIEW v_maille_pop AS
SELECT m.h3_index, m.code_hcp, m.geom, m.population AS pop_worldpop,
       CASE WHEN s.pop_wp > 0 THEN m.population * c.pop_2024 / s.pop_wp ELSE 0 END AS pop_2024
FROM maille_h3 m
JOIN commune c USING (code_hcp)
JOIN (SELECT code_hcp, sum(population) AS pop_wp FROM maille_h3 GROUP BY code_hcp) s USING (code_hcp);


-- 7. Couverture par hexagone et scénario : à vol d'oiseau (tampon) et par le réseau
CREATE VIEW v_couverture_h3 AS
SELECT p.h3_index, p.code_hcp, c.code_province, s.code_scenario, s.code_niveau, s.mode,
       s.seuil_min, s.normatif, p.pop_2024, t.temps_min,
       (t.temps_min <= s.seuil_min) AS couvert_reseau,
       EXISTS (SELECT 1 FROM zone_tampon z
               WHERE z.code_scenario = s.code_scenario
                 AND ST_Intersects(z.geom, ST_Centroid(p.geom))) AS couvert_tampon,
       p.geom
FROM v_maille_pop p
JOIN commune c USING (code_hcp)
JOIN scenario_acces s ON true
JOIN temps_acces t ON t.h3_index = p.h3_index AND t.code_niveau = s.code_niveau AND t.mode = s.mode;


-- 8. Règles de capacité du référentiel
-- Niveau 1 : un CSU pour 25 000 habitants au moins (CSU-1), dans les communes urbaines.
-- Le code HCP d'une commune urbaine (municipalité, arrondissements) a « 01 » en 3e partie.
CREATE VIEW v_capacite_commune AS
SELECT c.code_hcp, c.nom, c.code_province,
       (split_part(c.code_hcp, '.', 3) = '01') AS urbaine,
       c.pop_2024,
       count(e.id_etab) FILTER (WHERE e.code_niveau = 1 AND t.inclus_analyse) AS nb_niveau1,
       ceil(c.pop_2024 / 25000.0)::int AS nb_requis_csu,
       c.pop_2024 / NULLIF(count(e.id_etab) FILTER (WHERE e.code_niveau = 1 AND t.inclus_analyse), 0)
           AS hab_par_centre
FROM commune c
LEFT JOIN etablissement e USING (code_hcp)
LEFT JOIN type_etablissement t USING (code_type)
GROUP BY c.code_hcp, c.nom, c.code_province, c.pop_2024;

-- Niveau 2 : hôpital provincial dès 200 000 habitants, hôpital de proximité dès 70 000.
-- On compte les hôpitaux (type « hopital ») de niveau 2, publics ou non : OSM ne distingue
-- pas toujours le statut ; les cliniques sont comptées à part.
CREATE VIEW v_capacite_province AS
SELECT p.code_province, p.nom, sum(c.pop_2024) AS pop_2024,
       (sum(c.pop_2024) >= 200000) AS justifie_chp,
       (sum(c.pop_2024) >= 70000)  AS justifie_hopital_proximite,
       (SELECT count(*) FROM etablissement e JOIN commune c2 USING (code_hcp)
        WHERE c2.code_province = p.code_province AND e.code_type = 'hopital' AND e.code_niveau = 2) AS nb_hopitaux,
       (SELECT count(*) FROM etablissement e JOIN commune c2 USING (code_hcp)
        WHERE c2.code_province = p.code_province AND e.code_type = 'clinique') AS nb_cliniques,
       (SELECT count(*) FROM etablissement e JOIN commune c2 USING (code_hcp)
        WHERE c2.code_province = p.code_province AND e.code_niveau = 3) AS nb_niveau3
FROM province p JOIN commune c USING (code_province)
GROUP BY p.code_province, p.nom;
