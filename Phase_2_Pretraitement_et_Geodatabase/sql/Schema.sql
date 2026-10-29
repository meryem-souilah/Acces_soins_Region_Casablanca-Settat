-- Géodatabase du projet : accès aux soins dans la région Casablanca-Settat
-- PostgreSQL 16 + PostGIS. Toutes les géométries sont en EPSG:26191 (Merchich / Nord Maroc).
--


CREATE EXTENSION IF NOT EXISTS postgis;
DROP SCHEMA IF EXISTS sante CASCADE;
CREATE SCHEMA sante;
SET search_path = sante, public;


-- 1. Référentiels et tables sans dépendance
-- On les crée en premier parce que les autres tables pointent vers elles.

CREATE TABLE province (
    code_province  varchar(10)  PRIMARY KEY,
    nom            varchar(100) NOT NULL,
    type_province  varchar(20)  NOT NULL,
    geom           geometry(MultiPolygon, 26191) NOT NULL,
    CONSTRAINT province_type CHECK (type_province IN ('province', 'prefecture')),
    CONSTRAINT province_geom_valide CHECK (ST_IsValid(geom))
);

-- Les seuils restent vides tant qu'on n'a pas de norme officielle à citer.
-- En attendant, on travaille par scénarios (15, 30, 45 min).
CREATE TABLE niveau_soin (
    code_niveau                smallint    PRIMARY KEY,
    libelle                    varchar(80) NOT NULL,
    seuil_acces_min            smallint,
    pop_cible_par_etab         integer,
    source_norme               text,
    couvre_niveaux_inferieurs  boolean     NOT NULL DEFAULT false,
    CONSTRAINT niveau_seuil_positif CHECK (seuil_acces_min IS NULL OR seuil_acces_min > 0),
    CONSTRAINT niveau_pop_positive  CHECK (pop_cible_par_etab IS NULL OR pop_cible_par_etab > 0),
    -- un chiffre sans source ne doit pas entrer dans la base
    CONSTRAINT niveau_seuil_source  CHECK (
        (seuil_acces_min IS NULL AND pop_cible_par_etab IS NULL) OR source_norme IS NOT NULL)
);

