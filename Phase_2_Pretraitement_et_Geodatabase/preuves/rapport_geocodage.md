# Rapport de géocodage des établissements de soins de santé primaires

Exécuté le 2026-11-18 15:28 UTC par `scripts/geocodage_essp.py`. Requêtes Nominatim envoyées : 0 (les autres réponses viennent du cache).

## Rattachement aux communes HCP

| Méthode | Établissements |
| --- | --- |
| nom identique | 257 |
| arrondissement de Casablanca | 119 |
| nom proche | 21 |
| correction manuelle | 7 |

## Origine des positions

| precision_geom | Établissements | Signification |
| --- | --- | --- |
| geocodage_etablissement | 66 | Nominatim a trouvé l'établissement lui-même |
| geocodage_lieu | 123 | douar ou quartier qui porte ce nom, dans la bonne commune : Nominatim (109) ou rapprochement avec les lieux OSM (14) |
| manuel | 122 | position saisie à la main (corrections/positions_essp*.csv), vérifiée dans la commune |
| approx_commune | 93 | **approximative** : centre de la population de la commune (hexagones H3 pondérés par WorldPop) |
| non_trouve | 0 | sans position |

Établissements de l'analyse sans position précise (sans position ou `approx_commune`) : 81, listés dans `corrections/a_positionner_essp.csv` ; une saisie manuelle valide remplace la position approchée (les 31 centres spécialisés et laboratoires ne sont pas listés).

**Limite** : une position `approx_commune` peut être à plusieurs kilomètres du vrai centre dans les grandes communes rurales. Elle évite de compter comme non desservie la population d'un centre qui existe ; l'analyse d'accessibilité doit être testée avec et sans ces positions.

**Rapprochements avec les lieux OSM** (seuil de ressemblance 0.88, lieu dans la commune, rapprochements ambigus refusés)

| id_source | Nom (Ministère) | Lieu OSM | Type | Score |
| --- | --- | --- | --- | --- |
| msps2022/1579 | Cherrat (Sidi Khdim) | Cherrat ⵛⵕⵕⴰⵟ الشراط | village | 1.0 |
| msps2022/1581 | Sidi Bettach | Sidi Bettache ⵙⵉⴷⵉ ⴱⵟⵟⴰⵛ سيدي بطاش | village | 0.96 |
| msps2022/1598 | Ghnimyine | Laghnimyine ⵍⵖⵏⵉⵎⵢⵢⵉⵏ الغليميين | village | 0.9 |
| msps2022/1646 | Ouled Hcine | Oulad Hcine ⵡⵍⴰⴷ ⵃⵙⵉⵏ أولاد حسين | village | 1.0 |
| msps2022/1650 | Ouled Hamdane | Oulad Hamdane ⵡⵍⴰⴷ ⵃⵎⴷⴰⵏ أولاد حمدان | village | 1.0 |
| msps2022/1664 | Tagourate | Douar Tagourant ⴷⵓⴰⵔ ⵜⴰⴳⵓⵔⴰⵏⵜ دوار تاكورانت | village | 0.89 |
| msps2022/1666 | El Jadida-CRSR | El Jadida ⵊⴷⵉⴷⴰ الجديدة | city | 1.0 |
| msps2022/1667 | Ouled Ghadbane | Oulad Ghadbane ⵡⵍⴰⴷ ⵖⴹⴱⴰⵏ أولاد الغضبان | village | 1.0 |
| msps2022/1716 | My Thami (Ouled Azzouz) | Oulad Azzouz ⵡⵍⴰⴷ ⵄⵣⵓⵣ أولاد عزوز | village | 1.0 |
| msps2022/1755 | Mechraa B. Abbou | Machraa Ben Abbou مشرع بن عبو | village | 0.94 |
| msps2022/1774 | Ouled M'hammed | Oulad M'Hamed ⵡⵍⴰⴷ ⵎⵃⴰⵎⴷ أولاد امحمد | village | 0.96 |
| msps2022/1823 | Od Boussaken(Od Nacer) | Oulad Boussaken ⵡⵍⴰⴷ ⴱⵓⵙⴰⴽⵏ أولاد بوساكن | village | 1.0 |
| msps2022/1834 | Koudiat B.Dghough | Koudiat Bni Dghough ⴽⵯⴷⵢⵜ ⴱⵏⵉ ⴷⵖⵓⵖ كدية بني دغوغ | village | 0.97 |
| msps2022/1835 | Tamda(S.Abdellah) | Tamda ⵜⴰⵎⴷⴰ تامدة | village | 1.0 |

Points à plus de 500 m de leur commune déclarée : 0 (attendu : 0).

Points juste hors de leur commune, dans la bande de tolérance de 500 m : 6. Ils sont acceptés : la limite communale et le géocodage ont chacun une imprécision de quelques centaines de mètres.

| id_source | Nom | Distance à la commune (m) |
| --- | --- | --- |
| msps2022/1576 | MOUALINE EL GHABA | 261.2 |
| msps2022/1688 | Bni Yakhlef | 339.1 |
| msps2022/1690 | S.Moussa Ben Ali | 106.4 |
| msps2022/1712 | Lemkansa-Sud | 388.3 |
| msps2022/1797 | Ouled  Hajjaj | 398.1 |
| msps2022/1961 | Lahraouine 2 | 75.1 |

## Positions manuelles refusées

88 positions saisies à la main tombent à plus de 500 m de leur commune déclarée : elles ne sont PAS appliquées. Détail (commune où tombe réellement le point) dans `corrections/positions_rejetees_essp.csv`.

| Fichier | Saisies | Acceptées | Refusées |
| --- | --- | --- | --- |
| positions_essp_lot1.csv | 49 | 14 | 35 |
| positions_essp_lot2.csv | 40 | 39 | 1 |
| positions_essp_lot3.csv | 46 | 39 | 7 |
| positions_essp_lot4.csv | 40 | 13 | 27 |
| positions_essp_lot5.csv | 35 | 17 | 18 |

| Où tombe le point refusé | Nombre |
| --- | --- |
| Casablanca | 34 |
| HORS RÉGION | 15 |
| Bouskoura | 5 |
| Oulad Azzouz | 5 |
| Oulad Salah | 3 |
| Sidi Mohammed Ben Rahal | 2 |
| Sidi Moussa Ben Ali | 2 |
| Méchouar de Casablanca | 2 |

## Par province

| Code | Total | Positionnés |
| --- | --- | --- |
| 06.111 | 27 | 27 |
| 06.117 | 36 | 36 |
| 06.141 | 120 | 120 |
| 06.181 | 44 | 44 |
| 06.355 | 12 | 12 |
| 06.371 | 21 | 21 |
| 06.385 | 22 | 22 |
| 06.461 | 89 | 89 |
| 06.467 | 33 | 33 |

