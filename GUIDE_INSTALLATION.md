# Guide d'installation — environnement et données

**Projet :** Accès aux soins dans la région Casablanca-Settat
**But de ce guide :** installer l'environnement, télécharger les 5 sources, produire les
preuves d'accès exigées par la checklist Go/No-Go (§1.2), et préparer les démos de la séance 2.

Temps estimé : 1 h à 1 h 30 la première fois (dont ~20 min de téléchargements).

---

## Étape 0 — Logiciels à installer (une seule fois)

| Logiciel | Pourquoi | Lien |
|---|---|---|
| **Git** | dépôt partagé du groupe | git-scm.com |
| **Miniconda** (recommandé) | installe GDAL/PROJ sans conflit, surtout sous Windows | docs.conda.io/en/latest/miniconda.html |
| **QGIS 3.x LTR** | vérification visuelle des couches (capture exigée en séance 3) | qgis.org |
| **Docker Desktop** *(pas urgent)* | PostGIS en conteneur, utile dès l'intersession 3 | docker.com |

> Sous Windows, évitez `pip install geopandas rasterio` avec un Python « nu » : c'est la
> première cause de blocage (GDAL). Passez par conda.

---

## Étape 1 — Récupérer le projet

```bash
# Créez votre propre dépôt (GitHub/GitLab), puis :
git clone <url-de-votre-depot> projet_sante
cd projet_sante
# copiez-y les fichiers fournis : scripts/, environment.yml, requirements.txt,
# GUIDE_INSTALLATION.md, SOURCES.md
```

Arborescence attendue après les étapes suivantes :

```
projet_sante/
├── scripts/
│   ├── config.py              # emprise, URLs, CRS, licences (un seul endroit à modifier)
│   ├── 00_test_acces.py       # preuves d'accès aux 5 sources
│   └── 01_demo_carte.py       # superposition + aperçu par commune
├── donnees_brutes/            # créé automatiquement (fichiers nationaux téléchargés)
│   ├── worldpop/  limites/  hcp/
├── preuves/                   # créé automatiquement — c'est ce que vous montrez en séance 2
├── environment.yml  requirements.txt
├── SOURCES.md  GUIDE_INSTALLATION.md
```

---

## Étape 2 — Créer l'environnement Python

```bash
conda env create -f environment.yml
conda activate geodata-sante
```

Vérification (doit afficher les versions sans erreur) :

```bash
python -c "import geopandas, rasterio, osmnx, pdfplumber; print('OK', geopandas.__version__, osmnx.__version__)"
gdalinfo --version
```

