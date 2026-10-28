# Phase de collecte des données — README

Projet **Géodata appliquée** · Accès aux soins, région Casablanca-Settat
Défi : *où implanter quel type d'offre de soins pour maximiser la population couverte
dans le temps d'accès adapté à chaque niveau ?*

Ce document décrit tout ce qui a été mis en place pour la collecte : les scripts, le lanceur `run_collecte.bat`, la façon de relancer **une seule source**
pour tester, les fichiers produits et les problèmes déjà rencontrés avec leur solution.

---

## 1. Principe

Une seule commande récupère toutes les sources, les découpe sur la région, les
reprojette dans un **CRS unique (EPSG:26191, Merchich / Nord Maroc)** et documente
leur provenance (URL, date, licence, SHA-256). Les téléchargements sont mis en
**cache** : une relance réutilise ce qui est déjà présent et ne retélécharge que sur
demande (`--force`).

Les cinq sources :

| Clé | Donnée | Producteur | Accès |
| --- | --- | --- | --- |
| `limites` | Communes (ADM3) et contour régional | HCP, diffusé par OCHA sur HDX | API HDX, ou zip déposé à la main ; secours geoBoundaries |
| `sante` | Établissements de santé | OpenStreetMap | API Overpass (3 serveurs essayés) |
| `routes` | Réseau routier circulable de toute la région | OpenStreetMap | osmnx (Overpass, par tuiles de 250 km²) |
| `worldpop` | Population maillée 100 m, 2020 (*constrained*) | WorldPop (Univ. Southampton) | téléchargement direct (2 miroirs) |
| `hcp` | Population légale RGPH 2024 | HCP | PDF hcp.ma, ou PDF déposé à la main |

---

## 2. Organisation des fichiers

```
Acces_soins_Region_Casablanca-Settat/
├── run_collecte.bat          lanceur Windows : collecte + contrôle
├── run_collecte.sh           même lanceur pour Linux / macOS
├── environment.yml           environnement conda « geodata-sante »
├── requirements.txt          dépendances pip équivalentes
├── SOURCES.md                inventaire des sources (GÉNÉRÉ par collecte.py)
├── GUIDE_INSTALLATION.md     installation de l'environnement
├── scripts/
│   ├── config.py             TOUS les paramètres : emprise, CRS, URL, provinces…
│   ├── 00_test_acces.py      preuve d'accès à chaque source (Go/No-Go)
│   ├── 01_demo_carte.py      carte de démo à partir des échantillons
│   ├── collecte.py           pipeline de collecte complet
│   └── controle_collecte.py  contrôle CRS / emprise / volumes + carte
├── donnees_brutes/           (créé par collecte.py)
│   ├── limites/  osm_sante/  osm_routes/  worldpop/  hcp/
│   ├── manifest.json         provenance machine (GÉNÉRÉ)
│   └── README.md             README de provenance lisible (GÉNÉRÉ)
└── preuves/                  rapports et cartes de contrôle
```

> `SOURCES.md`, `donnees_brutes/README.md` et `manifest.json` sont **régénérés à
> chaque exécution** : ne pas les modifier à la main.

---

## 3. Prérequis (une seule fois)

