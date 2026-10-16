
"""Graph-powered, stateful ECU test demonstration."""

import argparse
from collections import defaultdict
from falkordb import FalkorDB


def read(graph, cypher, **params):
    return graph.ro_query(cypher, params=params).result_set


def session_budget(graph, session_id, initial_budget):
    saved = read(
        graph,
        "MATCH (s:Session {id:$sid}) RETURN s.remaining_minutes",
        sid=session_id,
    )

    if saved:
        return int(saved[0][0])

    graph.query("""
        CREATE (:Session {
            id:$sid,
            initial_budget:$budget,
            remaining_minutes:$budget
        })
    """, params={"sid": session_id, "budget": initial_budget})

    return initial_budget


def load_context(graph, session_id):
    # Load engineering relationships from FalkorDB.
    evidence_rows = read(graph, """
        MATCH (t:Test)-[d:DETECTS]->(f:FailureMode)
              -[:AFFECTS]->(r:Requirement)
        RETURN t.id,t.name,t.duration_min,
               f.id,f.risk_weight,
               d.detection_probability,r.id
    """)

    tests = {}

    for tid, name, duration, fid, risk, prob, rid in evidence_rows:
        tests.setdefault(tid, {
            "name": name,
            "duration": int(duration),
            "links": []
        })
        tests[tid]["links"].append(
            (fid, float(risk), float(prob), rid)
        )

    if len(tests) != 8:
        raise RuntimeError(
            f"Expected 8 seeded tests; found {len(tests)}"
        )

    # Test prerequisites are stored in the graph.
    dependencies = defaultdict(set)

    for tid, prerequisite in read(graph, """
        MATCH (t:Test)-[:REQUIRES]->(p:Test)
        RETURN t.id,p.id
    """):
        dependencies[tid].add(prerequisite)

    # Retrieve previous test results from the session.
    history = read(graph, """
        MATCH (s:Session {id:$sid})
              -[:HAS_RUN]->(run:TestRun)
              -[:FOR_TEST]->(t:Test)
        RETURN t.id,run.outcome
    """, sid=session_id)

    executed = {tid for tid, _ in history}

    passed = {
        tid for tid, outcome in history
        if outcome == "PASS"
    }

    # Retrieve concerns raised by previous failed tests.
    suspected = {
        fid for (fid,) in read(graph, """
            MATCH (s:Session {id:$sid})
                  -[:HAS_RUN]->(run:TestRun)
                  -[:SUSPECTS]->(f:FailureMode)
            RETURN DISTINCT f.id
        """, sid=session_id)
    }

    return tests, dependencies, executed, passed, suspected


def choose_test(context, remaining):
    tests, dependencies, executed, passed, suspected = context

    eligible = []

    for tid, test in tests.items():
        # Never repeat an already executed test in this MVP.
        if tid in executed:
            continue

        # Prerequisites must have passed.
        if not dependencies[tid].issubset(passed):
            continue

        if test["duration"] > remaining:
            continue

        # Failed-test concerns increase related test priority.
        benefit = sum(
            risk * prob * (2.0 if fid in suspected else 1.0)
            for fid, risk, prob, _ in test["links"]
        )

        score = benefit / test["duration"]
        eligible.append((score, tid, test))

    eligible.sort(key=lambda item: (-item[0], item[1]))

    return eligible[0] if eligible else None


def simulate(test_id):
    # Demonstration only: no physical ECU is being tested.
    if test_id == "TEST-002":
        return (
            "FAIL",
            "FM-002",
            "Synthetic undervoltage-monitor anomaly"
        )

    return "PASS", None, "Synthetic test passed"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default="DEMO-001")
    parser.add_argument("--budget", type=int, default=60)

    args = parser.parse_args()

    if args.budget <= 0 or not args.session.strip():
        parser.error("Use a nonempty session and positive budget")

    db = FalkorDB(host="127.0.0.1", port=6379)
    graph = db.select_graph("testpilot_ai")

    remaining = session_budget(
        graph, args.session, args.budget
    )

    context = load_context(graph, args.session)
    selection = choose_test(context, remaining)

    print(
        f"\nSession: {args.session} | "
        f"Remaining: {remaining} min"
    )

    if selection is None:
        print("No eligible tests remain.")
        return

    score, tid, test = selection

    print(
        f"SELECTED: {tid} - {test['name']} | "
        f"Score: {score:.3f}"
    )

    for fid, risk, prob, rid in test["links"]:
        print(
            f"  Evidence: {tid} DETECTS {fid} "
            f"AFFECTS {rid} (risk={risk}, p={prob})"
        )

    outcome, suspected_fid, message = simulate(tid)
    after = remaining - test["duration"]

    decision_id = f"{args.session}:{tid}:decision"
    run_id = f"{args.session}:{tid}:run"

    # Save decision, test run, and remaining budget.
    graph.query("""
        MATCH (s:Session {id:$sid})
        MATCH (t:Test {id:$tid})
        MERGE (d:Decision {id:$did})
        SET d.score=$score, d.remaining_before=$before
        MERGE (run:TestRun {id:$rid})
        SET run.outcome=$outcome,
            run.duration_min=$duration,
            run.message=$message
        MERGE (s)-[:HAS_DECISION]->(d)
        MERGE (d)-[:SELECTS]->(t)
        MERGE (s)-[:HAS_RUN]->(run)
        MERGE (run)-[:FOR_TEST]->(t)
        SET s.remaining_minutes=$after
    """, params={
        "sid": args.session,
        "tid": tid,
        "did": decision_id,
        "score": score,
        "before": remaining,
        "rid": run_id,
        "outcome": outcome,
        "duration": test["duration"],
        "message": message,
        "after": after,
    })

    # Link a failed test to its suspected failure mode.
    if suspected_fid:
        graph.query("""
            MATCH (run:TestRun {id:$rid})
            MATCH (f:FailureMode {id:$fid})
            MERGE (run)-[:SUSPECTS]->(f)
        """, params={
            "rid": run_id,
            "fid": suspected_fid
        })

    print(f"RESULT: {outcome} - {message}")
    print(f"SAVED TO FALKORDB | Remaining: {after} min")

    # Re-read graph state and calculate next recommendation.
    next_context = load_context(graph, args.session)
    next_selection = choose_test(next_context, after)

    if next_selection:
        next_score, next_id, next_test = next_selection
        print(
            f"NEXT: {next_id} - {next_test['name']} | "
            f"Score: {next_score:.3f}"
        )
    else:
        print("NEXT: No eligible test")


if __name__ == "__main__":
    main()
