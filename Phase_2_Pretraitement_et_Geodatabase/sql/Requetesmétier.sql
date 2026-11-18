SET search_path = sante, public;

CREATE OR REPLACE VIEW maille_h3_habitee AS
SELECT * FROM maille_h3 WHERE population > 0;

CREATE INDEX IF NOT EXISTS maille_h3_habitee_gist ON maille_h3 USING gist (geom)
WHERE population > 0;


-- ============================================================================
-- Requête 1 : raccorder chaque hexagone habité au nœud routier le plus proche
-- ============================================================================

SELECT m.h3_index,
       m.population,
       n.id_noeud,
       round(n.dist_m::numeric) AS dist_raccordement_m
FROM maille_h3_habitee m
CROSS JOIN LATERAL (
    SELECT nd.id_noeud, ST_Distance(nd.geom, ST_Centroid(m.geom)) AS dist_m
    FROM noeud nd
    ORDER BY nd.geom <-> ST_Centroid(m.geom)
    LIMIT 1
) n
ORDER BY n.dist_m DESC
LIMIT 20;    
EXPLAIN (ANALYZE, BUFFERS)
SELECT m.h3_index, m.population, n.id_noeud, round(n.dist_m::numeric) AS dist_raccordement_m
FROM maille_h3_habitee m
CROSS JOIN LATERAL (
    SELECT nd.id_noeud, ST_Distance(nd.geom, ST_Centroid(m.geom)) AS dist_m
    FROM noeud nd
    ORDER BY nd.geom <-> ST_Centroid(m.geom)
    LIMIT 1
) n
ORDER BY n.dist_m DESC
LIMIT 20;


-- ============================================================================
-- Requête 2 : population éloignée d'un centre de santé, par province
-- ============================================================================


SELECT p.nom                                                     AS province,
       round(sum(m.population)::numeric)                                AS population,
       round(sum(m.population) FILTER (WHERE d.dist_m > 5000)::numeric) AS pop_a_plus_de_5km,
       round((100 * sum(m.population) FILTER (WHERE d.dist_m > 5000)
                  / sum(m.population))::numeric, 1)                     AS part_pct,
       round((max(d.dist_m) / 1000)::numeric, 1)                        AS distance_max_km
FROM maille_h3_habitee m
JOIN commune  c USING (code_hcp)
JOIN province p USING (code_province)
CROSS JOIN LATERAL (
    SELECT ST_Distance(e.geom, ST_Centroid(m.geom)) AS dist_m
    FROM etablissement e
    JOIN type_etablissement t USING (code_type)
    WHERE t.inclus_analyse
    ORDER BY e.geom <-> ST_Centroid(m.geom)
    LIMIT 1
) d
GROUP BY p.nom
ORDER BY part_pct DESC;

EXPLAIN (ANALYZE, BUFFERS)
SELECT p.nom, round(sum(m.population)::numeric),
       round(sum(m.population) FILTER (WHERE d.dist_m > 5000)::numeric),
       round((100 * sum(m.population) FILTER (WHERE d.dist_m > 5000) / sum(m.population))::numeric, 1) AS part_pct,
       round((max(d.dist_m) / 1000)::numeric, 1)
FROM maille_h3_habitee m
JOIN commune  c USING (code_hcp)
JOIN province p USING (code_province)
CROSS JOIN LATERAL (
    SELECT ST_Distance(e.geom, ST_Centroid(m.geom)) AS dist_m
    FROM etablissement e JOIN type_etablissement t USING (code_type)
    WHERE t.inclus_analyse
    ORDER BY e.geom <-> ST_Centroid(m.geom)
    LIMIT 1
) d
GROUP BY p.nom
ORDER BY part_pct DESC;


-- ============================================================================
-- Requête 3 : sites candidats dans les zones blanches
-- ============================================================================

WITH zone_blanche AS MATERIALIZED (
    SELECT m.h3_index, m.population, m.geom
    FROM maille_h3_habitee m
    WHERE NOT EXISTS (
        SELECT 1
        FROM etablissement e
        JOIN type_etablissement t USING (code_type)
        WHERE t.inclus_analyse
          AND ST_DWithin(e.geom, ST_Centroid(m.geom), 5000)
    )
)
SELECT s.h3_index                         AS site_candidat,
       s.code_hcp,
       c.nom                              AS commune,
       count(*)                           AS hexagones_couverts,
       round(sum(z.population)::numeric)  AS population_gagnee
FROM zone_blanche z
JOIN maille_h3 s ON ST_DWithin(s.geom, ST_Centroid(z.geom), 3000)
JOIN commune c ON c.code_hcp = s.code_hcp
GROUP BY s.h3_index, s.code_hcp, c.nom
ORDER BY population_gagnee DESC
LIMIT 10;

EXPLAIN (ANALYZE, BUFFERS)
WITH zone_blanche AS MATERIALIZED (
    SELECT m.h3_index, m.population, m.geom
    FROM maille_h3_habitee m
    WHERE NOT EXISTS (
        SELECT 1 FROM etablissement e JOIN type_etablissement t USING (code_type)
        WHERE t.inclus_analyse AND ST_DWithin(e.geom, ST_Centroid(m.geom), 5000))
)
SELECT s.h3_index, s.code_hcp, c.nom, count(*), round(sum(z.population)::numeric) AS population_gagnee
FROM zone_blanche z
JOIN maille_h3 s ON ST_DWithin(s.geom, ST_Centroid(z.geom), 3000)
JOIN commune c ON c.code_hcp = s.code_hcp
GROUP BY s.h3_index, s.code_hcp, c.nom
ORDER BY population_gagnee DESC
LIMIT 10;