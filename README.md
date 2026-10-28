# Accès aux soins dans la région Casablanca-Settat

Projet du module **Géodata appliquée** — *Geo-AI appliqué à un défi spatial* (élèves ingénieurs 3ᵉ année).

> **Défi spatial :** *Où implanter quel type d'offre de soins dans la région Casablanca-Settat pour maximiser la population couverte dans le temps d'accès adapté à chaque niveau ?*

- **Territoire :** Région Casablanca-Settat (code géographique HCP `06`), **9 provinces et préfectures**, **153 communes** (**19 448 km²**, **7 688 967 habitants** au RGPH 2024).
- **Système de coordonnées unique :** **`EPSG:26191`** (*Merchich / Nord Maroc*).

---

## Organisation du dépôt par phase

Toutes les ressources du projet (documentation, scripts, schémas SQL, données et preuves) sont classées directement dans le dossier de leur phase :

| Phase | Séance | Dossier | Statut | Contenu principal |
|---|---|---|---|---|
| **Phase 0** — Cadrage et audit des sources | Séance 2 | [`Phase_0_Cadrage_et_Audit_Sources/`](Phase_0_Cadrage_et_Audit_Sources/) | ✅ Réalisé | [`README.md`](Phase_0_Cadrage_et_Audit_Sources/README.md) (cadrage complet), [`SOURCES.md`](Phase_0_Cadrage_et_Audit_Sources/SOURCES.md), scripts de test d'accès et échantillons dans [`preuves/`](Phase_0_Cadrage_et_Audit_Sources/preuves/) |
| **Phase 1** — Acquisition et collecte | Séance 3 | [`Phase_1_Acquisition_et_Collecte/`](Phase_1_Acquisition_et_Collecte/) | ✅ Réalisé | [`README.md`](Phase_1_Acquisition_et_Collecte/README.md) (documentation collecte), [`scripts/`](Phase_1_Acquisition_et_Collecte/scripts/) (`collecte.py`, `controle_collecte.py`), [`donnees_brutes/`](Phase_1_Acquisition_et_Collecte/donnees_brutes/) (`manifest.json` SHA-256, couches `EPSG:26191`), [`preuves/`](Phase_1_Acquisition_et_Collecte/preuves/) (`controle_collecte.md`, `carte_controle.png`, projet QGIS), [`uml/`](Phase_1_Acquisition_et_Collecte/uml/) |
| **Phase 2** — Pré-traitement et géodatabase PostGIS | Séance 4 | [`Phase_2_Pretraitement_et_Geodatabase/`](Phase_2_Pretraitement_et_Geodatabase/) | ✅ Réalisé | [`modelisation_mcd_mld/modele_acces_soins.drawio`](Phase_2_Pretraitement_et_Geodatabase/modelisation_mcd_mld/modele_acces_soins.drawio), [`sql/`](Phase_2_Pretraitement_et_Geodatabase/sql/) (`schema.sql`, `requetes.sql`, `acces_soins.backup`) |
| **Phase 3** — Traitement et Geo-AI | Séance 5 | [`Phase_3_Traitement_et_GeoAI/`](Phase_3_Traitement_et_GeoAI/) | ⚪ À venir | — |
| **Phase 4** — Contrôle qualité | Séance 6 | [`Phase_4_Controle_Qualite/`](Phase_4_Controle_Qualite/) | ⚪ À venir | — |
| **Phase 5** — Diffusion et recommandations | Séance 7 | [`Phase_5_Diffusion_et_Recommandations/`](Phase_5_Diffusion_et_Recommandations/) | ⚪ À venir | — |
