"""Read-only counterfactual planning over graph data loaded from FalkorDB.

The graph remains the source of truth. We temporarily remove one DETECTS
relationship from the in-memory context, compare test rankings, and never
write the hypothetical change back to FalkorDB.
"""


def rank_candidates(context, budget, removed_edge=None):
    """Rank eligible tests using the same score/constraints as run_agent.choose_test.

    removed_edge: optional (test_id, failure_mode_id) pair.
    Returns descending sorted list of score/test_id/test_name/duration/evidence.
    """
    tests, dependencies, executed, passed, suspected = context
    ranked = []
    for test_id, test in tests.items():
        if test_id in executed:
            continue
        if not dependencies[test_id].issubset(passed):
            continue
        if test["duration"] > budget:
            continue
        links = [
            (fid, risk, prob, rid)
            for fid, risk, prob, rid in test["links"]
            if removed_edge != (test_id, fid)
        ]
        # A test with no failure coverage must not be recommended.
        if not links:
            continue
        benefit = sum(
            risk * prob * (2.0 if fid in suspected else 1.0)
            for fid, risk, prob, rid in links
        )
        ranked.append({
            "test_id": test_id,
            "name": test["name"],
            "duration": test["duration"],
            "score": benefit / test["duration"],
            "links": links,
        })
    return sorted(ranked, key=lambda row: (-row["score"], row["test_id"]))


def comparison(context, budget, test_id, failure_id):
    """Return normal and one-edge-removed rankings without mutating graph state."""
    tests = context[0]
    if test_id not in tests:
        raise ValueError("Unknown test ID")
    if not any(fid == failure_id for fid, *_ in tests[test_id]["links"]):
        raise ValueError("Selected edge is absent from the graph evidence")
    before = rank_candidates(context, budget)
    after = rank_candidates(context, budget, removed_edge=(test_id, failure_id))
    return before, after
