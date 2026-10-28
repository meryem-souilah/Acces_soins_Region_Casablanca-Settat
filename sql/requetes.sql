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
