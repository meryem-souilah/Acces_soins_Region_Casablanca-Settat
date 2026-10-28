

CREATE EXTENSION IF NOT EXISTS postgis;

DROP SCHEMA IF EXISTS sante CASCADE;
CREATE SCHEMA sante;
SET search_path = sante, public;

-- ----------------------------------------------------------------------------
-- 1. Tables de référence et tables mères
-- ----------------------------------------------------------------------------

CREATE TABLE province (
    code_province  varchar(10)  PRIMARY KEY,
    nom            varchar(100) NOT NULL,
    type_province  varchar(20)  NOT NULL,          -- 'province' ou 'prefecture'
    geom           geometry(MultiPolygon, 26191) NOT NULL,
    CONSTRAINT province_type_valide CHECK (type_province IN ('province', 'prefecture')),
    CONSTRAINT province_geom_valide CHECK (ST_IsValid(geom))
);


CREATE TABLE niveau_soin (
    code_niveau         smallint    PRIMARY KEY,   
    libelle             varchar(80) NOT NULL,
    seuil_acces_min     smallint,                  
    pop_cible_par_etab  integer,                   
    source_norme        text,                      
    -- Règle de couverture portée par la donnée : false = couverture STRICTE,
    -- un établissement ne couvre que son propre niveau (un CHU ne couvre pas le
    -- niveau 1). Passer à true sert de scénario de comparaison.
    couvre_niveaux_inferieurs  boolean NOT NULL DEFAULT false,
    CONSTRAINT niveau_seuil_positif CHECK (seuil_acces_min IS NULL OR seuil_acces_min > 0),
    CONSTRAINT niveau_pop_cible_positive CHECK (pop_cible_par_etab IS NULL OR pop_cible_par_etab > 0),
    CONSTRAINT niveau_source_requise CHECK (
        (seuil_acces_min IS NULL AND pop_cible_par_etab IS NULL)
        OR source_norme IS NOT NULL
    )
);

