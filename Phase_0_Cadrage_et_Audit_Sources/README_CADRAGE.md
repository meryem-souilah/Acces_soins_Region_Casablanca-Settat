# Cadrage du projet — README

Projet **Géodata appliquée** · Accès aux soins, région Casablanca-Settat
Groupe de 5 étudiants ingénieurs

Ce document fixe le cadre de tout le projet : la question à laquelle on répond, le
territoire, les choix structurants (unité d'analyse, CRS, niveaux de soin), les sources
retenues, la méthode générale et l'outillage. Les phases suivantes (collecte,
pré-traitement, accessibilité, analyse) s'appuient sur ces décisions.

---

## 1. Le défi

> **Où implanter quel type d'offre de soins dans la région Casablanca-Settat pour
> maximiser la population couverte dans le temps d'accès adapté à chaque niveau ?**

Trois mots de la question orientent tout le projet :

| Terme | Ce qu'il impose |
| --- | --- |
| **quel type d'offre** | on ne cherche pas seulement *où* ajouter un établissement, mais *de quel niveau* : un centre de santé de proximité et un hôpital de référence ne répondent pas au même besoin |
| **population couverte** | il faut connaître finement où vivent les habitants, pas seulement le total par commune |
| **temps d'accès adapté à chaque niveau** | la distance à vol d'oiseau ne suffit pas : on mesure un temps de trajet sur le réseau routier, et le seuil acceptable dépend du niveau de soin |

**Livrable attendu à la fin du projet** : pour chaque niveau de soin, la carte des zones
non couvertes dans le temps d'accès fixé, et des propositions de sites d'implantation
classées selon la population supplémentaire couverte.

---

## 2. Le territoire

- **Région Casablanca-Settat** (découpage régional de 2015), environ 20 000 km².
- **9 provinces et préfectures** : Casablanca, Mohammedia, Nouaceur, Médiouna,
  Berrechid, Benslimane, Settat, El Jadida, Sidi Bennour.
- Un territoire très contrasté : la métropole de Casablanca, dense et bien équipée, et
  de vastes espaces ruraux (Settat, Sidi Bennour, Benslimane) où l'accès dépend
  fortement du réseau routier. C'est ce contraste qui rend la question intéressante.
- **Emprise de travail** : rectangle englobant pour les requêtes
  (lat. 31,90 → 33,95 ; lon. −9,40 → −6,40), puis découpage exact sur le contour
  régional issu des limites HCP.

---

## 3. Les niveaux de soin

L'offre est classée en trois niveaux, qui correspondent à la filière de soins :

| Niveau | Libellé | Exemples |
| --- | --- | --- |
| 1 | Soins de proximité (premier recours) | centres de santé, dispensaires, cabinets médicaux |
| 2 | Hôpital de référence | hôpitaux provinciaux et préfectoraux, cliniques |
| 3 | Hôpital régional ou CHU | CHU Ibn Rochd, hôpital régional |

**Règles de cadrage :**

- **Couverture stricte** : un établissement ne couvre que son propre niveau. Un CHU ne
  couvre pas le besoin de proximité. Cela respecte la filière de soins et évite qu'un
  grand hôpital urbain masque un manque de soins de premier recours. L'hypothèse
  inverse sera testée comme scénario de comparaison.
- **Seuils d'accès** : un seuil de temps est attaché à chaque niveau. Tant qu'aucune
  norme officielle n'est sourcée, on raisonne en **scénarios** (15, 30 et 45 minutes)
  plutôt que d'inventer un chiffre.
- **Hors périmètre** : pharmacies et cabinets dentaires sont collectés mais exclus du
  calcul, car ils ne relèvent pas du premier recours au sens de l'étude.

---

## 4. Choix structurants

| Choix | Décision | Justification |
| --- | --- | --- |
| Unité d'analyse de la demande | **grille hexagonale H3, résolution 8** (≈ 0,74 km² par hexagone) | maille régulière : évite les biais de communes de tailles très différentes ; fine en ville, raisonnable à l'échelle régionale ; voisinages homogènes |
| Système de coordonnées | **EPSG:26191 (Merchich / Nord Maroc)**, unique pour toutes les couches | projection métrique adaptée au nord du Maroc : distances et surfaces en mètres sans déformation gênante ; les données sont échangées en EPSG:4326 puis reprojetées |
| Mesure de l'accès | **temps de trajet sur le réseau routier** | plus réaliste que la distance euclidienne, surtout en zone rurale |
| Échelles de restitution | commune et province | ce sont les échelles où se prennent les décisions d'implantation |
| Paramètres d'analyse | **stockés comme données** (seuils, population cible, source de la norme) | modifiables et traçables sans toucher au code ; chaque chiffre est rattaché à sa source |

