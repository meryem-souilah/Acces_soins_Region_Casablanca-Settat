# Accès aux soins dans la région Casablanca-Settat
# Accès aux soins dans la région Casablanca-Settat

Projet du module **Géodata appliquée** — Geo-AI appliqué à un défi spatial
(élèves ingénieurs 3ᵉ année).

## Défi spatial

> **Quelles zones de la région Casablanca-Settat sont mal desservies en
> établissements de santé, et où faut-il intervenir en priorité ?**

Le projet mesure le temps d'accès par la route de la population aux
établissements de santé (hôpitaux, cliniques, médecins, pharmacies), identifie
les zones sous-desservies à l'aide d'un modèle de machine learning, puis
propose des recommandations priorisées.

**Utilisateurs cibles :** Direction régionale de la Santé, Conseil régional
Casablanca-Settat, urbanistes et planificateurs des communes.

**Emprise :** région Casablanca-Settat (découpage par le polygone régional HCP).

## Sources de données

| Donnée | Source | Licence |
|---|---|---|
| Établissements de santé | OpenStreetMap (API Overpass) | ODbL 1.0 |
| Réseau routier | OpenStreetMap | ODbL 1.0 |
| Population maillée 100 m (2020) | WorldPop | CC BY 4.0 |
| Limites administratives (communes) | HCP, via OCHA / HDX | voir page HDX |
| Population légale RGPH 2024 | HCP | citation de la source |

Détail complet (URL, dates, CRS, emprise) : [`SOURCES.md`](SOURCES.md).

## Arborescence

```
donnees_brutes/      données téléchargées, non versionnées
donnees_traitees/    données nettoyées, non versionnées
scripts/             scripts d'acquisition, de nettoyage et de modélisation
sql/                 schéma PostGIS et requêtes métier
notebooks/           exploration des données
docs/                document de 1er jet, schémas, documentation
preuves/             échantillons et captures prouvant l'accès aux données
archive/             anciens fichiers conservés pour référence
```

## Installation de l'environnement

```bash
git clone https://github.com/meryem-souilah/Acces_soins_Region_Casablanca-Settat.git
cd Acces_soins_Region_Casablanca-Settat
conda env create -f environment.yml
conda activate geodata-sante
```

Sans conda : `pip install -r requirements.txt` (Python ≥ 3.10).

## Avancement

| Phase | Séance | Statut |
|---|---|---|
| 0. Choix du thème et audit des sources | Séance 2 | 🟡 Réaliser |
| 1. Collecte (script reproductible) | Séance 3 | 🟡 Réaliser |
| 2. Pré-traitement et géodatabase PostGIS | Séance 4 | ⚪ À venir |
| 3. Traitement et Geo-AI | Séance 5 | ⚪ À venir |
| 4. Contrôle qualité | Séance 6 | ⚪ À venir |
| 5. Diffusion et recommandations | Séance 7 | ⚪ À venir |

## Équipe et rotation du lead

| N° | Membre | Lead avant la séance |
|---|---|---|
| M1 | _Nom 1_ | SOUILAH Meryem |
| M2 | _Nom 2_ | Manyani Hiba |
| M3 | _Nom 3_ | ZOUHRI Imane|
| M4 | _Nom 4_ | BELMOKHTARE Fatima Ezzahra|
| M5 | _Nom 5_ | GUEROUANE Imane|