-- Rôle : offre. Liste fermée qui traduit les tags OSM disparates.
-- Justification métier (clinique -> niveau 2 par défaut) : une clinique privée dispose
-- d'un plateau technique chirurgical/hospitalisation (avec lits), comparable au second
-- recours (niveau 2), à la différence d'un cabinet médical ou centre de santé (niveau 1).
CREATE TABLE type_etablissement (
    code_type       varchar(20) PRIMARY KEY,       -- 'hopital', 'centre_sante'...
    libelle         varchar(60) NOT NULL,
    tags_osm        text        NOT NULL,          -- règle de correspondance documentée
    inclus_analyse  boolean     NOT NULL DEFAULT true,  -- false : gardé en base, hors calcul
    niveau_defaut   smallint    NOT NULL                -- niveau PROPOSÉ au nettoyage
        REFERENCES niveau_soin (code_niveau) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Rôle : accès. Intersections et extrémités du réseau routier.
CREATE TABLE noeud (
    id_noeud  bigint PRIMARY KEY,                  -- identifiant du nœud du graphe routier
    geom      geometry(Point, 26191) NOT NULL
);

-- ----------------------------------------------------------------------------
-- 2. Tables qui dépendent des précédentes
-- ----------------------------------------------------------------------------

-- Rôle : décision. Unité de la population officielle HCP et des recommandations (153 communes).
CREATE TABLE commune (
    code_hcp       varchar(20)  PRIMARY KEY,
    nom            varchar(150) NOT NULL,
    pop_2024       integer,                        -- NULL tant que non apparié au PDF HCP
    code_province  varchar(10)  NOT NULL
        REFERENCES province (code_province)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    geom           geometry(MultiPolygon, 26191) NOT NULL,
    CONSTRAINT commune_geom_valide CHECK (ST_IsValid(geom)),
    CONSTRAINT commune_pop_positive CHECK (pop_2024 IS NULL OR pop_2024 >= 0)
);

-- Rôle : accès. Un tronçon relie deux nœuds (sens de circulation du graphe).
-- Justification ON DELETE CASCADE : un tronçon est une arête du graphe qui n'a pas
-- d'existence propre sans ses deux nœuds extrémités, contrairement à une commune
-- qui est une entité administrative de référence protégée par ON DELETE RESTRICT.
CREATE TABLE troncon (
    id_troncon     bigserial   PRIMARY KEY,
    type_voie      varchar(30) NOT NULL,           -- tag highway / fclass OSM
    longueur_m     real        NOT NULL,
    vitesse_kmh    smallint,                       -- maxspeed OSM ou vitesse par défaut selon fclass
    sens_unique    boolean     NOT NULL DEFAULT false,
    noeud_depart   bigint      NOT NULL REFERENCES noeud (id_noeud) ON DELETE CASCADE,
    noeud_arrivee  bigint      NOT NULL REFERENCES noeud (id_noeud) ON DELETE CASCADE,
    geom           geometry(LineString, 26191) NOT NULL,
    CONSTRAINT troncon_longueur_positive CHECK (longueur_m > 0),
    CONSTRAINT troncon_vitesse_positive CHECK (vitesse_kmh IS NULL OR vitesse_kmh > 0),
    CONSTRAINT troncon_noeuds_distincts CHECK (noeud_depart <> noeud_arrivee)
);

-- ----------------------------------------------------------------------------
-- 3. Tables « faits » : l'offre (établissements) et la demande (hexagones H3)
-- ----------------------------------------------------------------------------

-- Rôle : offre. Destinations des calculs d'accès.
-- Justification id_noeud nullable vs code_hcp NOT NULL : tout établissement de la région
-- tombe dans une commune dès l'import (ST_Within), alors que l'accrochage au réseau
-- routier (id_noeud) peut être recalculé ou réinitialisé (ON DELETE SET NULL) si le
-- graphe routier est mis à jour, sans perdre l'établissement.
CREATE TABLE etablissement (
    id_etab    serial       PRIMARY KEY,
    osm_id     varchar(30)  NOT NULL UNIQUE,       -- 'node/123', 'way/456' : traçabilité
    nom        varchar(200),
    secteur    varchar(20),                        -- 'public', 'prive', NULL si inconnu
    nb_lits    integer,
    urgences   boolean,
    code_type  varchar(20)  NOT NULL
        REFERENCES type_etablissement (code_type) ON UPDATE CASCADE ON DELETE RESTRICT,
    -- Le niveau est une propriété de l'établissement, pas de son type : un hôpital
    -- provincial et un CHU sont tous deux « hospital » dans OSM.
    code_niveau    smallint    NOT NULL
        REFERENCES niveau_soin (code_niveau) ON UPDATE CASCADE ON DELETE RESTRICT,
    niveau_source  varchar(15) NOT NULL DEFAULT 'defaut_type',
        -- 'defaut_type' = recopié de type_etablissement.niveau_defaut au nettoyage
        -- 'relecture'   = corrigé à la main (traçabilité de la relecture métier)
    code_hcp   varchar(20)  NOT NULL
        REFERENCES commune (code_hcp) ON UPDATE CASCADE ON DELETE RESTRICT,
    id_noeud   bigint
        REFERENCES noeud (id_noeud) ON DELETE SET NULL,
    geom       geometry(Point, 26191) NOT NULL,
    CONSTRAINT etab_niveau_source_valide CHECK (niveau_source IN ('defaut_type', 'relecture')),
    CONSTRAINT etab_secteur_valide CHECK (secteur IS NULL OR secteur IN ('public', 'prive')),
    CONSTRAINT etab_nb_lits_positif CHECK (nb_lits IS NULL OR nb_lits >= 0)
);

-- Rôle : demande. Population WorldPop agrégée par hexagone H3 (résolution 8).
CREATE TABLE maille_h3 (
    h3_index    varchar(15) PRIMARY KEY,
    resolution  smallint    NOT NULL DEFAULT 8,
    population  real        NOT NULL DEFAULT 0,
    code_hcp    varchar(20) NOT NULL
        REFERENCES commune (code_hcp) ON UPDATE CASCADE ON DELETE RESTRICT,
    id_noeud    bigint
        REFERENCES noeud (id_noeud) ON DELETE SET NULL,
    geom        geometry(Polygon, 26191) NOT NULL,
    CONSTRAINT maille_resolution CHECK (resolution BETWEEN 0 AND 15),
    CONSTRAINT maille_population_positive CHECK (population >= 0),
    CONSTRAINT maille_geom_valide CHECK (ST_IsValid(geom))
);

-- ----------------------------------------------------------------------------
-- 4. Index
-- ----------------------------------------------------------------------------

-- Index spatiaux GIST : indispensables à ST_Within, ST_DWithin et à l'opérateur <->
CREATE INDEX province_geom_gist       ON province      USING gist (geom);
CREATE INDEX commune_geom_gist        ON commune       USING gist (geom);
CREATE INDEX noeud_geom_gist          ON noeud         USING gist (geom);
CREATE INDEX troncon_geom_gist        ON troncon       USING gist (geom);
CREATE INDEX etablissement_geom_gist  ON etablissement USING gist (geom);
CREATE INDEX maille_h3_geom_gist      ON maille_h3     USING gist (geom);

-- Index B-tree sur les clés étrangères (PostgreSQL ne les crée pas tout seul)
CREATE INDEX commune_code_province_idx  ON commune            (code_province);
CREATE INDEX etablissement_code_hcp_idx ON etablissement      (code_hcp);
CREATE INDEX etablissement_type_idx     ON etablissement      (code_type);
CREATE INDEX type_niveau_idx            ON type_etablissement (niveau_defaut);
CREATE INDEX etablissement_niveau_idx   ON etablissement      (code_niveau);
CREATE INDEX etablissement_id_noeud_idx ON etablissement      (id_noeud);
CREATE INDEX troncon_depart_idx         ON troncon            (noeud_depart);
CREATE INDEX troncon_arrivee_idx        ON troncon            (noeud_arrivee);
CREATE INDEX maille_h3_code_hcp_idx     ON maille_h3          (code_hcp);
CREATE INDEX maille_h3_id_noeud_idx     ON maille_h3          (id_noeud);

-- ----------------------------------------------------------------------------
-- 5. Données de référence
-- ----------------------------------------------------------------------------

-- Seuils et populations cibles : renseignés à partir des normes OMS / grille de la
-- carte sanitaire (Décret n° 2-14-562 relatif à l'organisation de l'offre de soins)
-- pour les requêtes d'évaluation, tout en restant modifiables par scénario.
INSERT INTO niveau_soin (code_niveau, libelle, seuil_acces_min, pop_cible_par_etab, source_norme, couvre_niveaux_inferieurs) VALUES
    (1, 'Soins de proximité (premier recours)',        15,  25000, 'Scénario carte sanitaire (ESSP / centre de santé, 15 min)', false),
    (2, 'Hôpital de référence (provincial / préfectoral)', 30, 150000, 'Scénario carte sanitaire (CHP / clinique de 2e recours, 30 min)', false),
    (3, 'Hôpital régional ou CHU',                     60, 1000000, 'Scénario carte sanitaire (CHR / CHU de 3e recours, 60 min)', false);


INSERT INTO type_etablissement (code_type, libelle, tags_osm, inclus_analyse, niveau_defaut) VALUES
    ('hopital',      'Hôpital',                                      'amenity=hospital ; healthcare=hospital',      true,  2),
    ('clinique',     'Clinique',                                     'amenity=clinic ; healthcare=clinic',          true,  2),
    ('centre_sante', 'Centre de santé / dispensaire',                'healthcare=centre ; amenity=clinic + nom « centre de santé »', true, 1),
    ('medecin',      'Cabinet médical',                              'amenity=doctors ; healthcare=doctor',         true,  1),
    ('dentiste',     'Cabinet dentaire',                             'amenity=dentist ; healthcare=dentist',        false, 1),
    ('pharmacie',    'Pharmacie',                                    'amenity=pharmacy ; healthcare=pharmacy',      false, 1),
    ('autre',        'Autre structure (laboratoire, kiné, centre…)', 'healthcare=* hors catégories ci-dessus',      false, 1);

-- ----------------------------------------------------------------------------
-- 6. Documentation dans la base (visible dans QGIS et pgAdmin)
-- ----------------------------------------------------------------------------
COMMENT ON TABLE province           IS 'Provinces et préfectures de Casablanca-Settat (9 entités, agrégées depuis les communes OSM/HCP)';
COMMENT ON TABLE commune            IS 'Communes de Casablanca-Settat (153 entités OSM avec code HCP et population légale RGPH 2024)';
COMMENT ON TABLE niveau_soin        IS 'Référentiel des niveaux de soin : paramètres de l''analyse d''accès. Couverture stricte par défaut : un établissement ne couvre que son propre niveau';
COMMENT ON TABLE type_etablissement IS 'Typologie normalisée des établissements de santé traduite des tags OpenStreetMap';
COMMENT ON TABLE etablissement      IS 'Établissements de santé issus d''OpenStreetMap, rattachés à leur commune et au nœud routier le plus proche';
COMMENT ON TABLE maille_h3          IS 'Population WorldPop 2020 agrégée en hexagones H3 résolution 8 (~0,74 km²), rattachée à la commune et au réseau routier';
COMMENT ON TABLE noeud              IS 'Nœuds (intersections et extrémités) du graphe routier régional en EPSG:26191';
COMMENT ON TABLE troncon            IS 'Tronçons orientés du réseau routier régional (OSM Geofabrik) avec longueur et vitesse estimée';
COMMENT ON COLUMN etablissement.niveau_source IS 'defaut_type = niveau du type ; relecture = corrigé à la main';
COMMENT ON COLUMN niveau_soin.seuil_acces_min IS 'Temps d''accès cible en minutes — associé à source_norme';


