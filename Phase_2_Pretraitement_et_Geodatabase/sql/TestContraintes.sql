-- Tests des contraintes du schéma sante

-- Test 1 : un système de coordonnées autre que 26191 est refusé

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'province',
  ST_SetSRID(ST_Multi(ST_MakeEnvelope(300000, 330000, 301000, 331000)), 4326));
ROLLBACK;


-- Test 2 : on ne supprime pas une commune qui a des établissements (ON DELETE RESTRICT)

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'province',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 310000, 340000, 26191)));
INSERT INTO sante.commune (code_hcp, nom, code_province, geom)
VALUES ('C_TEST', 'Commune test', 'P_TEST',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 305000, 335000, 26191)));
INSERT INTO sante.etablissement (osm_id, code_type, code_niveau, code_hcp, geom)
VALUES ('test/1', 'hopital', 2, 'C_TEST', ST_SetSRID(ST_MakePoint(302000, 332000), 26191));
DELETE FROM sante.commune WHERE code_hcp = 'C_TEST';
ROLLBACK;


-- Test 3 : un établissement doit être dans une commune qui existe

BEGIN;
INSERT INTO sante.etablissement (osm_id, code_type, code_niveau, code_hcp, geom)
VALUES ('test/3', 'hopital', 2, 'INEXISTANTE', ST_SetSRID(ST_MakePoint(302000, 332000), 26191));
ROLLBACK;


-- Test 4 : niveau_source n'accepte que 'defaut_type' ou 'relecture'

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'province',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 310000, 340000, 26191)));
INSERT INTO sante.commune (code_hcp, nom, code_province, geom)
VALUES ('C_TEST', 'Commune test', 'P_TEST',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 305000, 335000, 26191)));
INSERT INTO sante.etablissement (osm_id, code_type, code_niveau, niveau_source, code_hcp, geom)
VALUES ('test/4', 'hopital', 2, 'devine', 'C_TEST', ST_SetSRID(ST_MakePoint(302000, 332000), 26191));
ROLLBACK;


-- Test 5 : secteur n'accepte que 'public', 'prive', 'associatif' ou vide

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'province',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 310000, 340000, 26191)));
INSERT INTO sante.commune (code_hcp, nom, code_province, geom)
VALUES ('C_TEST', 'Commune test', 'P_TEST',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 305000, 335000, 26191)));
INSERT INTO sante.etablissement (osm_id, code_type, code_niveau, secteur, code_hcp, geom)
VALUES ('test/5', 'hopital', 2, 'militaire', 'C_TEST', ST_SetSRID(ST_MakePoint(302000, 332000), 26191));
ROLLBACK;


-- Test 6 : une province est soit 'province', soit 'prefecture'

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'region',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 310000, 340000, 26191)));
ROLLBACK;


-- Test 7 : la population d'une commune ne peut pas être négative

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'province',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 310000, 340000, 26191)));
INSERT INTO sante.commune (code_hcp, nom, pop_2024, code_province, geom)
VALUES ('C_TEST', 'Commune test', -10, 'P_TEST',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 305000, 335000, 26191)));
ROLLBACK;


-- Test 8 : un tronçon ne peut pas partir et arriver au même nœud

BEGIN;
INSERT INTO sante.noeud VALUES (1, ST_SetSRID(ST_MakePoint(300000, 330000), 26191));
INSERT INTO sante.troncon (type_voie, longueur_m, vitesse_kmh, noeud_depart, noeud_arrivee, geom)
VALUES ('primary', 100, 80, 1, 1,
  ST_SetSRID(ST_MakeLine(ST_MakePoint(300000, 330000), ST_MakePoint(300100, 330000)), 26191));
ROLLBACK;


-- Test 9 : un tronçon a une longueur strictement positive

BEGIN;
INSERT INTO sante.noeud VALUES (1, ST_SetSRID(ST_MakePoint(300000, 330000), 26191));
INSERT INTO sante.noeud VALUES (2, ST_SetSRID(ST_MakePoint(300100, 330000), 26191));
INSERT INTO sante.troncon (type_voie, longueur_m, vitesse_kmh, noeud_depart, noeud_arrivee, geom)
VALUES ('primary', 0, 80, 1, 2,
  ST_SetSRID(ST_MakeLine(ST_MakePoint(300000, 330000), ST_MakePoint(300100, 330000)), 26191));
ROLLBACK;


-- Test 10 : un seuil d'accès ne peut pas être saisi sans sa source

BEGIN;
UPDATE sante.niveau_soin SET seuil_acces_min = 30 WHERE code_niveau = 1;
ROLLBACK;


-- Test 11 : on ne supprime pas un niveau encore utilisé par des types

BEGIN;
DELETE FROM sante.niveau_soin WHERE code_niveau = 2;
ROLLBACK;


-- Test 12 : un objet OSM n'est importé qu'une fois (osm_id unique)

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'province',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 310000, 340000, 26191)));
INSERT INTO sante.commune (code_hcp, nom, code_province, geom)
VALUES ('C_TEST', 'Commune test', 'P_TEST',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 305000, 335000, 26191)));
INSERT INTO sante.etablissement (osm_id, code_type, code_niveau, code_hcp, geom)
VALUES ('test/12', 'hopital', 2, 'C_TEST', ST_SetSRID(ST_MakePoint(302000, 332000), 26191));
INSERT INTO sante.etablissement (osm_id, code_type, code_niveau, code_hcp, geom)
VALUES ('test/12', 'clinique', 2, 'C_TEST', ST_SetSRID(ST_MakePoint(302500, 332500), 26191));
ROLLBACK;


-- Test 13 (doit être ACCEPTÉ) : corriger un niveau à la relecture

BEGIN;
INSERT INTO sante.province VALUES ('P_TEST', 'Province test', 'province',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 310000, 340000, 26191)));
INSERT INTO sante.commune (code_hcp, nom, code_province, geom)
VALUES ('C_TEST', 'Commune test', 'P_TEST',
  ST_Multi(ST_MakeEnvelope(300000, 330000, 305000, 335000, 26191)));
INSERT INTO sante.etablissement (osm_id, nom, code_type, code_niveau, code_hcp, geom)
VALUES ('test/13', 'CHU test', 'hopital', 2, 'C_TEST', ST_SetSRID(ST_MakePoint(302000, 332000), 26191));
UPDATE sante.etablissement SET code_niveau = 3, niveau_source = 'relecture' WHERE osm_id = 'test/13';
SELECT osm_id, code_niveau, niveau_source FROM sante.etablissement WHERE osm_id = 'test/13';
ROLLBACK;


-- Test 14 (doit être ACCEPTÉ) : un seuil avec sa source

BEGIN;
UPDATE sante.niveau_soin
SET seuil_acces_min = 30, source_norme = 'Scénario de travail (pas de norme officielle)'
WHERE code_niveau = 1;
SELECT code_niveau, seuil_acces_min, source_norme FROM sante.niveau_soin WHERE code_niveau = 1;
ROLLBACK;
