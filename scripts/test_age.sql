LOAD 'age';
SET search_path = ag_catalog, public;
SELECT * FROM cypher('life_graph', $$ MATCH (n) RETURN count(n) $$) AS (count agtype);