---

## 5. Les sources retenues

| Besoin | Source | Producteur | Licence | Pourquoi celle-ci |
| --- | --- | --- | --- | --- |
| Offre de soins | OpenStreetMap (API Overpass) | contributeurs OSM | ODbL 1.0 | seule source ouverte, géolocalisée et à jour couvrant toute la région |
| Réseau routier | OpenStreetMap (osmnx) | contributeurs OSM | ODbL 1.0 | graphe routable directement exploitable pour les temps de trajet |
| Population fine | WorldPop 2020, 100 m, *constrained* | WorldPop (Univ. Southampton) | CC BY 4.0 | population répartie sur les seuls bâtiments : agrégeable sur les hexagones H3 |
| Limites administratives | communes (ADM3) HCP via OCHA/HDX | HCP / OCHA | à vérifier sur la page HDX | découpage officiel, avec les codes communaux |
| Population légale | RGPH 2024 | HCP | réutilisation avec citation | chiffre officiel le plus récent, sert à contrôler WorldPop |

Chaque source est documentée lors de la collecte (URL, date, licence, empreinte
SHA-256) dans `SOURCES.md` et `donnees_brutes/README.md`.

---

## 6. Limites connues dès le départ

- **OSM ne connaît pas les niveaux de soin marocains** : un CHU et un hôpital provincial
  portent le même tag `amenity=hospital`. Un niveau par défaut est attribué par type,
  puis les hôpitaux sont relus à la main.
- **Complétude d'OSM inégale** : meilleure en ville qu'en zone rurale, et les attributs
  (secteur, lits, urgences) sont souvent vides.
- **WorldPop date de 2020** : on le recale sur la population légale 2024 par commune.
- **Analyse normative, pas descriptive** : le modèle mesure l'accès conforme à
  l'organisation des soins, pas l'usage réel (beaucoup d'habitants vont directement aux
  urgences des CHU).
- **Vitesses sur le réseau** : la vitesse maximale est rarement renseignée dans OSM ;
  des vitesses par défaut selon le type de voie seront appliquées et documentées.

---

## 7. Méthode générale

```
1. Cadrage         question, territoire, niveaux, CRS, sources       (ce document)
2. Collecte        téléchargement reproductible, CRS unique, provenance
3. Pré-traitement  nettoyage, typage OSM → niveau, géodatabase PostGIS
4. Accessibilité   temps d'accès de chaque hexagone à chaque niveau de soin
5. Analyse         zones non couvertes, sites candidats, population gagnée
6. Restitution     cartes, recommandations, limites
```

Chaque étape produit des fichiers vérifiables et peut être rejouée par script.

---

## 8. Outillage

| Outil | Usage |
| --- | --- |
| Anaconda, environnement `geodata-sante` (`environment.yml`) | Python 3.11 avec GDAL, geopandas, rasterio, shapely, pyproj, osmnx, pdfplumber |
| PostgreSQL 16 + PostGIS 3.4 | géodatabase du projet (schéma `sante`) |
| QGIS 3.x LTR | vérification visuelle des couches |
| draw.io | modèles de données (MCD, MLD) |
| Git / GitHub | dépôt partagé : `meryem-souilah/Acces_soins_Region_Casablanca-Settat` |

Installation détaillée : `GUIDE_INSTALLATION.md`.

---

## 9. Organisation du dépôt

```
Acces_soins_Region_Casablanca-Settat/
├── README_CADRAGE.md        ce document
├── README_COLLECTE.md       phase de collecte
├── GUIDE_INSTALLATION.md    installation de l'environnement
├── SOURCES.md               inventaire des sources (généré)
├── environment.yml          environnement conda
├── requirements.txt         équivalent pip
├── run_collecte.bat / .sh   lanceurs de la collecte
├── scripts/                 config.py (tous les paramètres) et scripts Python
├── sql/                     schéma de la géodatabase PostGIS
├── donnees_brutes/          données téléchargées (non versionnées si lourdes)
└── preuves/                 rapports de contrôle et cartes
```

Tous les paramètres (emprise, CRS, URL des sources, liste des provinces) sont
centralisés dans `scripts/config.py` : un seul endroit à modifier si une source change.
