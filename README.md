# Accès aux soins dans la région Casablanca-Settat

Projet fil rouge du module **Géodata appliquée** — *Geo-AI appliqué à un défi spatial* (élèves ingénieurs 3ᵉ année).

> **Défi spatial :** *Quelles zones de la région Casablanca-Settat sont mal desservies en établissements de santé, et où faut-il intervenir en priorité ?*

- **Utilisateurs cibles :** Direction régionale de la Santé, Conseil régional Casablanca-Settat, urbanistes et planificateurs des communes.
- **Emprise d'étude :** Région Casablanca-Settat (code géographique HCP `06`), formée par l'union exacte de ses **153 communes** (**9 provinces**, **19 448 km²**, **7 688 967 habitants** au RGPH 2024).
- **Système de coordonnées de référence (CRS) :** **`EPSG:26191`** (*Merchich / Nord Maroc*, projection conforme conique de Lambert métrique).

---

## 📂 Navigation rapide par phase du projet

Le dépôt est organisé **par phase** (selon le découpage des séances du module) afin de faciliter la consultation et l'évaluation de chaque livrable :

| Phase | Séance | Dossier dédié | README de phase | Statut | Principaux livrables contenus dans le dossier |
|---|---|---|---|---|---|
| **Phase 0** — Cadrage & Audit des sources | Séance 2 | [`Phase_0_Cadrage_et_Audit_Sources/`](Phase_0_Cadrage_et_Audit_Sources/) | [`README_CADRAGE.md`](README_CADRAGE.md) | ✅ Réalisé | [`GUIDE_INSTALLATION.md`](GUIDE_INSTALLATION.md), [`SOURCES.md`](Phase_0_Cadrage_et_Audit_Sources/SOURCES.md), [`00_test_acces.py`](Phase_0_Cadrage_et_Audit_Sources/scripts/00_test_acces.py), rapport d'accès initial, échantillons GeoJSON/GeoTIFF |
| **Phase 1** — Acquisition & Collecte reproductible | Séance 3 | [`Phase_1_Acquisition_et_Collecte/`](Phase_1_Acquisition_et_Collecte/) | [`README_COLLECTE.md`](README_COLLECTE.md) | ✅ Réalisé | Présentation [`seance3_acquisition.pdf`](Phase_1_Acquisition_et_Collecte/presentation/seance3_acquisition.pdf), scripts [`collecte.py`](Phase_1_Acquisition_et_Collecte/scripts/collecte.py) & [`controle_collecte.py`](Phase_1_Acquisition_et_Collecte/scripts/controle_collecte.py), [`manifest.json`](Phase_1_Acquisition_et_Collecte/donnees_brutes_provenance/manifest.json) (SHA-256), 6 diagrammes [`uml/`](Phase_1_Acquisition_et_Collecte/uml/), [`carte_controle.png`](Phase_1_Acquisition_et_Collecte/preuves/carte_controle.png), projet QGIS |
| **Phase 2** — Pré-traitement & Géodatabase PostGIS | Séance 4 | [`Phase_2_Pretraitement_et_Geodatabase/`](Phase_2_Pretraitement_et_Geodatabase/) | [`README_PRETRAITEMENT.md`](README_PRETRAITEMENT.md) | ✅ Réalisé | Présentation [`seance4_pretraitement.pdf`](Phase_2_Pretraitement_et_Geodatabase/presentation/seance4_pretraitement.pdf), MCD/MLD [`modele_acces_soins.drawio`](Phase_2_Pretraitement_et_Geodatabase/modelisation_mcd_mld/modele_acces_soins.drawio) & [PDF](Phase_2_Pretraitement_et_Geodatabase/modelisation_mcd_mld/Avancement_projet_MCD_MLD.pdf), DDL [`schema.sql`](Phase_2_Pretraitement_et_Geodatabase/sql/schema.sql), 3 requêtes métier [`requetes.sql`](Phase_2_Pretraitement_et_Geodatabase/sql/requetes.sql) + [`resultats_requetes_seance4.md`](Phase_2_Pretraitement_et_Geodatabase/preuves/resultats_requetes_seance4.md), script [`nettoyage.py`](Phase_2_Pretraitement_et_Geodatabase/scripts/nettoyage.py) (`--dry-run`), [`rapport_nettoyage.md`](Phase_2_Pretraitement_et_Geodatabase/preuves/rapport_nettoyage.md), [`carte_nettoyage.png`](Phase_2_Pretraitement_et_Geodatabase/preuves/carte_nettoyage.png), dump [`acces_soins.backup`](sql/acces_soins.backup) |
| **Phase 3** — Traitement spatial & Geo-AI | Séance 5 | [`Phase_3_Traitement_et_GeoAI/`](Phase_3_Traitement_et_GeoAI/) | [`README.md`](Phase_3_Traitement_et_GeoAI/README.md) | ⚪ À venir | Calcul d'accessibilité routière (Dijkstra), indicateurs par maille H3 et modèle ML |
| **Phase 4** — Contrôle qualité (ISO 19157) | Séance 6 | [`Phase_4_Controle_Qualite/`](Phase_4_Controle_Qualite/) | [`README.md`](Phase_4_Controle_Qualite/README.md) | ⚪ À venir | Validation croisée spatiale, analyse des biais et contrôle qualité |
| **Phase 5** — Diffusion & Recommandations | Séance 7 | [`Phase_5_Diffusion_et_Recommandations/`](Phase_5_Diffusion_et_Recommandations/) | [`README.md`](Phase_5_Diffusion_et_Recommandations/README.md) | ⚪ À venir | Cartographie décisionnelle et priorisation des implantations sanitaires |

