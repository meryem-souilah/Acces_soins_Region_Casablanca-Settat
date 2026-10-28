# Résultats d'import PostGIS, tests de contraintes et requêtes métier (Séance 4)

- **Date d'exécution** : 2026-10-28 20:03 UTC
- **Base de données** : PostgreSQL 16 / PostGIS 3.5 (`acces_soins`, schéma `sante`, CRS `EPSG:26191`)
- **Sauvegarde restaurable** : `sql/acces_soins.backup` (42.13 Mo, testé avec `pg_restore` : 1583 établ., 25255 mailles H3, 318229 tronçons)

## 1. Effectifs des 8 tables du schéma `sante`

| Table | Rôle | Lignes chargées | Géométrie / SRID | Index GIST / B-tree |
| --- | --- | --- | --- | --- |
| `sante.province` | Décision | **9** | `MultiPolygon, 26191` | `province_geom_gist` |
| `sante.commune` | Décision | **153** | `MultiPolygon, 26191` | `commune_geom_gist`, `commune_code_province_idx` |
| `sante.niveau_soin` | Offre | **3** | — (référentiel) | PK `code_niveau` |
| `sante.type_etablissement` | Offre | **7** | — (référentiel) | `type_niveau_idx` |
| `sante.etablissement` | Offre | **1 583** | `Point  26191` | `etablissement_geom_gist` + 4 index FK |
| `sante.maille_h3` | Demande | **25 255** | `Polygon  26191` | `maille_h3_geom_gist` + 2 index FK |
| `sante.noeud` | Accès | **228 554** | `Point  26191` | `noeud_geom_gist` |
| `sante.troncon` | Accès | **318 229** | `LineString  26191` | `troncon_geom_gist` + 2 index FK |

## 2. Démonstration des contraintes d'intégrité (rejets automatiques)

| Test d'intégrité | Résultat PostgreSQL / PostGIS |
| --- | --- |
| Insertion d'un établissement dans une commune inexistante (violation FK `etablissement_code_hcp_fkey`) | REJETÉ COMME ATTENDU : `ERREUR:  une instruction insert ou update sur la table « etablissement » viole la contrainte de clé` |
| Insertion d'une géométrie en EPSG:4326 au lieu de EPSG:26191 (violation SRID) | REJETÉ COMME ATTENDU : `ERREUR:  Geometry SRID (4326) does not match column SRID (26191)` |
| Suppression d'une commune possédant des établissements (violation `ON DELETE RESTRICT`) | REJETÉ COMME ATTENDU : `ERREUR:  UPDATE ou DELETE sur la table « commune » viole la contrainte de clé étrangère « etablissement_code_hcp_fkey » de la table « etablissement »` |
| Insertion d'un tronçon bouclant sur le même nœud (violation `CHECK (noeud_depart <> noeud_arrivee)`) | REJETÉ COMME ATTENDU : `ERREUR:  la nouvelle ligne de la relation « troncon » viole la contrainte de vérification « troncon_noeuds_distincts »` |

## 3. Sortie complète des 3 requêtes spatiales métier et plans `EXPLAIN (ANALYZE, BUFFERS)`

