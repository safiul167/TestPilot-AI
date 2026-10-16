
"""Regression tests for TestPilot AI."""

from collections import defaultdict
from math import isclose

from falkordb import FalkorDB
from src.run_agent import choose_test, load_context


def make_context(executed=None, passed=None, suspected=None):
    """Create a small synthetic planner fixture."""

    tests = {
        "TEST-001": {
            "name": "Power Transient",
            "duration": 10,
            "links": [
                ("FM-001", 8.0, 0.80, "REQ-001"),
                ("FM-002", 9.0, 0.60, "REQ-002"),
            ],
        },
        "TEST-002": {
            "name": "Power Rail Monitoring",
            "duration": 8,
            "links": [
                ("FM-001", 8.0, 0.50, "REQ-001"),
                ("FM-002", 9.0, 0.95, "REQ-002"),
            ],
        },
        "TEST-003": {
            "name": "PMIC Startup",
            "duration": 6,
            "links": [
                ("FM-003", 7.0, 0.90, "REQ-003"),
            ],
        },
        "TEST-006": {
            "name": "Ethernet Link Recovery",
            "duration": 15,
            "links": [
                ("FM-005", 7.0, 0.90, "REQ-005"),
            ],
        },
    }

    dependencies = defaultdict(set)
    dependencies["TEST-006"].add("TEST-003")

    return (
        tests,
        dependencies,
        set(executed or []),
        set(passed or []),
        set(suspected or []),
    )


def test_initial_recommendation():
    result = choose_test(make_context(), 60)

    assert result is not None
    assert result[1] == "TEST-002"
    assert isclose(result[0], 1.56875)


def test_failure_changes_recommendation():
    context = make_context(
        executed={"TEST-002"},
        suspected={"FM-002"},
    )

    result = choose_test(context, 52)

    assert result is not None
    assert result[1] == "TEST-001"
    assert isclose(result[0], 1.72)


def test_completed_test_not_repeated():
    context = make_context(
        executed={"TEST-002"},
        passed={"TEST-002"},
    )

    result = choose_test(context, 52)

    assert result[1] != "TEST-002"
    assert result[1] == "TEST-001"


def test_prerequisite_handling():
    # TEST-003 executed but failed: TEST-006 stays blocked.
    blocked = make_context(
        executed={"TEST-001", "TEST-002", "TEST-003"},
        passed=set(),
    )

    assert choose_test(blocked, 60) is None

    # A passing prerequisite unlocks TEST-006.
    unlocked = make_context(
        executed={"TEST-001", "TEST-002", "TEST-003"},
        passed={"TEST-003"},
    )

    result = choose_test(unlocked, 60)

    assert result is not None
    assert result[1] == "TEST-006"


def test_insufficient_time_budget():
    result = choose_test(make_context(), 5)

    assert result is None


def test_live_graph_relationships():
    """Read-only test against the seeded FalkorDB graph."""

    db = FalkorDB(host="127.0.0.1", port=6379)
    graph = db.select_graph("testpilot_ai")

    tests = graph.ro_query(
        "MATCH (t:Test) RETURN count(t)"
    ).result_set[0][0]

    coverage = graph.ro_query("""
        MATCH (:Test)-[:DETECTS]->(:FailureMode)
        RETURN count(*)
    """).result_set[0][0]

    dependencies = graph.ro_query("""
        MATCH (:Test)-[:REQUIRES]->(:Test)
        RETURN count(*)
    """).result_set[0][0]

    assert tests == 8
    assert coverage == 12
    assert dependencies == 2


def test_live_graph_recommendation():
    """Confirm the planner uses the real graph data."""

    db = FalkorDB(host="127.0.0.1", port=6379)
    graph = db.select_graph("testpilot_ai")

    # Read-only: this does not create a session.
    context = load_context(
        graph, "PYTEST-READ-ONLY-SESSION"
    )

    recommendation = choose_test(context, 60)

    assert recommendation is not None
    assert recommendation[1] == "TEST-002"
    assert isclose(
        recommendation[0], 1.56875,
        rel_tol=1e-6
    )