---

## 🗂️ Récapitulatif des livrables par phase complétée

### 🔹 Phase 0 — Cadrage et audit des sources (Séance 2)
- **Catalogue des 5 sources** : [`Phase_0_Cadrage_et_Audit_Sources/SOURCES.md`](Phase_0_Cadrage_et_Audit_Sources/SOURCES.md)
- **Preuves d'accès et échantillons** : [`Phase_0_Cadrage_et_Audit_Sources/preuves/`](Phase_0_Cadrage_et_Audit_Sources/preuves/)

### 🔹 Phase 1 — Acquisition et collecte reproductible (Séance 3)
- **Support de présentation Séance 3** : [`Phase_1_Acquisition_et_Collecte/presentation/seance3_acquisition.pdf`](Phase_1_Acquisition_et_Collecte/presentation/seance3_acquisition.pdf)
- **Pipeline de collecte et contrôle CRS (`EPSG:26191`)** : [`Phase_1_Acquisition_et_Collecte/scripts/collecte.py`](Phase_1_Acquisition_et_Collecte/scripts/collecte.py) & [`controle_collecte.py`](Phase_1_Acquisition_et_Collecte/scripts/controle_collecte.py)
- **Manifeste de provenance (`SHA-256`)** : [`Phase_1_Acquisition_et_Collecte/donnees_brutes_provenance/manifest.json`](Phase_1_Acquisition_et_Collecte/donnees_brutes_provenance/manifest.json)
- **Rapport et cartes de contrôle** : [`Phase_1_Acquisition_et_Collecte/preuves/controle_collecte.md`](Phase_1_Acquisition_et_Collecte/preuves/controle_collecte.md) & [`carte_controle.png`](Phase_1_Acquisition_et_Collecte/preuves/carte_controle.png)
- **Diagrammes d'architecture UML (6 diagrammes PlantUML)** : [`Phase_1_Acquisition_et_Collecte/uml/`](Phase_1_Acquisition_et_Collecte/uml/)

### 🔹 Phase 2 — Pré-traitement et géodatabase PostGIS (Séance 4)
- **Support de présentation Séance 4** : [`Phase_2_Pretraitement_et_Geodatabase/presentation/seance4_pretraitement.pdf`](Phase_2_Pretraitement_et_Geodatabase/presentation/seance4_pretraitement.pdf)
- **Modèle conceptuel et logique (MCD / MLD)** : [`Phase_2_Pretraitement_et_Geodatabase/modelisation_mcd_mld/modele_acces_soins.drawio`](Phase_2_Pretraitement_et_Geodatabase/modelisation_mcd_mld/modele_acces_soins.drawio) et [`Avancement_projet_MCD_MLD.pdf`](Phase_2_Pretraitement_et_Geodatabase/modelisation_mcd_mld/Avancement_projet_MCD_MLD.pdf)
- **DDL complet du schéma PostGIS `sante`** (8 tables, 10 clés étrangères, contraintes `CHECK`, 6 index `GIST`, 9 index `B-tree`) : [`Phase_2_Pretraitement_et_Geodatabase/sql/schema.sql`](Phase_2_Pretraitement_et_Geodatabase/sql/schema.sql)
- **Script de nettoyage v2 avec mode `--dry-run`** (validation `make_valid`, fusion des doublons topologiques point/polygone OSM à < 35 m, découpage du graphe routier aux carrefours partagés avec 99,8 % de connectivité sur 228 554 nœuds et 318 229 tronçons, génération des 25 255 hexagones H3 rés. 8) : [`Phase_2_Pretraitement_et_Geodatabase/scripts/nettoyage.py`](Phase_2_Pretraitement_et_Geodatabase/scripts/nettoyage.py)
- **Rapport avant/après nettoyage et planche visuelle** : [`Phase_2_Pretraitement_et_Geodatabase/preuves/rapport_nettoyage.md`](Phase_2_Pretraitement_et_Geodatabase/preuves/rapport_nettoyage.md) & [`carte_nettoyage.png`](Phase_2_Pretraitement_et_Geodatabase/preuves/carte_nettoyage.png)
- **3 requêtes spatiales métier commentées avec `EXPLAIN (ANALYZE, BUFFERS)`** : [`Phase_2_Pretraitement_et_Geodatabase/sql/requetes.sql`](Phase_2_Pretraitement_et_Geodatabase/sql/requetes.sql) et résultats d'exécution [`resultats_requetes_seance4.md`](Phase_2_Pretraitement_et_Geodatabase/preuves/resultats_requetes_seance4.md)
- **Dump PostGIS complet restaurable (`pg_dump -Fc`)** : [`sql/acces_soins.backup`](sql/acces_soins.backup) (42,13 Mo, restauration testée automatiquement via `pg_restore`)
- **Couches nettoyées (GeoPackage)** : [`donnees_traitees/sante_nettoyee_couches_legeres.gpkg`](donnees_traitees/sante_nettoyee_couches_legeres.gpkg)