```text
-- ============================================================================
-- requetes.sql — Trois requêtes spatiales métier pour la séance 4 & la séance 5
-- Projet : Accès aux soins dans la région Casablanca-Settat (EPSG:26191)
--
-- Exécution :
--   psql -h 127.0.0.1 -U postgres -d acces_soins -f sql/requetes.sql
--
-- Chaque requête est accompagnée de son commentaire métier et d'une analyse
-- de son plan d'exécution (EXPLAIN ANALYZE) démontrant l'utilisation des
-- index spatiaux GIST et des index B-tree sur clés étrangères.
-- ============================================================================
SET search_path = sante, public;
SET
-- ============================================================================
-- REQUÊTE 1 : Diagnostic territorial de l'offre de soins par commune et niveau
-- ----------------------------------------------------------------------------
-- Objectif métier (préparation Séance 5) :
--   Croiser la demande officielle (population RGPH 2024 des 153 communes) avec
--   l'offre de soins active (inclus_analyse = true) ventilée par niveau de la
--   filière (niveau 1 : proximité, niveau 2 : référence provinciale, niveau 3 :
--   CHU régional), tout en calculant la surface en km² via PostGIS (ST_Area).
--   Cette requête identifie immédiatement les communes rurales les plus peuplées
--   dépourvues d'offre de premier et second recours.
-- ============================================================================
SELECT
    p.nom                                                        AS province,
    c.code_hcp,
    c.nom                                                        AS commune,
    c.pop_2024,
    ROUND((ST_Area(c.geom) / 1e6)::numeric, 2)                   AS surface_km2,
    ROUND((c.pop_2024 / NULLIF(ST_Area(c.geom) / 1e6, 0))::numeric, 1) AS densite_hab_km2,
    COUNT(e.id_etab) FILTER (WHERE t.inclus_analyse AND e.code_niveau = 1) AS nb_niveau_1_proximite,
    COUNT(e.id_etab) FILTER (WHERE t.inclus_analyse AND e.code_niveau = 2) AS nb_niveau_2_reference,
    COUNT(e.id_etab) FILTER (WHERE t.inclus_analyse AND e.code_niveau = 3) AS nb_niveau_3_chu,
    COUNT(e.id_etab) FILTER (WHERE NOT t.inclus_analyse)                   AS nb_hors_analyse_pharma_dent
FROM sante.commune c
JOIN sante.province p
    ON p.code_province = c.code_province
LEFT JOIN sante.etablissement e
    ON ST_Within(e.geom, c.geom)
LEFT JOIN sante.type_etablissement t
    ON t.code_type = e.code_type
GROUP BY p.nom, c.code_hcp, c.nom, c.pop_2024, c.geom
ORDER BY
    (COUNT(e.id_etab) FILTER (WHERE t.inclus_analyse)) ASC,
    c.pop_2024 DESC NULLS LAST
LIMIT 20;
   province   |   code_hcp   |         commune         | pop_2024 | surface_km2 | densite_hab_km2 | nb_niveau_1_proximite | nb_niveau_2_reference | nb_niveau_3_chu | nb_hors_analyse_pharma_dent 
--------------+--------------+-------------------------+----------+-------------+-----------------+-----------------------+-----------------------+-----------------+-----------------------------
 Mohammadia   | 06.371.01.05 | Bni Yakhlef             |   117653 |       59.15 |          1989.0 |                     0 |                     0 |               0 |                           8
 Mohammadia   | 06.371.01.07 | Chellalate              |    98015 |       49.49 |          1980.6 |                     0 |                     0 |               0 |                           2
 Berrechid    | 06.117.01.05 | Deroua                  |    96619 |       13.75 |          7024.3 |                     0 |                     0 |               0 |                          35
 Médiouna     | 06.355.01.07 | El Majjatia Ouled Taleb |    95457 |       88.13 |          1083.2 |                     0 |                     0 |               0 |                           5
 Médiouna     | 06.355.01.01 | Lahraouyine             |    87977 |       16.45 |          5347.5 |                     0 |                     0 |               0 |                           1
 Nouaceur     | 06.385.01.07 | Oulad Azzouz            |    81048 |       71.27 |          1137.2 |                     0 |                     0 |               0 |                           1
 Médiouna     | 06.355.01.09 | Sidi Hajjaj Oued Hassar |    76362 |      107.34 |           711.4 |                     0 |                     0 |               0 |                           3
 Berrechid    | 06.117.01.09 | Had Soualem             |    74762 |       17.70 |          4224.1 |                     0 |                     0 |               0 |                          26
 Benslimane   | 06.111.01.03 | Bouznika                |    55722 |      110.59 |           503.9 |                     0 |                     0 |               0 |                          34
 Berrechid    | 06.117.09.33 | Soualem Trifiya         |    45285 |       69.23 |           654.1 |                     0 |                     0 |               0 |                           2
 Berrechid    | 06.117.09.25 | Sahel Oulad H'riz       |    43776 |      383.08 |           114.3 |                     0 |                     0 |               0 |                           2
 El Jadida    | 06.181.03.01 | Chtouka                 |    38025 |      217.93 |           174.5 |                     0 |                     0 |               0 |                           0
 Nouaceur     | 06.385.01.03 | Nouaceur                |    36326 |       87.87 |           413.4 |                     0 |                     0 |               0 |                           9
 El Jadida    | 06.181.05.07 | Oulad Hcine             |    36018 |      228.26 |           157.8 |                     0 |                     0 |               0 |                           0
 El Jadida    | 06.181.07.03 | Haouzia                 |    35777 |      152.60 |           234.5 |                     0 |                     0 |               0 |                           0
 Sidi Bennour | 06.467.11.01 | Laghnadra               |    34680 |      120.91 |           286.8 |                     0 |                     0 |               0 |                           0
 El Jadida    | 06.181.07.09 | Oulad Rahmoune          |    33380 |      192.09 |           173.8 |                     0 |                     0 |               0 |                           0
 El Jadida    | 06.181.09.19 | Sidi Smaïl              |    32694 |      176.23 |           185.5 |                     0 |                     0 |               0 |                           0
 Mohammadia   | 06.371.03.07 | Sidi Moussa El Majdoub  |    30254 |       41.59 |           727.4 |                     0 |                     0 |               0 |                           2
 Médiouna     | 06.355.01.03 | Médiouna                |    29972 |        4.40 |          6809.2 |                     0 |                     0 |               0 |                           2
(20 lignes)

-- Plan d'exécution de la Requête 1 (vérifie l'index spatial GIST sur ST_Within) :
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    p.nom AS province,
    c.code_hcp,
    c.nom AS commune,
    c.pop_2024,
    COUNT(e.id_etab) FILTER (WHERE t.inclus_analyse AND e.code_niveau = 1) AS nb_niv1,
    COUNT(e.id_etab) FILTER (WHERE t.inclus_analyse AND e.code_niveau = 2) AS nb_niv2
FROM sante.commune c
JOIN sante.province p ON p.code_province = c.code_province
LEFT JOIN sante.etablissement e ON ST_Within(e.geom, c.geom)
LEFT JOIN sante.type_etablissement t ON t.code_type = e.code_type
GROUP BY p.nom, c.code_hcp, c.nom, c.pop_2024
ORDER BY nb_niv1 ASC, c.pop_2024 DESC NULLS LAST
LIMIT 20;
                                                                                    QUERY PLAN                                                                                    
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=2247.92..2247.97 rows=20 width=54) (actual time=7.226..7.233 rows=20 loops=1)
   Buffers: shared hit=758
   ->  Sort  (cost=2247.92..2248.90 rows=395 width=54) (actual time=7.225..7.229 rows=20 loops=1)
         Sort Key: (count(e.id_etab) FILTER (WHERE (t.inclus_analyse AND (e.code_niveau = 1)))), c.pop_2024 DESC NULLS LAST
         Sort Method: top-N heapsort  Memory: 29kB
         Buffers: shared hit=758
         ->  GroupAggregate  (cost=2226.54..2237.40 rows=395 width=54) (actual time=6.690..7.155 rows=153 loops=1)
               Group Key: p.nom, c.code_hcp
               Buffers: shared hit=758
               ->  Sort  (cost=2226.54..2227.53 rows=395 width=45) (actual time=6.674..6.757 rows=1696 loops=1)
                     Sort Key: p.nom, c.code_hcp
                     Sort Method: quicksort  Memory: 167kB
                     Buffers: shared hit=758
                     ->  Nested Loop Left Join  (cost=0.14..2209.51 rows=395 width=45) (actual time=0.116..5.718 rows=1696 loops=1)
                           Join Filter: ((t.code_type)::text = (e.code_type)::text)
                           Rows Removed by Join Filter: 7951
                           Buffers: shared hit=758
                           ->  Nested Loop Left Join  (cost=0.14..2171.35 rows=395 width=53) (actual time=0.095..4.326 rows=1696 loops=1)
                                 Buffers: shared hit=757
                                 ->  Nested Loop  (cost=0.00..60.46 rows=153 width=2693) (actual time=0.025..0.235 rows=153 loops=1)
                                       Join Filter: ((c.code_province)::text = (p.code_province)::text)
                                       Rows Removed by Join Filter: 709
                                       Buffers: shared hit=40
                                       ->  Seq Scan on commune c  (cost=0.00..40.53 rows=153 width=2690) (actual time=0.013..0.075 rows=153 loops=1)
                                             Buffers: shared hit=39
                                       ->  Materialize  (cost=0.00..1.14 rows=9 width=17) (actual time=0.000..0.000 rows=6 loops=153)
                                             Buffers: shared hit=1
                                             ->  Seq Scan on province p  (cost=0.00..1.09 rows=9 width=17) (actual time=0.006..0.007 rows=9 loops=1)
                                                   Buffers: shared hit=1
                                 ->  Index Scan using etablissement_geom_gist on etablissement e  (cost=0.14..13.79 rows=1 width=47) (actual time=0.013..0.025 rows=10 loops=153)
                                       Index Cond: (geom @ c.geom)
                                       Filter: st_within(geom, c.geom)
                                       Rows Removed by Filter: 7
                                       Buffers: shared hit=678
                           ->  Materialize  (cost=0.00..1.10 rows=7 width=10) (actual time=0.000..0.000 rows=6 loops=1696)
                                 Buffers: shared hit=1
                                 ->  Seq Scan on type_etablissement t  (cost=0.00..1.07 rows=7 width=10) (actual time=0.012..0.013 rows=7 loops=1)
                                       Buffers: shared hit=1
 Planning:
   Buffers: shared hit=15
 Planning Time: 1.085 ms
 Execution Time: 7.354 ms
(42 lignes)

-- ============================================================================
-- REQUÊTE 2 : Baseline euclidienne d'accessibilité — Plus proche établissement
--             par hexagone H3 (opérateur KNN <-> sur index GIST)
-- ----------------------------------------------------------------------------
-- Objectif métier (préparation Séance 5) :
--   Pour chaque hexagone H3 peuplé (maille_h3), rechercher par plus proche voisin
--   spatial (CROSS JOIN LATERAL + ORDER BY m.geom <-> e.geom LIMIT 1) l'établissement
--   de soins actif (inclus_analyse = true) le plus proche et calculer la distance
--   en kilomètres ainsi qu'un temps théorique à vol d'oiseau (baseline pour la
--   séance 5 avant comparaison au temps réel sur le graphe routier et au modèle IA).
-- ============================================================================
WITH distance_maille AS (
    SELECT
        m.h3_index,
        m.code_hcp,
        m.population,
        proche.id_etab,
        proche.nom          AS etab_proche,
        proche.code_type,
        proche.code_niveau,
        ROUND((ST_Distance(ST_Centroid(m.geom), proche.geom) / 1000.0)::numeric, 2) AS dist_km
    FROM sante.maille_h3 m
    CROSS JOIN LATERAL (
        SELECT e.id_etab, e.nom, e.code_type, e.code_niveau, e.geom
        FROM sante.etablissement e
        JOIN sante.type_etablissement t ON t.code_type = e.code_type
        WHERE t.inclus_analyse = true
        ORDER BY ST_Centroid(m.geom) <-> e.geom
        LIMIT 1
    ) proche
    WHERE m.population > 0
)
SELECT
    c.nom                                                       AS commune,
    p.nom                                                       AS province,
    COUNT(d.h3_index)                                           AS nb_hexagones_peuples,
    ROUND(SUM(d.population)::numeric, 0)                        AS pop_worldpop_totale,
    ROUND(AVG(d.dist_km)::numeric, 2)                           AS dist_moyenne_km,
    ROUND(MAX(d.dist_km)::numeric, 2)                           AS dist_max_km,
    ROUND(SUM(d.population) FILTER (WHERE d.dist_km > 10)::numeric, 0) AS pop_a_plus_de_10km
FROM distance_maille d
JOIN sante.commune c  ON c.code_hcp = d.code_hcp
JOIN sante.province p ON p.code_province = c.code_province
GROUP BY c.nom, p.nom
ORDER BY pop_a_plus_de_10km DESC NULLS LAST, dist_moyenne_km DESC
LIMIT 20;
      commune      |   province   | nb_hexagones_peuples | pop_worldpop_totale | dist_moyenne_km | dist_max_km | pop_a_plus_de_10km 
-------------------+--------------+----------------------+---------------------+-----------------+-------------+--------------------
 Deroua            | Berrechid    |                   18 |               63076 |           11.06 |       12.19 |              62249
 Sahel Oulad H'riz | Berrechid    |                  222 |               56695 |           11.81 |       16.84 |              40972
 Bouznika          | Benslimane   |                   77 |               40519 |           14.95 |       20.77 |              39953
 El Gara           | Berrechid    |                    9 |               39950 |           23.12 |       24.15 |              39950
 Oulad Hcine       | El Jadida    |                   29 |               35825 |           17.83 |       26.79 |              35741
 Chtouka           | El Jadida    |                  112 |               34343 |           14.72 |       24.18 |              34123
 Mettouh           | El Jadida    |                  127 |               33828 |           33.80 |       41.26 |              33828
 Sidi Smaïl        | El Jadida    |                   33 |               32531 |           22.17 |       30.21 |              32531
 Had Soualem       | Berrechid    |                   19 |               32243 |           12.31 |       14.04 |              32212
 Lgharbia          | Sidi Bennour |                   90 |               29551 |           41.33 |       51.26 |              29551
 Ouled Ghanem      | El Jadida    |                   72 |               27512 |           44.82 |       51.43 |              27512
 Saniat Berguig    | Sidi Bennour |                   62 |               30389 |           15.75 |       28.52 |              26787
 Zemamra           | Sidi Bennour |                   14 |               24718 |           26.33 |       27.47 |              24718
 Laghnadra         | Sidi Bennour |                   66 |               24365 |           23.83 |       30.68 |              24365
 Ouled M'Rah       | Settat       |                    8 |               23234 |           17.02 |       17.84 |              23234
 El Borouj         | Settat       |                   13 |               22846 |           12.70 |       14.58 |              22846
 Oulad Ziyane      | Berrechid    |                   83 |               22611 |           14.31 |       19.64 |              22611
 Oulad Sbaïta      | Sidi Bennour |                   72 |               22199 |           33.79 |       46.75 |              22199
 Sidi Abed         | El Jadida    |                   45 |               20965 |           19.30 |       26.43 |              20965
 Oulad Aïssa       | El Jadida    |                   36 |               19898 |           31.24 |       36.59 |              19898
(20 lignes)

-- Plan d'exécution de la Requête 2 (démontre l'Index Scan GIST KNN avec <->) :
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    m.h3_index,
    m.population,
    proche.id_etab,
    ROUND((ST_Distance(m.geom, proche.geom) / 1000.0)::numeric, 2) AS dist_km
FROM sante.maille_h3 m
CROSS JOIN LATERAL (
    SELECT e.id_etab, e.geom
    FROM sante.etablissement e
    JOIN sante.type_etablissement t ON t.code_type = e.code_type
    WHERE t.inclus_analyse = true
    ORDER BY m.geom <-> e.geom
    LIMIT 1
) proche
WHERE m.population > 0
ORDER BY dist_km DESC
LIMIT 20;
                                                                                   QUERY PLAN                                                                                    
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=98059.09..98059.14 rows=20 width=56) (actual time=428.797..428.802 rows=20 loops=1)
   Buffers: shared hit=75693
   ->  Sort  (cost=98059.09..98076.87 rows=7112 width=56) (actual time=428.796..428.799 rows=20 loops=1)
         Sort Key: (round(((st_distance(m.geom, e.geom) / '1000'::double precision))::numeric, 2)) DESC
         Sort Method: top-N heapsort  Memory: 27kB
         Buffers: shared hit=75693
         ->  Nested Loop  (cost=0.14..97869.84 rows=7112 width=56) (actual time=0.102..425.856 rows=7113 loops=1)
               Buffers: shared hit=75693
               ->  Seq Scan on maille_h3 m  (cost=0.00..1037.69 rows=7112 width=172) (actual time=0.013..4.463 rows=7113 loops=1)
                     Filter: (population > '0'::double precision)
                     Rows Removed by Filter: 18142
                     Buffers: shared hit=722
               ->  Limit  (cost=0.14..1.09 rows=1 width=44) (actual time=0.057..0.057 rows=1 loops=7113)
                     Buffers: shared hit=74971
                     ->  Nested Loop  (cost=0.14..853.40 rows=905 width=44) (actual time=0.057..0.057 rows=1 loops=7113)
                           Join Filter: ((e.code_type)::text = (t.code_type)::text)
                           Rows Removed by Join Filter: 61
                           Buffers: shared hit=74971
                           ->  Index Scan using etablissement_geom_gist on etablissement e  (cost=0.14..199.85 rows=1583 width=45) (actual time=0.022..0.044 rows=16 loops=7113)
                                 Order By: (geom <-> m.geom)
                                 Buffers: shared hit=74970
                           ->  Materialize  (cost=0.00..1.09 rows=4 width=9) (actual time=0.000..0.000 rows=4 loops=113253)
                                 Buffers: shared hit=1
                                 ->  Seq Scan on type_etablissement t  (cost=0.00..1.07 rows=4 width=9) (actual time=0.006..0.007 rows=4 loops=1)
                                       Filter: inclus_analyse
                                       Rows Removed by Filter: 3
                                       Buffers: shared hit=1
 Planning:
   Buffers: shared hit=4
 Planning Time: 0.348 ms
 Execution Time: 428.951 ms
(31 lignes)

-- ============================================================================
-- REQUÊTE 3 : Connectivité routière des établissements et coût des tronçons
--             dans un rayon de desserte (ST_DWithin + graphe noeud/troncon)
-- ----------------------------------------------------------------------------
-- Objectif métier (préparation Séance 5) :
--   Vérifier la qualité de l'accrochage des établissements de niveau 2 et 3
--   (hôpitaux et cliniques) au graphe routier (table noeud) et évaluer la densité
--   ainsi que le temps de parcours élémentaire (en minutes) des tronçons routiers
--   situés dans un tampon de 2 km autour de chaque hôpital (ST_DWithin).
-- ============================================================================
SELECT
    e.id_etab,
    COALESCE(e.nom, '(Hôpital sans nom)')                        AS etablissement,
    e.code_type,
    ns.libelle                                                   AS niveau_soin,
    c.nom                                                        AS commune,
    ROUND(ST_Distance(e.geom, n.geom)::numeric, 1)               AS dist_accrochage_noeud_m,
    COUNT(tr.id_troncon)                                         AS nb_troncons_rayon_2km,
    ROUND((SUM(tr.longueur_m) / 1000.0)::numeric, 2)             AS km_voirie_rayon_2km,
    ROUND(AVG(tr.longueur_m / NULLIF(tr.vitesse_kmh * 1000.0 / 60.0, 0))::numeric, 3) AS temps_moyen_troncon_min
FROM sante.etablissement e
JOIN sante.niveau_soin ns  ON ns.code_niveau = e.code_niveau
JOIN sante.commune c       ON c.code_hcp = e.code_hcp
LEFT JOIN sante.noeud n    ON n.id_noeud = e.id_noeud
LEFT JOIN sante.troncon tr ON ST_DWithin(e.geom, tr.geom, 2000)
WHERE e.code_niveau IN (2, 3)
GROUP BY e.id_etab, e.nom, e.code_type, ns.libelle, c.nom, e.geom, n.geom
ORDER BY dist_accrochage_noeud_m DESC NULLS LAST, nb_troncons_rayon_2km ASC
LIMIT 20;
 id_etab |           etablissement           | code_type |                   niveau_soin                   |        commune         | dist_accrochage_noeud_m | nb_troncons_rayon_2km | km_voirie_rayon_2km | temps_moyen_troncon_min 
---------+-----------------------------------+-----------+-------------------------------------------------+------------------------+-------------------------+-----------------------+---------------------+-------------------------
    1497 | (Hôpital sans nom)                | hopital   | Hôpital de référence (provincial / préfectoral) | Sidi Ali Ben Hamdouche |                   264.6 |                  1507 |              114.50 |                   0.180
      56 | (Hôpital sans nom)                | hopital   | Hôpital de référence (provincial / préfectoral) | Laqraqra               |                   125.4 |                   224 |               56.41 |                   0.619
    1580 | مستشفى سيدي بنور                  | hopital   | Hôpital de référence (provincial / préfectoral) | Sidi Bennour           |                   102.4 |                  2334 |              151.27 |                   0.127
     706 | clinique ain saba3                | clinique  | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    90.7 |                  2329 |              176.58 |                   0.140
    1579 | مستشفى اهل الغلام الأزهر          | hopital   | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    83.5 |                  4506 |              285.55 |                   0.121
    1480 | (Hôpital sans nom)                | hopital   | Hôpital de référence (provincial / préfectoral) | Mohammédia             |                    81.4 |                  2444 |              163.45 |                   0.130
    1533 | Hôpital Hassan 2                  | hopital   | Hôpital de référence (provincial / préfectoral) | Settat                 |                    79.1 |                  4444 |              249.89 |                   0.106
    1543 | (Hôpital sans nom)                | clinique  | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    79.1 |                  4897 |              288.05 |                   0.113
    1538 | Ajial Hôpital Pédiatrique         | hopital   | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    70.1 |                  5917 |              337.56 |                   0.102
    1555 | Complexe Medico-Social Al Wouroud | clinique  | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    63.4 |                  6623 |              360.18 |                   0.099
    1526 | Hôpital Sekkat                    | hopital   | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    60.2 |                  8111 |              398.94 |                   0.090
    1572 | hopital d'errahma                 | hopital   | Hôpital de référence (provincial / préfectoral) | Dar Bouazza            |                    58.5 |                  3371 |              231.56 |                   0.140
    1434 | Hôpital Bouafi                    | hopital   | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    58.4 |                  6371 |              353.02 |                   0.100
    1570 | Clinique Green Town               | clinique  | Hôpital de référence (provincial / préfectoral) | Bouskoura              |                    57.1 |                  1080 |              119.63 |                   0.213
     710 | clinique firdaous                 | clinique  | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    55.5 |                  4924 |              301.45 |                   0.116
    1532 | Clinique CNSS                     | clinique  | Hôpital de référence (provincial / préfectoral) | Settat                 |                    55.3 |                  4170 |              241.38 |                   0.107
    1431 | (Hôpital sans nom)                | hopital   | Hôpital de référence (provincial / préfectoral) | Ben Ahmed              |                    55.0 |                  1446 |              116.43 |                   0.160
      84 | Clinique Attal                    | clinique  | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    54.9 |                  3699 |              281.11 |                   0.136
    1575 | Hôpital Mly abdellah              | hopital   | Hôpital de référence (provincial / préfectoral) | Mohammédia             |                    53.8 |                  4549 |              250.03 |                   0.102
    1573 | Clinique Mersultan                | clinique  | Hôpital de référence (provincial / préfectoral) | Casablanca             |                    53.8 |                  6188 |              352.90 |                   0.103
(20 lignes)

-- Plan d'exécution de la Requête 3 (démontre l'Index Scan GIST sur troncon_geom_gist via ST_DWithin) :
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    e.id_etab,
    e.nom,
    COUNT(tr.id_troncon) AS nb_troncons_rayon_2km
FROM sante.etablissement e
JOIN sante.troncon tr ON ST_DWithin(e.geom, tr.geom, 2000)
WHERE e.code_niveau IN (2, 3)
GROUP BY e.id_etab, e.nom;
                                                                      QUERY PLAN                                                                      
------------------------------------------------------------------------------------------------------------------------------------------------------
 GroupAggregate  (cost=0.69..71938.38 rows=141 width=46) (actual time=1.526..1659.293 rows=141 loops=1)
   Group Key: e.id_etab
   Buffers: shared hit=252269
   ->  Nested Loop  (cost=0.69..71446.52 rows=98091 width=46) (actual time=0.052..1520.941 rows=650252 loops=1)
         Buffers: shared hit=252269
         ->  Index Scan using etablissement_pkey on etablissement e  (cost=0.28..92.98 rows=141 width=70) (actual time=0.011..1.323 rows=141 loops=1)
               Filter: (code_niveau = ANY ('{2,3}'::integer[]))
               Rows Removed by Filter: 1442
               Buffers: shared hit=42
         ->  Index Scan using troncon_geom_gist on troncon tr  (cost=0.41..505.73 rows=32 width=150) (actual time=0.075..9.769 rows=4612 loops=141)
               Index Cond: (geom && st_expand(e.geom, '2000'::double precision))
               Filter: st_dwithin(e.geom, geom, '2000'::double precision)
               Rows Removed by Filter: 1108
               Buffers: shared hit=252227
 Planning:
   Buffers: shared hit=3
 Planning Time: 1.149 ms
 Execution Time: 1659.504 ms
(18 lignes)
```
