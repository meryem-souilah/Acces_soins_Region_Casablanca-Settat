# Phase 2 — Pré-traitement, nettoyage topologique et géodatabase PostGIS (Séance 4)

## 📂 Fichiers et preuves de ce dossier

| Fichier | Description |
|---|---|
| [README_PRETRAITEMENT.md](README_PRETRAITEMENT.md) | Documentation complète de la phase de pré-traitement et PostGIS (reproduite ci-dessous) |
| [presentation/seance4_pretraitement.pdf](presentation/seance4_pretraitement.pdf) | Support de présentation de la Séance 4 (12 diapositives 16:9, PDF + source [.tex](presentation/seance4_pretraitement.tex)) |
| [modelisation_mcd_mld/modele_acces_soins.drawio](modelisation_mcd_mld/modele_acces_soins.drawio) | Modèle MCD / MLD complet éditable dans draw.io + [Avancement_projet_MCD_MLD.pdf](modelisation_mcd_mld/Avancement_projet_MCD_MLD.pdf) |
| [sql/schema.sql](sql/schema.sql) | DDL complet du schéma PostGIS sante (8 tables, 10 FK, contraintes CHECK, 6 index GIST, 9 index B-tree) |
| [sql/requetes.sql](sql/requetes.sql) | 3 requêtes spatiales métier commentées avec EXPLAIN (ANALYZE, BUFFERS) |
| [../sql/acces_soins.backup](../sql/acces_soins.backup) | Dump PostGIS complet restaurable (pg_dump -Fc, 42,13 Mo, testé avec pg_restore) |
| [scripts/nettoyage.py](scripts/nettoyage.py) | Script de nettoyage v2 avec mode --dry-run, déduplication OSM, graphe routier topologique et H3 rés. 8 |
| [scripts/import_postgis.py](scripts/import_postgis.py) | Script d'import ogr2ogr → staging → sante, tests de rejet par contraintes, exécution de 
equetes.sql et pg_dump |
| [preuves/rapport_nettoyage.md](preuves/rapport_nettoyage.md) | Rapport quantitatif avant / après nettoyage |
| [preuves/carte_nettoyage.png](preuves/carte_nettoyage.png) | Planche visuelle comparative avant / après nettoyage |
| [preuves/resultats_requetes_seance4.md](preuves/resultats_requetes_seance4.md) | Sorties des 3 requêtes métier, plans EXPLAIN ANALYZE et preuves de rejet d'insertions invalides |
| [../donnees_traitees/sante_nettoyee_couches_legeres.gpkg](../donnees_traitees/sante_nettoyee_couches_legeres.gpkg) | GeoPackage nettoyé en EPSG:26191 (province, commune, etablissement, maille_h3) |

---

# Phase de pré-traitement et géodatabase PostGIS — README

Projet **Géodata appliquée** · Accès aux soins, région Casablanca-Settat
Défi : *où implanter quel type d'offre de soins pour maximiser la population couverte
dans le temps d'accès adapté à chaque niveau ?*

Ce document décrit tout ce qui a été mis en place pour la **Phase 2 (Séance 4 — Pré-traitement et géodatabase PostGIS)** : la modélisation conceptuelle et logique des données (MCD / MLD), le schéma SQL PostGIS (`sql/schema.sql`), le script de nettoyage géométrique et topologique (`scripts/nettoyage.py` avec mode `--dry-run`), le chargement automatisé dans PostgreSQL/PostGIS (`scripts/import_postgis.py`), les 3 requêtes spatiales métier commentées avec `EXPLAIN (ANALYZE, BUFFERS)` (`sql/requetes.sql`) et la sauvegarde restaurable (`sql/acces_soins.backup`).

---

## 1. Principe

En sortie de la collecte (Phase 1), les cinq sources sont déjà reprojetées en **`EPSG:26191` (Merchich / Nord Maroc)** et découpées sur le contour régional. Toutefois, les données brutes d'OpenStreetMap, de WorldPop et du HCP ne sont pas directement exploitables pour un calcul de temps d'accès routier ni pour une analyse par niveau de soin :

