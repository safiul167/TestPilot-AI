
// TestPilot AI — FalkorDB Cypher Reference
// Run each query separately in FalkorDB Browser.
// These are read-only demonstration queries.

// Q1: List the engineering test catalogue
MATCH (s:Subsystem)-[:HAS_TEST]->(t:Test)
RETURN s.name AS subsystem,
       t.id AS test_id,
       t.name AS test_name,
       t.duration_min AS duration
ORDER BY test_id;

// Q2: Retrieve graph-based risk coverage
MATCH (t:Test)-[d:DETECTS]->(f:FailureMode)
      -[:AFFECTS]->(r:Requirement)
RETURN t.id AS test_id,
       f.id AS failure_id,
       f.risk_weight AS risk,
       d.detection_probability AS probability,
       r.id AS requirement_id
ORDER BY test_id, failure_id;

// Q3: Find prerequisite dependencies
MATCH (t:Test)-[:REQUIRES]->(p:Test)
RETURN t.id AS test_id,
       p.id AS prerequisite_id
ORDER BY test_id;

// Q4: Retrieve persistent session history
MATCH (s:Session {id:'DEMO-UI-001'})
      -[:HAS_RUN]->(run:TestRun)
      -[:FOR_TEST]->(t:Test)
RETURN t.id AS test_id,
       run.outcome AS outcome,
       run.duration_min AS duration
ORDER BY test_id;

// Q5: Retrieve suspected failure modes
MATCH (s:Session {id:'DEMO-UI-001'})
      -[:HAS_RUN]->(run:TestRun)
      -[:SUSPECTS]->(f:FailureMode)
RETURN run.id AS run_id,
       f.id AS failure_id,
       f.name AS failure_name;

// Q6: Retrieve agent decisions
MATCH (s:Session {id:'DEMO-UI-001'})
      -[:HAS_DECISION]->(d:Decision)
      -[:SELECTS]->(t:Test)
RETURN t.id AS test_id,
       d.score AS priority_score,
       d.remaining_before AS time_before
ORDER BY time_before DESC;

// Q7: Retrieve engineering evidence path
MATCH (e:ECU)-[:CONTAINS]->(s:Subsystem)
      -[:HAS_TEST]->(t:Test)
      -[:DETECTS]->(f:FailureMode)
      -[:AFFECTS]->(r:Requirement)
RETURN e.name AS ecu,
       s.name AS subsystem,
       t.id AS test_id,
       f.id AS failure_id,
       r.id AS requirement_id
ORDER BY test_id;

// Q8: Verify graph counts
MATCH (n)
RETURN count(n) AS total_nodes;
