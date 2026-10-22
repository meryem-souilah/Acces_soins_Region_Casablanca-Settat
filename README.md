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

**Emprise :** région Casablanca-Settat (code géographique HCP 06), contour
formé par l'union de ses 153 communes. **CRS de toutes les couches :** EPSG:26191.

## Sources de données

| Donnée | Source | Licence |
|---|---|---|
| Communes et contour régional | OpenStreetMap (`admin_level=8`, code HCP `ref:MA:HCP`) | ODbL 1.0 |
| Établissements de santé | OpenStreetMap (API Overpass) | ODbL 1.0 |
| Réseau routier | OpenStreetMap (extrait Geofabrik) | ODbL 1.0 |
| Population maillée 100 m (2020) | WorldPop | CC BY 4.0 |
| Population légale RGPH 2024 | HCP (PDF des tableaux) | citation de la source |

Le jeu COD-AB d'OCHA/HDX pour le Maroc s'arrête aux provinces : les communes
viennent d'OSM, où chacune porte son code HCP, identique à celui du tableau de
population légale (153 communes sur 153 appariées).

Détail complet (URL, millésime, licence, CRS, emprise, volume) : [`SOURCES.md`](SOURCES.md).
Provenance et empreintes SHA-256 : [`donnees_brutes/README.md`](donnees_brutes/README.md).

## Installation de l'environnement

Les versions sont figées : celles qui ont produit le jeu de données.

```bash
git clone https://github.com/meryem-souilah/Acces_soins_Region_Casablanca-Settat.git
cd Acces_soins_Region_Casablanca-Settat
conda env create -f environment.yml     # Python 3.11.17 + requirements-lock.txt
conda activate geodata-sante
```

Sans conda : Python 3.11 puis `pip install -r requirements-lock.txt`.

## Collecte des données (phase 1)

```bash
run_collecte.bat                                   # collecte + contrôle (Windows)
python scripts/collecte.py                         # collecte, cache réutilisé
python scripts/collecte.py --force                 # tout retélécharger depuis les sources
python scripts/controle_collecte.py                # contrôle CRS, emprise, jointure HCP
```

Le contrôle écrit `preuves/controle_collecte.md` et `preuves/carte_controle.png`,
et sort avec le code 0 seulement si tout est conforme.

## Reproductibilité dans le temps

Les sources en ligne évoluent : OSM change chaque jour, Geofabrik ne conserve
que le dernier extrait, un lien peut disparaître. Re-télécharger plus tard
donne donc d'autres données. Pour retrouver **exactement** le jeu de données du
projet, on part de l'archive des fichiers bruts :

```bash
python scripts/collecte.py --archiver
# → sauvegarde_sources/sources_brutes_AAAA-MM-JJ.zip : fichiers bruts exacts + manifeste

python scripts/collecte.py --depuis-archive sauvegarde_sources/sources_brutes_2026-10-22.zip
python scripts/controle_collecte.py
# → restaure les fichiers, vérifie leurs SHA-256, rejoue le traitement hors ligne
```

L'archive (262 Mo) dépasse la limite de GitHub pour un dépôt : elle est publiée
en **Release** du dépôt. Pour la récupérer :

```bash
gh release download donnees-2026-10-22 --dir sauvegarde_sources
```

| Garantie | Comment |
|---|---|
| Même code | dépôt Git |
| Même environnement | `environment.yml`, `requirements-lock.txt` (versions exactes) |
| Mêmes données brutes | archive en Release, SHA-256 vérifiés à la restauration |
| Même résultat | `controle_collecte.py` : 153 communes, 1 588 établissements, 130 813 tronçons, 7 466 216 hab. |

## Arborescence

```
scripts/             config.py, collecte.py, controle_collecte.py
donnees_brutes/      un dossier par source ; seuls README, manifeste, requêtes et CSV HCP sont versionnés
preuves/             rapport et carte de contrôle, capture et projet QGIS
presentation/        présentations des séances (LaTeX)
sauvegarde_sources/  archive des sources brutes (non versionnée, publiée en Release)
donnees_traitees/    données nettoyées (phase 2)
sql/                 schéma PostGIS et requêtes métier (phase 2)
notebooks/           exploration des données
docs/                document de 1er jet, schémas, documentation
```

## Avancement

| Phase | Séance | Statut |
|---|---|---|
| 0. Choix du thème et audit des sources | Séance 2 | ✅ Réalisé |
| 1. Collecte (script reproductible) | Séance 3 | ✅ Réalisé |
| 2. Pré-traitement et géodatabase PostGIS | Séance 4 | ⚪ À venir |
| 3. Traitement et Geo-AI | Séance 5 | ⚪ À venir |
| 4. Contrôle qualité | Séance 6 | ⚪ À venir |
| 5. Diffusion et recommandations | Séance 7 | ⚪ À venir |