1. Ouvrir **Anaconda Prompt** (pas l'invite de commandes Windows classique : `conda`
   et parfois `git` n'y sont pas reconnus).
2. Créer l'environnement (voir `GUIDE_INSTALLATION.md`) :
   ```
   conda env create -f environment.yml
   ```
3. Se placer dans le projet et activer l'environnement :
   ```
   cd C:\projet\Acces_soins_Region_Casablanca-Settat
   conda activate geodata-sante
   ```
   Si `conda activate` n'est pas reconnu :
   ```
   call C:\Users\pc\anaconda3-pbe\Scripts\activate.bat
   conda activate geodata-sante
   ```

---

## 4. Le lanceur `run_collecte.bat`

Contenu :

```bat
@echo off
REM Rejoue toute la phase 1 (collecte + contrôle) en une commande.
REM A lancer depuis Anaconda Prompt, dans le dossier du projet.
call conda activate geodata-sante
python scripts\collecte.py %*
python scripts\controle_collecte.py
```

Ce qu'il fait :

1. active l'environnement `geodata-sante` ;
2. lance `collecte.py` en lui **transmettant tous les arguments** reçus (`%*`) ;
3. lance ensuite `controle_collecte.py`, qui vérifie le résultat.

Le lanceur accepte donc les mêmes options que `collecte.py` :

```
run_collecte.bat                          tout, en réutilisant le cache
run_collecte.bat --etapes sante           une seule source, puis contrôle
run_collecte.bat --force                  tout retélécharger
run_collecte.bat --etapes routes --routes principal
```

Sous Linux / macOS : `./run_collecte.sh` avec les mêmes options.

Durée : 10 à 30 min la première fois (surtout `routes`), quelques secondes ensuite
grâce au cache.

---

## 5. `collecte.py` — options

| Option | Valeurs | Effet |
| --- | --- | --- |
| `--etapes` | une ou plusieurs parmi `limites sante routes worldpop hcp` | n'exécute que ces étapes (par défaut : toutes) |
| `--force` | — | retélécharge même si le fichier est déjà en cache |
| `--routes` | `complet` (défaut) ou `principal` | `principal` exclut les voies résidentielles : beaucoup plus léger si Overpass sature |

Les étapes s'exécutent toujours **dans l'ordre** `limites → sante → routes → worldpop
→ hcp`, quel que soit l'ordre tapé. Si une étape échoue, les suivantes continuent ;
l'échec est noté dans le manifeste (`"statut": "ECHEC"` + message d'erreur).

Aide intégrée : `python scripts\collecte.py --help`

---

## 6. Lancer une seule source pour tester

### Dépendance importante

`sante`, `routes` et `worldpop` découpent leurs données sur le **contour régional**
produit par `limites` (`donnees_brutes\limites\limites_casablanca_settat.gpkg`).
Il faut donc avoir réussi `limites` **au moins une fois** avant de les tester seules.
`hcp` est indépendante.

Sans contour, l'erreur est explicite :
`contour régional absent : lancez d'abord l'étape « limites »`.

### Commandes par source

| Objectif | Commande | Durée indicative |
| --- | --- | --- |
| Limites (à faire en premier) | `python scripts\collecte.py --etapes limites` | < 1 min |
| Établissements de santé | `python scripts\collecte.py --etapes sante` | 30 s à 2 min |
| Réseau routier complet | `python scripts\collecte.py --etapes routes` | plusieurs minutes à > 30 min |
| Réseau routier allégé | `python scripts\collecte.py --etapes routes --routes principal` | quelques minutes |
| Population WorldPop | `python scripts\collecte.py --etapes worldpop` | 1 à 5 min (téléchargement national) |
| Population légale HCP | `python scripts\collecte.py --etapes hcp` | < 1 min |
| Deux sources à la fois | `python scripts\collecte.py --etapes sante hcp` | — |

Ajouter `--force` pour **refaire réellement le téléchargement** au lieu de lire le
cache (exemple : `python scripts\collecte.py --etapes sante --force`).

Puis vérifier :

```
python scripts\controle_collecte.py
```

> Le contrôle examine **toutes** les couches : si certaines n'ont pas encore été
> collectées, il les signale « absente » et renvoie un code d'erreur. C'est normal
> pendant un test partiel ; regardez la ligne de la source testée.

### Test d'accès rapide

Pour vérifier seulement qu'une source **répond** (sans tout traiter), avec un
échantillon et un rapport dans `preuves/rapport_acces.md` :