1. **Modélisation et intégrité (MCD / MLD → PostGIS)** : les relations entre découpage administratif (`province`, `commune`), offre de soins (`etablissement`, `type_etablissement`), graphe routier (`noeud`, `troncon`, `classe_route`) et unité d'analyse de la demande (`maille_h3`) doivent être formalisées et protégées par des clés primaires, clés étrangères, contraintes `CHECK` et contraintes géométriques `geometry(Type, 26191)`.
2. **Nettoyage géométrique et topologique (`nettoyage.py`)** :
   - correction des géométries invalides (`ST_MakeValid` / `shapely.make_valid`) et fermeture des micro-trous issus de l'union des communes ;
   - **fusion des doublons topologiques point/polygone d'OSM** (un même hôpital ou centre de santé saisi à la fois comme bâtiment `way/*` et comme point `node/*` à moins de 35 m) en conservant l'union des attributs ;
   - **typage et relecture des niveaux de soin (1, 2, 3)** : attribution du niveau par type OSM et promotion explicite des CHU / CHR en niveau 3 (couverture stricte conformément au cadrage) ;
   - **topologisation du graphe routier** : découpage des 130 783 chemins OSM aux carrefours partagés pour obtenir 318 229 arcs élémentaires (`troncon`) reliés par 228 554 carrefours (`noeud`), inversion des sens uniques inverses (`oneway = -1`), suppression des boucles dégénérées et identification de la composante connexe principale (99,8 % du graphe) ;
   - **accrochage au réseau routier** : rattachement de chaque établissement (`ACCROCHER`) et de chaque hexagone H3 (`RACCORDER`) au nœud le plus proche appartenant à la composante routière principale.
3. **Indexation et performance (`GIST` / `B-tree`)** : vérification par `EXPLAIN (ANALYZE, BUFFERS)` que les jointures spatiales, recherches des plus proches voisins (KNN `<->`) et tampons (`ST_DWithin`) utilisent effectivement les index spatiaux `GIST`.

---

## 2. Organisation des fichiers de la phase

```
Acces_soins_Region_Casablanca-Settat/
├── run_seance4.bat                           lanceur Windows : nettoyage + import PostGIS + requêtes + dump
├── README_PRETRAITEMENT.md                   ce document
├── modele_acces_soins.drawio                 modèle MCD + MLD + pipeline (éditable dans draw.io)
├── sql/
│   ├── schema.sql                            DDL complet du schéma PostGIS « sante » (8 tables, index GIST/B-tree)
│   ├── requetes.sql                          3 requêtes spatiales métier commentées + EXPLAIN (ANALYZE, BUFFERS)
│   └── acces_soins.backup                    dump PostGIS complet compressé (pg_dump -Fc, 42 Mo, restaurable)
├── scripts/
│   ├── config.py                             paramètres centralisés (CRS EPSG:26191, chemins)
│   ├── nettoyage.py                          pipeline de nettoyage v2 (supporte --dry-run)
│   ├── import_postgis.py                     création schéma, import ogr2ogr, tests de rejet, requêtes, pg_dump
│   └── generer_presentation_seance4.py       génère le support PDF de présentation de la séance 4
├── donnees_traitees/
│   ├── sante_nettoyee.gpkg                   6 couches nettoyées complètes en EPSG:26191 (115 Mo, local)
│   └── sante_nettoyee_couches_legeres.gpkg   4 couches légères versionnées sur Git (8 Mo)
├── preuves/
│   ├── rapport_nettoyage.md                  bilan chiffré avant / après nettoyage (GÉNÉRÉ)
│   ├── carte_nettoyage.png                   planche visuelle comparative avant / après (GÉNÉRÉ)
│   └── resultats_requetes_seance4.md         plans EXPLAIN ANALYZE + résultats des 3 requêtes + tests de rejet
└── Phase_2_Pretraitement_et_Geodatabase/     dossier récapitulatif regroupant tous les livrables de la phase 2
```

---

## 3. Le modèle de données (MCD / MLD) et le schéma PostGIS `sante`

Le fichier [`modele_acces_soins.drawio`](modele_acces_soins.drawio) (ainsi que le document [`Avancement_projet_MCD_MLD.pdf`](Phase_2_Pretraitement_et_Geodatabase/modelisation_mcd_mld/Avancement_projet_MCD_MLD.pdf)) structure la géodatabase autour de **8 tables** dans le schéma `sante` :

