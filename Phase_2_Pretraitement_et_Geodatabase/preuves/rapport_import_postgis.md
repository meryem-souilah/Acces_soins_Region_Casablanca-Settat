# Rapport de fusion et d'import PostGIS

Exécuté le 2026-11-18 15:32 UTC par `scripts/import_postgis.py`.

## Fusion des établissements

| Source | Établissements | Origine de la position |
| --- | --- | --- |
| OpenStreetMap (nettoyage.py) | 1571 | osm |
| Ministère de la Santé 2022 (geocodage_essp.py) | 404 | geocodage_lieu 123, manuel 122, approx_commune 93, geocodage_etablissement 66 |
| **Total** (`etablissement_complet`) | **1975** | |

Les centres de santé OSM (`centre_sante`) restent hors analyse (`inclus_analyse = false`) : les soins primaires publics viennent de la liste du Ministère, ce qui évite de compter deux fois le même centre. Seuls les établissements du Ministère **positionnés** sont chargés (la géométrie est obligatoire) ; ceux qui restent à positionner sont listés dans `corrections/a_positionner_essp.csv`.

## Chargement PostGIS

Base `acces_soins`, schéma `sante`, créé par `sql/Schema.sql`. Chargement par `COPY`, puis `id_noeud` = nœud routier le plus proche (index GiST, opérateur `<->`) pour les établissements et pour le centre de chaque hexagone.

| Table | Lignes attendues | Lignes en base | SRID | Géométries invalides |
| --- | --- | --- | --- | --- |
| province | 9 | 9 | 26191 | 0 |
| commune | 153 | 153 | 26191 | 0 |
| noeud | 228054 | 228054 | 26191 | 0 |
| troncon | 316012 | 316012 | 26191 | 0 |
| etablissement | 1975 | 1975 | 26191 | 0 |
| maille_h3 | 25432 | 25432 | 26191 | 0 |

| Contrôle | Valeur |
| --- | --- |
| Communes sans population | 0 |
| Population des communes (RGPH 2024) | 7 688 967 |
| Population des hexagones (WorldPop 2020) | 7 461 204 |
| Établissements sans nœud routier | 0 |
| Hexagones sans nœud routier | 0 |
| Distance médiane établissement → nœud (m) | 24 |
| Distance max établissement → nœud (m) | 2744 |
| Établissements hors de leur commune (> 500 m) | 0 |

**Établissements par source et niveau**

| Source | Niveau | Inclus dans l'analyse | Nombre |
| --- | --- | --- | --- |
| msps | 1 | non | 31 |
| msps | 1 | oui | 373 |
| osm | 1 | non | 1435 |
| osm | 2 | oui | 136 |

## Tests de contraintes (`sql/TestContraintes.sql`)

19 / 19 tests conformes au résultat attendu.

| # | Test | Attendu | Obtenu | Message de PostgreSQL |
| --- | --- | --- | --- | --- |
| 1 | une géométrie doit être en EPSG:26191 (SRID 4326 refusé) | refusé | ✅ refusé | ERREUR:  Geometry SRID (4326) does not match column SRID (26191) |
| 2 | on ne supprime pas une commune qui a des établissements (ON DELETE RESTRICT) | refusé | ✅ refusé | ERREUR:  UPDATE ou DELETE sur la table « commune » viole la contrainte de clé étrangère « etablissement_code_h |
| 3 | un établissement doit être dans une commune qui existe | refusé | ✅ refusé | ERREUR:  une instruction insert ou update sur la table « etablissement » viole la contrainte de clé |
| 4 | niveau_source n'accepte que 'defaut_type' ou 'relecture' | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « etablissement » viole la contrainte de vérification « etab_niveau_ |
| 5 | secteur n'accepte que 'public', 'prive', 'associatif' ou vide | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « etablissement » viole la contrainte de vérification « etab_secteur |
| 6 | une province est soit 'province', soit 'prefecture' | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « province » viole la contrainte de vérification « province_type » |
| 7 | la population d'une commune ne peut pas être négative | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « commune » viole la contrainte de vérification « commune_pop_positi |
| 8 | un tronçon ne peut pas partir et arriver au même nœud | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « troncon » viole la contrainte de vérification « troncon_pas_de_bou |
| 9 | un tronçon a une longueur strictement positive | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « troncon » viole la contrainte de vérification « troncon_longueur_p |
| 10 | un seuil d'accès ne peut pas être saisi sans sa source | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « niveau_soin » viole la contrainte de vérification « niveau_seuil_s |
| 11 | on ne supprime pas un niveau encore utilisé par des types | refusé | ✅ refusé | ERREUR:  UPDATE ou DELETE sur la table « niveau_soin » viole la contrainte de clé étrangère « type_etablisseme |
| 12 | un établissement de la source n'est importé qu'une fois (id_source unique) | refusé | ✅ refusé | ERREUR:  la valeur d'une clé dupliquée rompt la contrainte unique « etablissement_id_source_key » |
| 13 | corriger un niveau à la relecture | accepté | ✅ accepté |  |
| 14 | un seuil avec sa source | accepté | ✅ accepté |  |
| 15 | la source n'accepte que 'msps' ou 'osm' | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « etablissement » viole la contrainte de vérification « etab_source  |
| 16 | precision_geom n'accepte que les valeurs prévues | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « etablissement » viole la contrainte de vérification « etab_precisi |
| 17 | une ligne du Ministère ne peut pas avoir une position « osm » | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « etablissement » viole la contrainte de vérification « etab_precisi |
| 18 | le milieu d'un type est 'urbain' ou 'rural' | refusé | ✅ refusé | ERREUR:  la nouvelle ligne de la relation « type_etablissement » viole la contrainte de vérification « type_mi |
| 19 | un établissement OSM avec une position « osm » | accepté | ✅ accepté |  |

## Sauvegarde

`donnees_propres/acces_soins.backup` (49 Mo, format custom). Restauration : `pg_restore -d acces_soins --clean --if-exists acces_soins.backup`.
