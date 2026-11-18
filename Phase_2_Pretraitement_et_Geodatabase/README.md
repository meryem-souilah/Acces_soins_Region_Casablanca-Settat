# Phase 2 — Pré-traitement et géodatabase PostGIS

Projet **Géodata appliquée** · Accès aux soins, région Casablanca-Settat · CRS unique **EPSG:26191**.

Cette phase transforme les données brutes de la Phase 1 en une géodatabase propre,
conforme au modèle conceptuel ([`modelisation_mcd_mld/MCD_MLD.drawio`](modelisation_mcd_mld/MCD_MLD.drawio))
et chargée dans PostGIS ([`sql/Schema.sql`](sql/Schema.sql)).

## Chaîne de traitement

Les commandes se lancent depuis ce dossier, dans l'environnement `geodata-sante` (`conda activate geodata-sante`).

| # | Commande | Rôle | Sorties |
| --- | --- | --- | --- |
| 1 | `python scripts/nettoyage.py` | Communes et provinces (avec la population RGPH 2024), établissements OSM (type, niveau, doublons, commune), graphe routier (découpe, vitesses, connexité), grille H3 et population WorldPop | `donnees_propres/base_sante.gpkg`, [`preuves/rapport_nettoyage.md`](preuves/rapport_nettoyage.md), [`preuves/journal_nettoyage.csv`](preuves/journal_nettoyage.csv), `corrections/a_relire_hopitaux.csv` |
| 2 | `python scripts/geocodage_essp.py` | Rattachement des centres du Ministère de la Santé (liste 2022) aux communes et géocodage Nominatim (cache) ; une position n'est acceptée que dans la bonne commune | `donnees_propres/essp_geocode.gpkg`, [`preuves/rapport_geocodage.md`](preuves/rapport_geocodage.md), `corrections/a_positionner_essp.csv` |
| 3 | `python scripts/import_postgis.py` | Fusion OSM + Ministère dans une table `etablissement` unique, création du schéma `sante`, chargement par `COPY`, nœud routier le plus proche, contrôles et tests de contraintes | couche `etablissement_complet` du GeoPackage, base PostGIS, [`preuves/rapport_import_postgis.md`](preuves/rapport_import_postgis.md) |

Ajouter `--dry-run` à l'étape 1 pour une simulation (rapport sans écriture). L'étape 3 sans base
PostgreSQL : `--gpkg-seulement`. Avec base : définir `PGPASSWORD` (jamais en argument), puis
`python scripts/import_postgis.py --base acces_soins --user postgres --sauvegarde`.

## Corrections manuelles (dossier `corrections/`)

| Fichier | À faire | Pris en compte par |
| --- | --- | --- |
| `a_positionner_essp.csv` | Centres du Ministère sans position : remplir `lat`, `lon` (WGS84) et `justification`. Le fichier peut être copié en `positions_essp_<nom>.csv`, un par membre du groupe. | `geocodage_essp.py` (fichiers `positions_essp*.csv`) |
| `positions_rejetees_essp.csv` | Généré : positions saisies refusées car à plus de 500 m de la commune déclarée, avec la commune où tombe réellement le point. Corriger `lat`/`lon` dans le fichier du lot indiqué. | — (relancer `geocodage_essp.py`) |
| `a_relire_hopitaux.csv` | Hôpitaux et cliniques OSM : confirmer le niveau (2 ou 3). Reporter les décisions dans `niveaux_relecture.csv` (`osm_id;code_niveau;justification`). | `nettoyage.py` |
| `communes_essp.csv` | Communes du fichier du Ministère dont le nom ne correspond à aucune commune HCP | `geocodage_essp.py` |

Après une correction, relancer les étapes concernées puis l'étape 3.

## Choix de modélisation

- **Population** : légale RGPH 2024 par commune (`commune.pop_2024`, jointure par code HCP, total = 7 688 967) ; maillée WorldPop 2020 par hexagone H3 de résolution 8 (`maille_h3.population`), pour répartir la demande à l'intérieur des communes.
- **Établissements** : une seule table. `source` = `osm` ou `msps`, `precision_geom` = origine de la position. Les types du Ministère (CSU, CSR, DR) portent les soins primaires publics. Les centres de santé, cabinets et pharmacies OSM sont gardés en base mais exclus du calcul (`type_etablissement.inclus_analyse = false`), ce qui évite de compter deux fois le même centre.
- **Réseau** : graphe orienté (`sens_unique`), une seule composante connexe ; vitesse OSM `maxspeed`, sinon une vitesse par défaut selon le type de voie (94 % des tronçons, une limite à rappeler dans l'analyse).

## État et limites connues

- Les 404 centres du Ministère sont tous positionnés, avec l'origine de chaque position (`precision_geom`) :
  - 66 : l'établissement lui-même, trouvé par Nominatim ;
  - 123 : son douar ou son quartier (Nominatim, ou rapprochement des noms avec les lieux OSM, abréviations « Od », « S. », « My » développées) ;
  - 122 : saisis à la main et vérifiés dans la commune ;
  - **93 : approximatifs** (`approx_commune`), placés au centre de la population de leur commune (hexagones H3 pondérés par WorldPop). L'erreur peut atteindre quelques kilomètres dans les grandes communes rurales. En Phase 3, tester l'accessibilité avec et sans ces positions.
- Les centres sans position précise sont listés dans `corrections/a_positionner_essp.csv`. Une saisie manuelle valide remplace la position approchée au prochain lancement de `geocodage_essp.py`.
- Niveau des hôpitaux et cliniques : niveau 2 par défaut tant que la relecture n'est pas faite.
- Attributs OSM `nb_lits`, `secteur` et `urgences` presque vides : pas utilisés dans l'analyse.
