
from falkordb import FalkorDB

# Connect to our persistent FalkorDB container
db = FalkorDB(host="127.0.0.1", port=6379)
graph = db.select_graph("testpilot_ai")

# Synthetic automotive engineering entities
queries = [
    """
    MERGE (e:ECU {id:'ECU-001'})
    SET e.name = 'ADAS Camera ECU'
    """,
    """
    MERGE (s:Subsystem {id:'SUB-001'})
    SET s.name = 'Power Supply'
    """,
    """
    MERGE (t:Test {id:'TEST-001'})
    SET t.name = 'Power Transient',
        t.duration_min = 10
    """,
    """
    MERGE (f:FailureMode {id:'FM-001'})
    SET f.name = 'Unexpected ECU Reset',
        f.risk_weight = 8
    """,
    """
    MERGE (r:Requirement {id:'REQ-001'})
    SET r.description = 'ECU supply transient recovery'
    """,
    """
    MATCH (e:ECU {id:'ECU-001'})
    MATCH (s:Subsystem {id:'SUB-001'})
    MERGE (e)-[:CONTAINS]->(s)
    """,
    """
    MATCH (s:Subsystem {id:'SUB-001'})
    MATCH (t:Test {id:'TEST-001'})
    MERGE (s)-[:HAS_TEST]->(t)
    """,
    """
    MATCH (t:Test {id:'TEST-001'})
    MATCH (f:FailureMode {id:'FM-001'})
    MERGE (t)-[:DETECTS]->(f)
    """,
    """
    MATCH (f:FailureMode {id:'FM-001'})
    MATCH (r:Requirement {id:'REQ-001'})
    MERGE (f)-[:AFFECTS]->(r)
    """
]

for query in queries:
    graph.query(query)

# Validate graph counts
nodes = graph.ro_query(
    "MATCH (n) RETURN count(n)"
).result_set[0][0]

edges = graph.ro_query(
    "MATCH ()-[r]->() RETURN count(r)"
).result_set[0][0]

print("Graph: testpilot_ai")
print("Nodes:", nodes)
print("Relationships:", edges)

assert nodes == 5, "Unexpected number of nodes"
assert edges == 4, "Unexpected number of relationships"

# Verify a complete multi-hop evidence path
result = graph.ro_query("""
MATCH (e:ECU)-[:CONTAINS]->(s:Subsystem)
      -[:HAS_TEST]->(t:Test)
      -[:DETECTS]->(f:FailureMode)
      -[:AFFECTS]->(r:Requirement)
RETURN e.name, s.name, t.name, f.name, r.id
""").result_set

assert len(result) == 1, "Expected one evidence path"

for row in result:
    print("Evidence path:", " -> ".join(map(str, row)))

print("PASS: Engineering graph validated")