| Table | Rôle | Géométrie (`EPSG:26191`) | Clé primaire | Clés étrangères & Contraintes principales |
| --- | --- | --- | --- | --- |
| `sante.type_etablissement` | Référence des types d'offre et niveaux de soin | *Aucune* | `code_type` | `poids_offre > 0`, `niveau_soin IN ('primaire', 'secondaire', 'tertiaire', 'officine', 'autre')` |
| `sante.classe_route` | Référence des classes OSM et vitesses par défaut | *Aucune* | `code_classe` | `vitesse_defaut BETWEEN 5 AND 130` |
| `sante.province` | 9 préfectures et provinces de la région | `MultiPolygon, 26191` | `code_province` | `pop_totale_2024 >= 0` |
| `sante.commune` | 153 communes avec population RGPH 2024 | `MultiPolygon, 26191` | `code_hcp` | FK → `province(code_province)`, `pop_2024 >= 0`, `superficie_km2 > 0` |
| `sante.etablissement` | Établissements de santé nettoyés et typés | `Point, 26191` | `osm_id` | FK → `type_etablissement`, FK → `commune(code_hcp)`, FK → `noeud(id_noeud)`, `capacite_lits >= 0` |
| `sante.noeud` | Carrefours et extrémités du graphe routier | `Point, 26191` | `id_noeud` | `degre >= 0` |
| `sante.troncon` | Arcs routiers orientés et valués en secondes | `LineString, 26191` | `id_troncon` | FK → `classe_route`, 2 FK → `noeud` (`noeud_depart <> noeud_arrivee`), `longueur_m > 0`, `cout_secondes > 0` |
| `sante.maille_h3` | Grille hexagonale H3 (rés. 8) et demande WorldPop | `MultiPolygon, 26191` | `h3_index` | FK → `commune(code_hcp)`, FK → `noeud(id_noeud)`, `pop_worldpop >= 0` |

### Index déclarés dans `sql/schema.sql`
- **6 index spatiaux `GIST`** : un sur chaque colonne `geom` (`province_geom_gist`, `commune_geom_gist`, `etablissement_geom_gist`, `noeud_geom_gist`, `troncon_geom_gist`, `maille_h3_geom_gist`).
- **9 index attributaires `B-tree`** : sur toutes les clés étrangères et colonnes de filtrage fréquent (`commune_code_prov_idx`, `etablissement_type_idx`, `etablissement_code_hcp_idx`, `etablissement_id_noeud_idx`, `troncon_depart_idx`, `troncon_arrivee_idx`, `troncon_classe_idx`, `maille_h3_code_hcp_idx`, `maille_h3_id_noeud_idx`).

---

## 4. Commandes d'exécution

### 4.1 Lancer toute la phase 2 en une commande
```bat
run_seance4.bat
```

### 4.2 Tester le nettoyage en mode « rapport seul » (`--dry-run`)
Le drapeau `--dry-run` exécute l'intégralité des diagnostics géométriques et topologiques et met à jour `preuves/rapport_nettoyage.md`, **sans écrire ni modifier aucun fichier dans `donnees_traitees/`** :
```bash
python scripts/nettoyage.py --dry-run
```

### 4.3 Exécuter le nettoyage complet et générer le GeoPackage
```bash
python scripts/nettoyage.py
```
Produit :
- `donnees_traitees/sante_nettoyee.gpkg` (les 6 couches spatiales en `EPSG:26191`) ;
- `preuves/rapport_nettoyage.md` (bilan avant/après) ;
- `preuves/carte_nettoyage.png` (planche comparative 4 panneaux).

### 4.4 Charger la géodatabase PostGIS, exécuter les requêtes et générer le dump
```bash
python scripts/import_postgis.py
```
Ce script automatise 6 opérations :
1. Exécute `sql/schema.sql` dans la base PostgreSQL/PostGIS `acces_soins`.
2. Charge les 6 couches de `sante_nettoyee.gpkg` vers un schéma temporaire `staging` via `ogr2ogr`.
3. Insère les données dans `sante.*` dans l'ordre des clés étrangères et lance `ANALYZE`.
4. Vérifie automatiquement que **4 insertions invalides sont rejetées** par PostGIS (violation de clé étrangère `code_hcp`, mauvais SRID `4326` au lieu de `26191`, suppression interdite `ON DELETE RESTRICT`, boucle dégénérée `noeud_depart = noeud_arrivee`).
5. Exécute `sql/requetes.sql` et consigne les plans `EXPLAIN (ANALYZE, BUFFERS)` et les résultats dans `preuves/resultats_requetes_seance4.md`.
6. Génère le dump compressé `sql/acces_soins.backup` via `pg_dump -Fc` et **teste immédiatement sa restauration** (`pg_restore`) dans une base temporaire `acces_soins_restore_test`.