*Sans conda (Linux/macOS)* : `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

---

## Étape 3 — Lancer les tests d'accès (la preuve exigée)

```bash
python scripts/00_test_acces.py
```

Ce que fait le script, source par source :

| # | Source | Ce qui est téléchargé | Durée typique |
|---|---|---|---|
| 1 | **OSM — établissements de santé** (Overpass) | hôpitaux, cliniques, médecins, dentistes, pharmacies + tag `healthcare` sur l'emprise | 30 s – 3 min |
| 2 | **OSM — réseau routier** (osmnx) | extrait de démonstration : 3 km autour de Berrechid | < 1 min |
| 3 | **WorldPop 2020 « constrained » 100 m** | raster national (~14 Mo), découpé sur l'emprise | 1 – 5 min |
| 4 | **HCP — limites communales** (COD-AB sur HDX) | archive SHP (~34 Mo), couche ADM3 filtrée sur Casablanca-Settat | 1 – 5 min |
| 5 | **HCP — population légale RGPH 2024** | PDF officiel, pages contenant « Casablanca » repérées | < 1 min |

À la fin, ouvrez **`preuves/rapport_acces.md`** : tableau des statuts, URL réellement
utilisée, horodatage, nombre d'entités, CRS, taille et **empreinte SHA-256** de chaque
échantillon. C'est votre preuve d'accès « requête exécutée + échantillon téléchargé ».

Relancer une seule source (le rapport est complété, pas écrasé) :

```bash
python scripts/00_test_acces.py --sources osm
python scripts/00_test_acces.py --sources worldpop limites
```

### Si une source échoue — c'est normal, voici quoi faire

**Overpass (OSM) : erreur 429 ou 504**
Le serveur public est saturé. Attendez 2 minutes et relancez `--sources osm`
(le script essaie déjà automatiquement un 2ᵉ serveur miroir).

**Limites HCP : « Téléchargement automatique impossible »**
HDX bloque parfois les requêtes automatiques. Téléchargement manuel :
1. Ouvrez https://data.humdata.org/dataset/morocco-administrative-boundaries-populated-places
2. Téléchargez **`mar_admbnda_hcp_20230925_SHP.zip`** (≈ 34 Mo)
3. Placez-le dans `donnees_brutes/limites/` puis :
   ```bash
   python scripts/00_test_acces.py --sources limites --limites-zip donnees_brutes/limites/mar_admbnda_hcp_20230925_SHP.zip
   ```

**HCP population : « Le fichier reçu n'est pas un PDF »**
Le lien a pu changer. Sur **hcp.ma**, cherchez « Population légale … RGPH 2024 »
(document listant régions, provinces, préfectures et communes), téléchargez le PDF puis :
```bash
python scripts/00_test_acces.py --sources hcp --hcp-pdf chemin/vers/le_fichier.pdf
```
Sources alternatives à citer : la plateforme interactive https://resultats2024.rgphapps.ma
et les *fiches communales RGPH 2024 de la région Casablanca-Settat* publiées par la
Direction régionale du HCP.

**Erreur réseau / proxy à l'école**
Testez depuis une autre connexion (partage 4G). Notez-le dans le rapport : c'est une
contrainte réelle d'accès, utile pour l'audit.

---

## Étape 4 — Produire la carte de démonstration

```bash
python scripts/01_demo_carte.py
```

Sorties :
- `preuves/carte_demo.png` — population WorldPop en fond, limites communales, établissements par type
- `preuves/apercu_communes.csv` — par commune : population WorldPop, nb d'établissements,
  établissements pour 10 000 habitants, triées des moins dotées aux mieux dotées

> ⚠️ Cet aperçu est un **indicateur brut** (distance à vol d'oiseau ignorée, OSM non
> contrôlé). Présentez-le comme une première lecture, pas comme un résultat.

---

## Étape 5 — Vérifier dans QGIS (et faire les captures)

1. Ouvrez QGIS, glissez-déposez : `preuves/communes_casablanca_settat.geojson`,
   `preuves/osm_sante_echantillon.geojson`, `preuves/worldpop_casablanca_settat.tif`,
   `preuves/osm_routes_demo.gpkg`.
2. Vérifiez le CRS de chaque couche (clic droit → Propriétés → Information) : EPSG:4326.
3. Projet → Propriétés → SCR : passez à **EPSG:26191** pour mesurer des distances en mètres.
4. Capture d'écran → `preuves/capture_qgis.png`.

---

## Étape 6 — Ce qu'il faut versionner

- ✅ À committer : `scripts/`, `preuves/rapport_acces.md` et `.json`, `preuves/*.png`,
  les **échantillons** légers (`*.geojson` régionaux), `SOURCES.md`.
- ❌ À ne pas committer : `donnees_brutes/` volumineux (rasters nationaux, archive SHP).
  Ajoutez-le au `.gitignore` : le script les retélécharge, et le SHA-256 du rapport
  prouve que c'est le même fichier.

```bash
echo "donnees_brutes/" >> .gitignore
```

---

## Points d'audit à mentionner en séance 2

Ce sont des résultats d'audit à part entière (le dossier valorise le fait de les détecter) :

1. **Grille de population du projet de référence = synthétique.** Le pipeline
   `marouane-ouaomar/morocco-healthcare-optimization` génère une grille fictive
   (gaussiennes centrées sur des villes) lorsqu'aucun raster WorldPop n'est fourni,
   ce qui est le cas par défaut. → On repart du vrai raster WorldPop.
2. **Population communale officielle seulement en PDF.** Le jeu HDX « COD-PS » pour le
   Maroc date de 2014 et ne couvre que 31 provinces sur 69 → inutilisable. La population
   légale 2024 par commune n'existe qu'en PDF HCP → extraction de tableaux en intersession 2.
3. **Écarts de nomenclature à vérifier** : la couche HDX annonce 10 entités ADM1
   (le Maroc compte 12 régions) et 1 507 entités ADM3, alors que le RGPH 2024 compte
   1 503 communes. → À expliquer avant la jointure population ↔ limites.
4. **Distances à vol d'oiseau** dans le projet de référence → on passera au temps de
   trajet sur le réseau routier.

---

## Checklist avant la séance 2

- [ ] `preuves/rapport_acces.md` avec au moins **2 sources ✅** (idéalement les 5)
- [ ] `preuves/carte_demo.png` + `preuves/capture_qgis.png`
- [ ] `SOURCES.md` complété (dates réelles de téléchargement)
- [ ] Thème déclaré sur le document partagé de la promotion
- [ ] Document de 1er jet (2-3 pages) déposé
- [ ] Démo répétée une fois en conditions réelles (connexion de la salle !)
- [ ] Plan B : rapport et carte déjà générés, au cas où le réseau tombe pendant la démo
