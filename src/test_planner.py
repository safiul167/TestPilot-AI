
import argparse
from collections import defaultdict
from falkordb import FalkorDB


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--budget", type=int, default=60,
        help="Remaining test time in minutes"
    )
    parser.add_argument(
        "--completed", nargs="*", default=[],
        help="IDs of tests assumed completed (what-if only)"
    )
    args = parser.parse_args()

    if args.budget <= 0:
        raise ValueError("Time budget must be positive")

    completed = set(args.completed)

    # Connect to the existing graph.
    db = FalkorDB(host="127.0.0.1", port=6379)
    graph = db.select_graph("testpilot_ai")

    # Get test information and engineering evidence.
    rows = graph.ro_query("""
        MATCH (t:Test)-[d:DETECTS]->(f:FailureMode)
        MATCH (f)-[:AFFECTS]->(r:Requirement)
        RETURN t.id, t.name, t.duration_min,
               f.id, f.risk_weight,
               d.detection_probability, r.id
    """).result_set

    tests = {}

    for tid, name, duration, fid, risk, prob, rid in rows:
        if tid not in tests:
            tests[tid] = {
                "name": name,
                "duration": int(duration),
                "evidence": []
            }

        tests[tid]["evidence"].append({
            "failure": fid,
            "risk": float(risk),
            "probability": float(prob),
            "requirement": rid
        })

    # Read graph-defined test prerequisites.
    prerequisite_rows = graph.ro_query("""
        MATCH (t:Test)-[:REQUIRES]->(p:Test)
        RETURN t.id, p.id
    """).result_set

    prerequisites = defaultdict(set)

    for test_id, required_id in prerequisite_rows:
        prerequisites[test_id].add(required_id)

    if len(tests) != 8:
        raise RuntimeError(
            f"Expected 8 seeded tests, found {len(tests)}"
        )

    recommendations = []
    blocked = []

    for tid, test in tests.items():
        if tid in completed:
            continue

        missing = prerequisites[tid] - completed

        if missing:
            blocked.append((tid, sorted(missing)))
            continue

        if test["duration"] > args.budget:
            continue

        # Graph-derived risk coverage per minute.
        benefit = sum(
            item["risk"] * item["probability"]
            for item in test["evidence"]
        )

        score = benefit / test["duration"]

        recommendations.append({
            "id": tid,
            "name": test["name"],
            "duration": test["duration"],
            "score": score,
            "evidence": test["evidence"]
        })

    recommendations.sort(
        key=lambda x: (-x["score"], x["id"])
    )

    print("\n=== TESTPILOT AI ===")
    print(f"Time budget: {args.budget} minutes")
    print(f"Completed (what-if): {sorted(completed)}")
    print(f"Eligible tests: {len(recommendations)}")

    print("\nPrioritized tests:")
    for index, item in enumerate(recommendations, 1):
        print(
            f"{index}. {item['id']} "
            f"{item['name']} | "
            f"{item['duration']} min | "
            f"Score: {item['score']:.3f}"
        )

    print("\nBlocked prerequisites:")
    for tid, missing in sorted(blocked):
        print(f"{tid} requires {', '.join(missing)}")

    if recommendations:
        selected = recommendations[0]

        print("\nRECOMMENDED NEXT TEST:")
        print(selected["id"], selected["name"])
        print("Score:", round(selected["score"], 3))

        print("\nGraph evidence:")
        for item in selected["evidence"]:
            print(
                f"  {item['failure']} -> "
                f"{item['requirement']} | "
                f"Risk={item['risk']}, "
                f"Detection={item['probability']}"
            )
    else:
        print("\nNo eligible test for this budget.")


if __name__ == "__main__":
    main()
