# Rapport avant / après nettoyage — Phase 2 (Séance 4)

- **Date d'exécution** : 2026-10-28 21:10 UTC
- **Script** : `scripts/nettoyage.py`
- **Mode** : **RAPPORT SEUL (`--dry-run`, aucune écriture)**
- **CRS unique** : `EPSG:26191` (Merchich / Nord Maroc, mètres)

## 1. Synthèse globale avant / après nettoyage

| Couche / Table cible | Entités brutes (avant) | Géométries invalides (avant → après) | Doublons supprimés | Hors emprise / boucles écartés | Entités propres (après) | Statut |
| --- | --- | --- | --- | --- | --- | --- |
| `province` (dissolution communes) | 153 communes | 0 → 0 | 0 | 0 interstices fermés | **9** | ✅ 100 % valide |
| `commune` + jointure HCP 2024 | 153 | 0 → 0 | 0 | 0 | **153** (153/153 HCP) | ✅ 100 % valide |
| `etablissement` (OSM santé) | 1737 | 0 → 0 | 8 (8 topo) | 146 hors région | **1583** | ✅ 100 % valide |
| `troncon` (réseau routier) | 130 783 | 0 → 0 | 0 | 196 boucles | **318 229** (53 867 km) | ✅ 100 % valide |
| `noeud` (intersections graphe) | — (non topologisé) | 0 → 0 | — | 532 en îlots isolés | **228 554** | ✅ 100 % valide |
| `maille_h3` (demande rés. 8) | 26 789 | 0 → 0 | 0 | 1 534 hors région | **25 255** (7 113 peuplés) | ✅ 100 % valide |

## 2. Cas réels de désaccord topologique traités

### Cas A — Doublons topologiques point / polygone dans OpenStreetMap (`etablissement`)
- **Problème observé** : Dans OpenStreetMap, de nombreux hôpitaux, cliniques et pharmacies sont cartographiés deux fois : une fois sous forme d'emprise de bâtiment (`way/*` ou `relation/*`) et une seconde fois sous forme de point (`node/*`) placé à l'entrée ou au centre du bâtiment (à moins de 35 mètres).
- **Correction automatique** : Recherche spatiale par arbre KD (`cKDTree`, rayon $\le 35\text{ m}$) entre entités de même `code_type` partageant le même nom normalisé ou superposant un `node` et un `way/relation`. Les attributs (`nom`, `secteur`, `nb_lits`, `urgences`) sont fusionnés vers l'entité principale avant suppression du doublon.
- **Bilan** : **8 doublons topologiques** fusionnés et éliminés.
- **Exemples tracés** :
  - `way/1228709573` & `node/8443590471` (pharmacie, « Shérif », d = 7.6 m)
  - `way/1239621024` & `node/8446084011` (pharmacie, « Al Fath », d = 2.7 m)
  - `way/597845040` & `node/8443939484` (pharmacie, « Pharmacie Essaada », d = 9.2 m)
  - `way/414875894` & `node/2714951128` (dentiste, « clinique dentaire casablanca (cdc) », d = 1.9 m)
  - `way/424323318` & `node/4057991325` (hopital, « Hôpital Sidi Othmane », d = 21.9 m)
  - `node/4563362579` & `node/8483143887` (pharmacie, « Pharmacie Al Qods », d = 19.1 m)
  - `node/5234584424` & `node/5282223224` (clinique, « Avicenne », d = 16.0 m)
  - `node/5688271125` & `node/8446095434` (pharmacie, « Pharmacie El Breija صيدلية البريجة », d = 14.7 m)

### Cas B — Topologie du graphe routier : boucles, sens uniques inverses et îlots déconnectés (`troncon`, `noeud`)
- **Boucles dégénérées (`noeud_depart = noeud_arrivee`)** : **196 tronçons** formaient une boucle fermée sur un même nœud (ronds-points non découpés ou impasses circulaires) et auraient violé la contrainte d'intégrité `CHECK (noeud_depart <> noeud_arrivee)` du schéma PostGIS. Ils ont été détectés et écartés.
- **Sens uniques inversés (`oneway = '-1'`)** : **0 tronçons** avaient un sens de parcours opposé au sens de numérisation de la `LineString`. Leurs géométries et leurs clés (`noeud_depart`, `noeud_arrivee`) ont été inversées pour que le graphe orienté soit directement exploitable en séance 5.
- **Îlots routiers déconnectés** : L'analyse en composantes connexes (`networkx`) a identifié **91 micro-îlots isolés** (532 nœuds, ex. allées de parkings fermés ou pistes coupées au bord de la région). L'accrochage (`ACCROCHER` et `RACCORDER`) est restreint à la composante connexe principale afin qu'aucun établissement ni hexagone H3 ne soit piégé dans un cul-de-sac déconnecté.

### Cas C — Fermeture topologique des limites administratives (`commune` → `province`)
- **Problème observé** : L'assemblage des anneaux OSM des 153 communes présentait `0` auto-intersections mineures corrigées par `ST_MakeValid`, ainsi que de micro-interstices aux limites inter-communales lors de la dissolution en 9 provinces/préfectures.
- **Correction automatique** : Application d'une fermeture morphologique (`ST_Buffer(+5 m)` puis `ST_Buffer(-5 m)` + `ST_MakeValid`) lors de l'agrégation en `province`, produisant 9 `MultiPolygon` parfaitement jointifs.

## 3. Normalisation sémantique et relecture métier des établissements

- **Répartition par `code_type` après nettoyage** :
  - `pharmacie` : **1255** établissements
  - `clinique` : **87** établissements
  - `autre` : **61** établissements
  - `dentiste` : **61** établissements
  - `medecin` : **58** établissements
  - `hopital` : **54** établissements
  - `centre_sante` : **7** établissements
- **Répartition par `code_niveau` de soin** :
  - Niveau `1` : **1442** établissements
  - Niveau `2` : **136** établissements
  - Niveau `3` : **5** établissements
- **Relecture métier (`niveau_source = 'relecture'`)** : **5 établissements hospitaliers** ont été reclassés du niveau 2 (défaut du type `hopital`) vers le **niveau 3 (CHU / hôpital régional ou universitaire)**.

## 4. Contrôle de cohérence des populations (RGPH 2024 vs WorldPop 2020 H3)

- **Population légale RGPH 2024 (153 communes HCP)** : **7 688 967 habitants**
- **Population WorldPop 2020 agrégée sur les 25 255 hexagones H3** : **7 386 415 habitants**
- **Distance médiane d'accrochage au réseau routier** : **22.4 m** pour les établissements, **339.8 m** pour le centre des mailles H3.