---

## ⚙️ Installation et exécution reproductible

### 1. Environnement Python (versions figées)

```bash
git clone https://github.com/meryem-souilah/Acces_soins_Region_Casablanca-Settat.git
cd Acces_soins_Region_Casablanca-Settat
conda env create -f environment.yml     # Python 3.11 + requirements-lock.txt
conda activate geodata-sante
```

Sans conda : Python 3.11 puis `pip install -r requirements-lock.txt`.

### 2. Exécution de la Phase 1 (Collecte & Contrôle)

```bash
run_collecte.bat                         # Collecte + contrôle (Windows)
python scripts/collecte.py               # Collecte (utilise le cache local si présent)
python scripts/controle_collecte.py      # Contrôle CRS EPSG:26191, emprise, jointure HCP
```

### 3. Exécution de la Phase 2 (Nettoyage & Géodatabase PostGIS)

```bash
run_seance4.bat                          # Exécute toute la Phase 2 (Windows)
python scripts/nettoyage.py --dry-run    # Mode rapport seul (aucune écriture de fichier)
python scripts/nettoyage.py              # Nettoyage complet + export GeoPackage
python scripts/import_postgis.py         # Création schéma PostGIS, import ogr2ogr, 3 requêtes EXPLAIN ANALYZE, pg_dump
```

Pour restaurer directement la base PostGIS complète (`acces_soins`) sans relancer le pipeline :

```bash
psql -U postgres -c "CREATE DATABASE acces_soins;"
pg_restore -U postgres -d acces_soins --no-owner --no-privileges sql/acces_soins.backup
```

---

## 🌳 Arborescence complète du dépôt

```text
Acces_soins_Region_Casablanca-Settat/
├── Phase_0_Cadrage_et_Audit_Sources/       # Livrables Séance 2 (cadrage, audit des 5 sources, échantillons)
├── Phase_1_Acquisition_et_Collecte/        # Livrables Séance 3 (scripts collecte/contrôle, manifeste SHA-256, UML, présentation)
├── Phase_2_Pretraitement_et_Geodatabase/   # Livrables Séance 4 (MCD/MLD, schema.sql, nettoyage.py, requetes.sql, rapport, présentation)
├── Phase_3_Traitement_et_GeoAI/            # Séance 5 (À venir : routage Dijkstra, accessibilité H3, modèle Geo-AI)
├── Phase_4_Controle_Qualite/               # Séance 6 (À venir : contrôle qualité ISO 19157 et validation spatiale)
├── Phase_5_Diffusion_et_Recommandations/   # Séance 7 (À venir : cartographie décisionnelle et recommandations)
├── scripts/                                # Scripts techniques d'exécution directe à la racine
├── sql/                                    # DDL PostGIS (schema.sql), 3 requêtes métier (requetes.sql) et dump (acces_soins.backup)
├── donnees_brutes/                         # Données brutes par source (limites, osm_sante, worldpop, hcp, manifest.json)
├── donnees_traitees/                       # Données nettoyées en EPSG:26191 (GeoPackage)
├── preuves/                                # Rapports automatiques, plans EXPLAIN ANALYZE, cartes et projet QGIS
└── presentation/                           # Supports de présentation PDF et sources Beamer (.tex) des séances 3 et 4
```