```
python scripts\00_test_acces.py --sources osm
python scripts\00_test_acces.py --sources routes worldpop
python scripts\00_test_acces.py --sources limites --limites-zip donnees_brutes\limites\mar_admbnda_hcp_20230925_SHP.zip
python scripts\00_test_acces.py --sources hcp --hcp-pdf donnees_brutes\hcp\population_legale_rgph2024.pdf
```

Clés acceptées par `--sources` : `osm routes worldpop limites hcp` (attention : ici
c'est `osm`, pas `sante`). La carte de démo se produit ensuite avec
`python scripts\01_demo_carte.py` → `preuves\carte_demo.png`.

---

## 7. Détail de chaque étape

### `limites` — communes et contour régional
- Cherche un zip `*_SHP.zip` dans `donnees_brutes\limites\`. S'il n'y en a pas,
  interroge l'API HDX pour le télécharger.
- Lit la couche **ADM3** (communes), sélectionne la région par le nom de région
  (ADM1) **ou** par le nom de province (ADM2), d'après les 9 provinces de
  `PROVINCES_REGION` dans `config.py`. Cela fonctionne quel que soit le découpage
  régional (ancien ou 2015) inscrit dans les attributs.
- Reprojette en 26191, corrige les géométries (`make_valid`) et construit le contour
  régional par union des communes (tampon ±5 m pour refermer les interstices).
- **Secours** si aucun zip n'est disponible : contour régional geoBoundaries (OSM),
  **sans communes**, signalé comme dégradé dans le manifeste.
- Sortie : `limites_casablanca_settat.gpkg`, couches `region` et `communes`.
- À vérifier : la sortie annonce **9 provinces** (Casablanca, Mohammedia, Nouaceur,
  Médiouna, Berrechid, Benslimane, Settat, El Jadida, Sidi Bennour).

### `sante` — établissements de santé OSM
- Requête Overpass sur le rectangle de la région :
  `amenity = hospital | clinic | doctors | dentist | pharmacy` et tout objet `healthcare=*`
  (nœuds, chemins et relations, ramenés à leur centre).
- La requête exacte est enregistrée dans `osm_sante\requete.overpassql` (versionnée).
- Essaie les serveurs de `OVERPASS_URLS` dans l'ordre, deux fois chacun.
- Garde les tags utiles (nom fr/ar, amenity, healthcare, opérateur, lits, urgences,
  horaires…), reprojette en 26191 et **écarte ce qui est hors du vrai contour**.
- Sorties : `overpass_reponse.json` (brut) et `etablissements_sante.gpkg`.

### `routes` — réseau routier
- osmnx télécharge le réseau `drive` sur le polygone régional (~20 000 km²),
  découpé en **tuiles de 250 km²** (`ROUTES_TUILE_KM2`).
- Chaque tuile est mise en cache dans `osm_routes\cache_overpass\` : **une relance
  reprend là où la précédente s'est arrêtée** (inutile de tout recommencer après une
  coupure).
- Sorties : `routes_casablanca_settat.graphml` (graphe) et
  `routes_casablanca_settat.gpkg`, couches `troncons` et `noeuds` (en 26191).
- Colonnes gardées si elles existent : `u, v, key, osmid, highway, name, length,
  maxspeed, lanes, oneway` (`maxspeed` est souvent absent : ce n'est pas une erreur).

### `worldpop` — population 100 m
- Télécharge le raster national `mar_ppp_2020_constrained.tif` (ou réutilise celui
  déposé dans `donnees_brutes\worldpop\`).
- Découpe sur la région → copie en 4326, puis reprojette à 100 m en 26191 avec
  `Resampling.sum`, qui **conserve les effectifs**.
- La sortie affiche l'**écart de reprojection** : il doit être proche de 0 %.

### `hcp` — population légale RGPH 2024
- Cherche un PDF valide (commence par `%PDF-`) dans `donnees_brutes\hcp\`, sinon
  tente hcp.ma avec des en-têtes de navigateur.
- Extrait seulement les pages qui citent une province de la région :
  `pages_region_casablanca_settat.txt` et `tableaux_bruts_region.csv`.
- Import **brut** : la mise en forme et la jointure aux codes HCP des communes se
  font au pré-traitement.

---

## 8. Dépôts manuels acceptés

Deux serveurs bloquent parfois les scripts. C'est le **seul** cas où l'on dépose un
fichier à la main ; le script le détecte, l'indique dans le manifeste (« dépôt
manuel ») et calcule son SHA-256.

| Fichier | Où le télécharger | Où le déposer |
| --- | --- | --- |
| `mar_admbnda_hcp_20230925_SHP.zip` | page HDX « Morocco – Subnational Administrative Boundaries » | `donnees_brutes\limites\` |
| PDF population légale RGPH 2024 | hcp.ma (publication de la population légale) | `donnees_brutes\hcp\` |
| `mar_ppp_2020_constrained.tif` (facultatif) | data.worldpop.org | `donnees_brutes\worldpop\` |

Puis relancer l'étape concernée, par exemple `python scripts\collecte.py --etapes limites`.

---

## 9. Fichiers produits et preuves

| Fichier | Contenu |
| --- | --- |
| `donnees_brutes\manifest.json` | pour chaque source : statut, URL, mode, licence, dates, CRS d'origine et de sortie, fichiers avec taille et SHA-256, chiffres clés |
| `donnees_brutes\README.md` | la même provenance, lisible |
| `SOURCES.md` | tableau d'inventaire des sources |
| `preuves\controle_collecte.md` | pour chaque couche : CRS, nombre d'entités, géométries invalides, entités hors région, verdict ; « CRS uniforme : oui/non » |
| `preuves\carte_controle.png` | toutes les couches superposées en EPSG:26191 |

Points à vérifier dans le contrôle :
- **CRS uniforme : oui** ;
- 0 entité hors région ;
- les géométries invalides sont seulement comptées ici : leur correction tracée
  (`ST_MakeValid`, rapport avant/après) relève du pré-traitement.

---

## 10. Problèmes déjà rencontrés et solutions

| Symptôme | Cause | Solution appliquée |
| --- | --- | --- |
| `conda` ou `git` « n'est pas reconnu » | invite de commandes Windows classique | utiliser **Anaconda Prompt**, ou `call C:\Users\pc\anaconda3-pbe\Scripts\activate.bat` |
| `The EPSG code is unknown … DATABASE.LAYOUT.VERSION.MINOR` (WorldPop, rasterio) | l'installeur PostGIS impose son propre `PROJ_LIB`, plus ancien | corrigé dans `config.py` : `PROJ_DATA`, `PROJ_LIB` et `GDAL_DATA` pointent vers l'environnement conda ; **relancer `--etapes worldpop`** |
| Overpass `502 Bad Gateway` ou timeout | serveur principal saturé | miroirs essayés automatiquement (`OVERPASS_URLS`, kumi.systems en premier) ; relancer, ou `--routes principal` |
| `routes` interrompue en cours | coupure réseau / timeout | relancer `--etapes routes` : le cache par tuile reprend la progression |
| HDX renvoie 404 | identifiant de jeu changé ou blocage | dépôt manuel du zip (§8) |
| hcp.ma renvoie une page HTML au lieu du PDF | blocage des clients non navigateurs | dépôt manuel du PDF (§8) ; le script vérifie la signature `%PDF-` |
| `NameError: LICENCES` | ancienne version de `config.py` | remplacer `config.py` par la version à jour |
| `KeyError: maxspeed` | colonne absente des données osmnx | corrigé : seules les colonnes présentes sont gardées |
| Les corrections ne semblent pas appliquées | anciens scripts toujours en place | vérifier avec `findstr "PROJ_DATA" scripts\config.py` ; remplacer les fichiers du dossier `scripts\` |