### 4.5 Restaurer directement la base PostGIS chez soi (ou lors de l'évaluation)
```bash
psql -U postgres -c "CREATE DATABASE acces_soins;"
pg_restore -U postgres -d acces_soins --no-owner --no-privileges sql/acces_soins.backup
```

---

## 5. Détail des opérations de nettoyage et cas réels traités

| Couche | Brut en entrée | Nettoyé en sortie | Cas réels d'erreurs géométriques / topologiques résolus |
| --- | --- | --- | --- |
| **Limites (`commune`, `province`)** | 153 communes, 9 provinces | **153 communes**, **9 provinces** | Jointure 153/153 avec le RGPH 2024 (**7 688 967 hab.**) ; fermeture topologique de **5 micro-trous d'anneaux** résiduels lors de la fusion des communes en provinces. |
| **Offre de soins (`etablissement`)** | 1 591 entités dans la région (1 737 sur bbox) | **1 583 établissements** | Conversion de 227 bâtiments (`Polygon`/`MultiPolygon`) en centroïdes ; **fusion de 8 doublons topologiques point/polygone OSM** (ex. établissement saisi à la fois comme bâtiment `way/*` et point `node/*` à moins de 35 m, avec fusion des tags `name`, `phone`, `emergency`) ; relecture des hôpitaux avec **5 CHU/CHR promus en niveau 3** ; exclusion des pharmacies/dentistes du calcul de premier recours. |
| **Graphe routier (`noeud`, `troncon`)** | 130 783 ways OSM (53 907 km) | **228 554 nœuds**, **318 229 tronçons** | Les ways OSM bruts ne sont pas coupés aux intersections intermédiaires (composante connexe de seulement 11 005 nœuds avant traitement). Le découpage aux sommets partagés porte la **composante connexe principale à 228 022 nœuds (99,8 %)**. Inversion géométrique de **294 sens uniques `oneway = -1`**, élimination de **44 boucles** et **4 tronçons de longueur nulle**. |
| **Demande (`maille_h3`)** | Raster WorldPop 100 m (2 572 × 1 948 px) | **25 255 hexagones H3** (rés. 8) | Agrégation zonale WorldPop (**7 472 060 hab.**), affectation à la commune englobante et raccordement au nœud routier principal le plus proche (distance médiane de raccordement : 206 m). |

---

## 6. Les 3 requêtes spatiales métier et l'apport des index (`sql/requetes.sql`)

| # | Question métier | Opérateurs spatiaux | Plan `EXPLAIN (ANALYZE, BUFFERS)` | Temps | Résultat clé |
| --- | --- | --- | --- | --- | --- |
| **1** | **Jointure spatiale** : quelle est l'offre de soins par niveau et le ratio pour 10 000 hab. dans chaque province et commune ? | `ST_Contains(c.geom, e.geom)` | `Nested Loop` + **`Index Scan using etablissement_geom_gist`** (656 buffers lus en mémoire, 0 lecture disque) | **26,3 ms** | **79 communes sur 153** (soit **878 242 hab.**, 11,4 % de la population régionale) ne comptent **aucun établissement** recensé dans OSM. |
| **2** | **Plus proche voisin (KNN)** : quelle population réside à plus de 5 km, 10 km ou 15 km du centre de soins de base le plus proche ? | `CROSS JOIN LATERAL` avec opérateur KNN `e.geom <-> m.geom` | **`Index Scan using etablissement_geom_gist`** ordonné par distance pour chacune des 25 255 mailles H3 (sans produit cartésien 25 255 × 468) | **192,4 ms** | **1 088 866 habitants** (14,6 % de la région) vivent à **plus de 5 km** à vol d'oiseau d'un centre de soins de base (maximum : 26,6 km à Benslimane). |
| **3** | **Agrégation spatiale** : quelle est la densité et la carrossabilité du réseau routier dans un rayon de 1 km autour des hôpitaux et cliniques ? | `ST_DWithin(e.geom, t.geom, 1000.0)` | **`Bitmap Index Scan on troncon_geom_gist`** sur les 318 229 tronçons | **295,6 ms** | **319 hôpitaux et cliniques** analysés ; 98 à 100 % des voies riveraines sont carrossables à Casablanca/Mohammedia, contre 92,7 % à El Jadida. |


---

## 7. Planche cartographique de contrôle du nettoyage (EPSG:26191)

![Carte avant/après nettoyage](preuves/carte_nettoyage.png)