-- niveau_defaut est le niveau attribué au nettoyage. Il peut ensuite être
-- corrigé établissement par établissement (voir etablissement.niveau_source).
CREATE TABLE type_etablissement (
    code_type       varchar(20) PRIMARY KEY,
    libelle         varchar(60) NOT NULL,
    tags_osm        text        NOT NULL,
    inclus_analyse  boolean     NOT NULL DEFAULT true,
    niveau_defaut   smallint    NOT NULL
        REFERENCES niveau_soin (code_niveau) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- id_noeud reprend l'identifiant OSM du nœud, d'où bigint et pas serial.
CREATE TABLE noeud (
    id_noeud  bigint PRIMARY KEY,
    geom      geometry(Point, 26191) NOT NULL
);


-- 2. Tables qui dépendent des précédentes

-- pop_2024 est vide tant que les tableaux HCP ne sont pas rapprochés des communes.
CREATE TABLE commune (
    code_hcp       varchar(20)  PRIMARY KEY,
    nom            varchar(150) NOT NULL,
    pop_2024       integer,
    code_province  varchar(10)  NOT NULL
        REFERENCES province (code_province) ON UPDATE CASCADE ON DELETE RESTRICT,
    geom           geometry(MultiPolygon, 26191) NOT NULL,
    CONSTRAINT commune_pop_positive CHECK (pop_2024 IS NULL OR pop_2024 >= 0),
    CONSTRAINT commune_geom_valide  CHECK (ST_IsValid(geom))
);

-- Si on recharge le réseau, les tronçons partent avec leurs nœuds (CASCADE) :
-- un tronçon sans extrémité n'a aucun sens.
-- vitesse_kmh est toujours remplie : vitesse OSM, sinon vitesse par défaut du type de voie.
CREATE TABLE troncon (
    id_troncon     bigserial   PRIMARY KEY,
    type_voie      varchar(30) NOT NULL,
    longueur_m     real        NOT NULL,
    vitesse_kmh    smallint    NOT NULL,
    sens_unique    boolean     NOT NULL DEFAULT false,
    noeud_depart   bigint      NOT NULL REFERENCES noeud (id_noeud) ON DELETE CASCADE,
    noeud_arrivee  bigint      NOT NULL REFERENCES noeud (id_noeud) ON DELETE CASCADE,
    geom           geometry(LineString, 26191) NOT NULL,
    CONSTRAINT troncon_longueur_positive CHECK (longueur_m > 0),
    CONSTRAINT troncon_vitesse_positive  CHECK (vitesse_kmh > 0),
    CONSTRAINT troncon_pas_de_boucle     CHECK (noeud_depart <> noeud_arrivee)
);


-- 3. L'offre (établissements) et la demande (hexagones H3)

-- id_noeud est vide juste après l'import : le nœud le plus proche est calculé
-- ensuite dans PostGIS. Si le nœud disparaît, on garde l'établissement (SET NULL).
CREATE TABLE etablissement (
    id_etab        serial       PRIMARY KEY,
    osm_id         varchar(30)  NOT NULL UNIQUE,
    nom            varchar(200),
    secteur        varchar(20),
    nb_lits        integer,
    urgences       boolean,
    code_type      varchar(20)  NOT NULL
        REFERENCES type_etablissement (code_type) ON UPDATE CASCADE ON DELETE RESTRICT,
    code_niveau    smallint     NOT NULL
        REFERENCES niveau_soin (code_niveau) ON UPDATE CASCADE ON DELETE RESTRICT,
    niveau_source  varchar(15)  NOT NULL DEFAULT 'defaut_type',
    code_hcp       varchar(20)  NOT NULL
        REFERENCES commune (code_hcp) ON UPDATE CASCADE ON DELETE RESTRICT,
    id_noeud       bigint
        REFERENCES noeud (id_noeud) ON DELETE SET NULL,
    geom           geometry(Point, 26191) NOT NULL,
    CONSTRAINT etab_niveau_source CHECK (niveau_source IN ('defaut_type', 'relecture')),
    CONSTRAINT etab_secteur       CHECK (secteur IS NULL OR secteur IN ('public', 'prive', 'associatif')),
    CONSTRAINT etab_lits_positifs CHECK (nb_lits IS NULL OR nb_lits >= 0)
);

-- Chaque hexagone appartient à la commune qui contient son centre.
-- id_noeud est vide à l'import, pour la même raison que dans etablissement.
CREATE TABLE maille_h3 (
    h3_index    varchar(15) PRIMARY KEY,
    resolution  smallint    NOT NULL DEFAULT 8,
    population  real        NOT NULL DEFAULT 0,
    code_hcp    varchar(20) NOT NULL
        REFERENCES commune (code_hcp) ON UPDATE CASCADE ON DELETE RESTRICT,
    id_noeud    bigint
        REFERENCES noeud (id_noeud) ON DELETE SET NULL,
    geom        geometry(Polygon, 26191) NOT NULL,
    CONSTRAINT maille_resolution       CHECK (resolution BETWEEN 0 AND 15),
    CONSTRAINT maille_pop_positive     CHECK (population >= 0),
    CONSTRAINT maille_geom_valide      CHECK (ST_IsValid(geom))
);


-- 4. Index
-- GIST sur chaque géométrie pour les requêtes spatiales (ST_Within, plus proche voisin <->).
-- B-tree sur chaque clé étrangère : PostgreSQL ne les crée pas tout seul.

CREATE INDEX province_geom_gist       ON province      USING gist (geom);
CREATE INDEX commune_geom_gist        ON commune       USING gist (geom);
CREATE INDEX noeud_geom_gist          ON noeud         USING gist (geom);
CREATE INDEX troncon_geom_gist        ON troncon       USING gist (geom);
CREATE INDEX etablissement_geom_gist  ON etablissement USING gist (geom);
CREATE INDEX maille_h3_geom_gist      ON maille_h3     USING gist (geom);

CREATE INDEX commune_province_idx     ON commune            (code_province);
CREATE INDEX type_niveau_idx          ON type_etablissement (niveau_defaut);
CREATE INDEX troncon_depart_idx       ON troncon            (noeud_depart);
CREATE INDEX troncon_arrivee_idx      ON troncon            (noeud_arrivee);
CREATE INDEX etablissement_type_idx   ON etablissement      (code_type);
CREATE INDEX etablissement_niveau_idx ON etablissement      (code_niveau);
CREATE INDEX etablissement_hcp_idx    ON etablissement      (code_hcp);
CREATE INDEX etablissement_noeud_idx  ON etablissement      (id_noeud);
CREATE INDEX maille_h3_hcp_idx        ON maille_h3          (code_hcp);
CREATE INDEX maille_h3_noeud_idx      ON maille_h3          (id_noeud);


-- 5. Données de référence

INSERT INTO niveau_soin (code_niveau, libelle) VALUES
    (1, 'Soins de proximité (premier recours)'),
    (2, 'Hôpital de référence (provincial / préfectoral)'),
    (3, 'Hôpital régional ou CHU');

-- Pharmacies, dentistes et « autre » restent dans la base mais pas dans le calcul.
INSERT INTO type_etablissement (code_type, libelle, tags_osm, inclus_analyse, niveau_defaut) VALUES
    ('hopital',      'Hôpital',                       'amenity=hospital ; healthcare=hospital',      true,  2),
    ('clinique',     'Clinique',                      'amenity=clinic ; healthcare=clinic',          true,  2),
    ('centre_sante', 'Centre de santé / dispensaire', 'healthcare=centre ; amenity=clinic + nom « centre de santé »', true, 1),
    ('medecin',      'Cabinet médical',               'amenity=doctors ; healthcare=doctor',         true,  1),
    ('dentiste',     'Cabinet dentaire',              'amenity=dentist ; healthcare=dentist',        false, 1),
    ('pharmacie',    'Pharmacie',                     'amenity=pharmacy ; healthcare=pharmacy',      false, 1),
    ('autre',        'Autre / non classé',            'tout autre tag healthcare (laboratoire, kiné…)', false, 1);


-- 6. Commentaires stockés dans la base (pgAdmin et QGIS les affichent)

COMMENT ON TABLE province            IS 'Provinces et préfectures de la région, reconstituées à partir des communes HCP';
COMMENT ON TABLE commune             IS 'Communes HCP (COD-AB, HDX) de la région Casablanca-Settat';
COMMENT ON TABLE niveau_soin         IS 'Niveaux de soin et paramètres de l''analyse. Couverture stricte : un établissement ne couvre que son niveau';
COMMENT ON TABLE type_etablissement  IS 'Types d''établissement issus des tags OSM, avec le niveau proposé par défaut';
COMMENT ON TABLE etablissement       IS 'Établissements de santé OpenStreetMap après nettoyage';
COMMENT ON TABLE maille_h3           IS 'Hexagones H3 de résolution 8 avec la population WorldPop 2020';
COMMENT ON TABLE noeud               IS 'Nœuds du réseau routier OSM';
COMMENT ON TABLE troncon             IS 'Tronçons du réseau routier OSM entre deux nœuds';

COMMENT ON COLUMN niveau_soin.seuil_acces_min            IS 'Temps d''accès cible en minutes. Vide tant qu''aucune norme n''est sourcée';
COMMENT ON COLUMN niveau_soin.couvre_niveaux_inferieurs  IS 'false : un CHU ne compte pas comme soin de proximité';
COMMENT ON COLUMN type_etablissement.inclus_analyse      IS 'false : gardé en base mais exclu du calcul d''accès';
COMMENT ON COLUMN etablissement.niveau_source            IS 'defaut_type : niveau du type. relecture : corrigé à la main';
COMMENT ON COLUMN etablissement.id_noeud                 IS 'Nœud routier le plus proche, calculé après l''import';
COMMENT ON COLUMN maille_h3.id_noeud                     IS 'Nœud routier le plus proche du centre de l''hexagone, calculé après l''import';
COMMENT ON COLUMN troncon.vitesse_kmh                    IS 'maxspeed OSM, sinon vitesse par défaut selon le type de voie';