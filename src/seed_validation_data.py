
from falkordb import FalkorDB

db = FalkorDB(host="127.0.0.1", port=6379)
graph = db.select_graph("testpilot_ai")

def write(query, **params):
    graph.query(query, params=params)

# Check that our validated base graph exists.
count = graph.ro_query("""
    MATCH (e:ECU {id: 'ECU-001'})
    RETURN count(e)
""").result_set[0][0]

if count != 1:
    raise RuntimeError("Run seed_graph.py first")

# All data below is synthetic demonstration data.

subsystems = [
    ("SUB-001", "Power Supply"),
    ("SUB-002", "MCU and Watchdog"),
    ("SUB-003", "Automotive Ethernet"),
    ("SUB-004", "Camera Interface"),
]

tests = [
    ("TEST-001", "Power Transient", 10, "SUB-001"),
    ("TEST-002", "Power Rail Monitoring", 8, "SUB-001"),
    ("TEST-003", "PMIC Startup", 6, "SUB-001"),
    ("TEST-004", "Watchdog Recovery", 12, "SUB-002"),
    ("TEST-005", "MCU Reset Handling", 10, "SUB-002"),
    ("TEST-006", "Ethernet Link Recovery", 15, "SUB-003"),
    ("TEST-007", "Network Packet Loss", 14, "SUB-003"),
    ("TEST-008", "Camera Link Integrity", 18, "SUB-004"),
]

requirements = [
    ("REQ-001", "ECU supply transient recovery"),
    ("REQ-002", "Voltage monitoring"),
    ("REQ-003", "Stable PMIC startup"),
    ("REQ-004", "Watchdog recovery"),
    ("REQ-005", "Ethernet communication continuity"),
    ("REQ-006", "Camera stream availability"),
]

failure_modes = [
    ("FM-001", "Unexpected ECU Reset", 8, "REQ-001"),
    ("FM-002", "Undervoltage Detection Failure", 9, "REQ-002"),
    ("FM-003", "PMIC Startup Instability", 7, "REQ-003"),
    ("FM-004", "Watchdog Recovery Failure", 9, "REQ-004"),
    ("FM-005", "Ethernet Link Loss", 7, "REQ-005"),
    ("FM-006", "Camera Stream Loss", 8, "REQ-006"),
]

# Test ID, failure ID, synthetic detection probability.
coverage = [
    ("TEST-001", "FM-001", 0.80),
    ("TEST-001", "FM-002", 0.60),
    ("TEST-002", "FM-001", 0.50),
    ("TEST-002", "FM-002", 0.95),
    ("TEST-003", "FM-003", 0.90),
    ("TEST-004", "FM-004", 0.95),
    ("TEST-004", "FM-001", 0.40),
    ("TEST-005", "FM-001", 0.75),
    ("TEST-005", "FM-004", 0.65),
    ("TEST-006", "FM-005", 0.90),
    ("TEST-007", "FM-005", 0.60),
    ("TEST-008", "FM-006", 0.90),
]

# Create subsystem nodes and connections.
for sid, name in subsystems:
    write("""
        MERGE (s:Subsystem {id:$id})
        SET s.name = $name
    """, id=sid, name=name)

    write("""
        MATCH (e:ECU {id:'ECU-001'})
        MATCH (s:Subsystem {id:$id})
        MERGE (e)-[:CONTAINS]->(s)
    """, id=sid)

# Create test nodes and subsystem connections.
for tid, name, duration, sid in tests:
    write("""
        MERGE (t:Test {id:$id})
        SET t.name=$name, t.duration_min=$duration
    """, id=tid, name=name, duration=duration)

    write("""
        MATCH (s:Subsystem {id:$sid})
        MATCH (t:Test {id:$tid})
        MERGE (s)-[:HAS_TEST]->(t)
    """, sid=sid, tid=tid)

# Create requirement nodes.
for rid, description in requirements:
    write("""
        MERGE (r:Requirement {id:$id})
        SET r.description=$description
    """, id=rid, description=description)

# Create failure modes and affected requirements.
for fid, name, risk, rid in failure_modes:
    write("""
        MERGE (f:FailureMode {id:$id})
        SET f.name=$name, f.risk_weight=$risk
    """, id=fid, name=name, risk=risk)

    write("""
        MATCH (f:FailureMode {id:$fid})
        MATCH (r:Requirement {id:$rid})
        MERGE (f)-[:AFFECTS]->(r)
    """, fid=fid, rid=rid)

# Connect tests to failure modes.
for tid, fid, probability in coverage:
    write("""
        MATCH (t:Test {id:$tid})
        MATCH (f:FailureMode {id:$fid})
        MERGE (t)-[d:DETECTS]->(f)
        SET d.detection_probability=$probability
    """, tid=tid, fid=fid, probability=probability)

# Add execution prerequisites.
for tid in ("TEST-006", "TEST-008"):
    write("""
        MATCH (t:Test {id:$tid})
        MATCH (p:Test {id:'TEST-003'})
        MERGE (t)-[:REQUIRES]->(p)
    """, tid=tid)

# Final graph validation.
nodes = graph.ro_query(
    "MATCH (n) RETURN count(n)"
).result_set[0][0]

edges = graph.ro_query(
    "MATCH ()-[r]->() RETURN count(r)"
).result_set[0][0]

print("Graph: testpilot_ai")
print("Nodes:", nodes)
print("Relationships:", edges)

assert nodes == 25, f"Expected 25 nodes, got {nodes}"
assert edges == 32, f"Expected 32 edges, got {edges}"

print("PASS: Synthetic ECU dataset validated")
