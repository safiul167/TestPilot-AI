"""Tests for the read-only Graph What-If feature (no Docker required)."""
from collections import defaultdict
from math import isclose
from src.what_if import comparison, rank_candidates


def fixture_context():
    tests = {
        "TEST-001": {"name": "Power Transient", "duration": 10,
                     "links": [("FM-001", 8.0, 0.8, "REQ-001"),
                               ("FM-002", 9.0, 0.6, "REQ-002")]},
        "TEST-002": {"name": "Power Rail Monitoring", "duration": 8,
                     "links": [("FM-001", 8.0, 0.5, "REQ-001"),
                               ("FM-002", 9.0, 0.95, "REQ-002")]},
        "TEST-005": {"name": "MCU Reset Handling", "duration": 10,
                     "links": [("FM-001", 8.0, 0.75, "REQ-001"),
                               ("FM-004", 9.0, 0.65, "REQ-004")]},
    }
    return (tests, defaultdict(set), set(), set(), set())


def test_baseline_winner():
    ranked = rank_candidates(fixture_context(), 120)
    assert ranked[0]["test_id"] == "TEST-002"
    assert isclose(ranked[0]["score"], 1.56875)


def test_edge_removal_changes_winner():
    baseline, hypothetical = comparison(fixture_context(), 120, "TEST-002", "FM-002")
    assert baseline[0]["test_id"] == "TEST-002"
    assert hypothetical[0]["test_id"] == "TEST-005"
    assert isclose(next(t["score"] for t in hypothetical if t["test_id"] == "TEST-002"), 0.5)


def test_counterfactual_does_not_mutate_original():
    context = fixture_context()
    comparison(context, 120, "TEST-002", "FM-002")
    assert len(context[0]["TEST-002"]["links"]) == 2


def test_budget_excludes_unaffordable():
    ranked = rank_candidates(fixture_context(), 5)
    assert ranked == []


def test_eight_test_budget_and_dependency_walkthrough():
    # Mirror the public synthetic seed dataset: this tests scheduling logic,
    # not a live FalkorDB or Streamlit instance.
    tests = {
        "TEST-001": {"name": "Power Transient", "duration": 10, "links": [("FM-001",8,.8,"REQ-001"),("FM-002",9,.6,"REQ-002")]},
        "TEST-002": {"name": "Power Rail Monitoring", "duration": 8, "links": [("FM-001",8,.5,"REQ-001"),("FM-002",9,.95,"REQ-002")]},
        "TEST-003": {"name": "PMIC Startup", "duration": 6, "links": [("FM-003",7,.9,"REQ-003")]},
        "TEST-004": {"name": "Watchdog Recovery", "duration": 12, "links": [("FM-004",9,.95,"REQ-004"),("FM-001",8,.4,"REQ-001")]},
        "TEST-005": {"name": "MCU Reset Handling", "duration": 10, "links": [("FM-001",8,.75,"REQ-001"),("FM-004",9,.65,"REQ-004")]},
        "TEST-006": {"name": "Ethernet Link Recovery", "duration": 15, "links": [("FM-005",7,.9,"REQ-005")]},
        "TEST-007": {"name": "Network Packet Loss", "duration": 14, "links": [("FM-005",7,.6,"REQ-005")]},
        "TEST-008": {"name": "Camera Link Integrity", "duration": 18, "links": [("FM-006",8,.9,"REQ-006")]},
    }
    deps = defaultdict(set)
    deps["TEST-006"].add("TEST-003")
    deps["TEST-008"].add("TEST-003")
    executed, passed, suspected = set(), set(), set()
    context = (tests, deps, executed, passed, suspected)
    left = 120
    order = []
    for _ in range(8):
        candidate = rank_candidates(context, left)[0]
        tid = candidate["test_id"]
        order.append(tid)
        left -= candidate["duration"]
        executed.add(tid)
        if tid == "TEST-002":
            suspected.add("FM-002")
        else:
            passed.add(tid)
    assert len(set(order)) == 8
    assert order[0] == "TEST-002"
    assert order[1] == "TEST-001"
    assert order.index("TEST-003") < order.index("TEST-006")
    assert order.index("TEST-003") < order.index("TEST-008")
    assert left == 27
    assert rank_candidates(context, left) == []
