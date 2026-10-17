"""TestPilot AI | Mission Control + non-destructive Graph What-If Lab.

Drop-in replacement for the hackathon MVP app.py. The existing graph schema,
run_agent.py and its deterministic simulator are intentionally unchanged.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import pandas as pd
from falkordb import FalkorDB

from src.run_agent import load_context, choose_test, session_budget
from src.what_if import rank_candidates, comparison

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="TestPilot AI | Mission Control", page_icon="🧪", layout="wide")

st.markdown("""
<style>
.stApp { background: #091120; color: #eaf0ff; }
[data-testid="stSidebar"] {background: #101d32;}
[data-testid="stMetric"] {
  background: linear-gradient(135deg,#172643,#121c34);
  border: 1px solid #354b77; border-radius: 14px;
  padding: 16px 18px;
}
[data-testid="stMetricValue"] {color: #80e5ff;}
.hero {
  padding: 24px 28px; margin: 6px 0 22px;
  background: linear-gradient(115deg,#25316b,#116c78 85%);
  border: 1px solid #5272a8; border-radius: 18px;
}
.hero h1 { color: #fff; margin: 0 0 7px; font-size: 2.2rem; }
.hero p { color: #e4efff; margin: 0; }
.note {
  background: #151e34; border: 1px solid #344f78;
  padding: 12px 16px; border-radius: 11px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🧪 TestPilot AI · Mission Control</h1>
<p>Graph-powered ECU validation · Explainable decisions · Persistent FalkorDB memory</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("⚙️ Validation session")
if "testpilot_session_id" not in st.session_state:
    st.session_state["testpilot_session_id"] = "DEMO-FULL-001"

session_id = st.sidebar.text_input("Session ID", key="testpilot_session_id").strip()
budget = int(st.sidebar.number_input("Initial budget (minutes)", min_value=1, max_value=240, value=120, step=1))
st.sidebar.caption("Use a NEW session ID for a new budget. Existing sessions retain their saved budget and test history.")
st.sidebar.markdown("**Modes:** 60 min = constrained planning; 120 min = complete 8-test demonstration.")
st.sidebar.warning("Only synthetic tests are executed. No connection to real ECU hardware.")

if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", session_id):
    st.error("Session ID must have 1–60 letters, digits, hyphens or underscores.")
    st.stop()

try:
    # Do not cache the connection over server restarts. All state lives in FalkorDB.
    graph = FalkorDB(host="127.0.0.1", port=6379).select_graph("testpilot_ai")
    remaining = session_budget(graph, session_id, budget)
    context = load_context(graph, session_id)
    selected = choose_test(context, remaining)
    history_rows = graph.ro_query("""
        MATCH (s:Session {id:$sid})-[:HAS_RUN]->(r:TestRun)-[:FOR_TEST]->(t:Test)
        RETURN t.id, t.name, r.outcome, r.duration_min
        ORDER BY t.id
    """, params={"sid": session_id}).result_set
    decision_rows = graph.ro_query("""
        MATCH (s:Session {id:$sid})-[:HAS_DECISION]->(d:Decision)-[:SELECTS]->(t:Test)
        RETURN t.id, d.score, d.remaining_before
    """, params={"sid": session_id}).result_set
except Exception as exc:
    st.error("FalkorDB connection or graph query failed. Check `docker compose ps`, then reload.")
    st.exception(exc)
    st.stop()

tests, dependencies, executed, passed, suspected = context
history = [
    {"Test ID": tid, "Test name": name, "Outcome": outcome, "Duration (min)": int(duration)}
    for tid, name, outcome, duration in history_rows
]
result_map = {r["Test ID"]: r["Outcome"] for r in history}
failed_count = sum(row["Outcome"] == "FAIL" for row in history)
all_duration = sum(test["duration"] for test in tests.values())

m1, m2, m3, m4 = st.columns(4)
m1.metric("⏳ Time left", f"{remaining} min")
m2.metric("🧩 Tests completed", f"{len(executed)}/{len(tests)}")
m3.metric("⚠️ Failed tests", str(failed_count))
m4.metric("🔎 Unresolved concerns", str(len(suspected)))
st.progress(len(executed) / max(1, len(tests)), text=f"Validation progress · {len(executed)} of {len(tests)} tests executed")


def run_one():
    """Use the verified command-line agent; do not duplicate write logic."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "src" / "run_agent.py"),
         "--session", session_id, "--budget", str(budget)],
        cwd=str(ROOT), capture_output=True, text=True,
        timeout=35, check=True,
    )
    return proc.stdout


def execute_next():
    try:
        log = run_one()
        st.session_state["testpilot_log"] = {"session": session_id, "output": log}
        st.rerun()
    except Exception as exc:
        st.error(f"Test execution failed: {exc}")


def execute_all():
    logs = []
    meter = st.progress(0, text="Running synthetic tests...")
    status = st.empty()
    try:
        for i in range(len(tests)):
            # Query live DB state BEFORE each run. Stop when there is no eligible test.
            latest = load_context(graph, session_id)
            current_budget_rows = graph.ro_query(
                "MATCH (s:Session {id:$sid}) RETURN s.remaining_minutes",
                params={"sid": session_id},
            ).result_set
            left = int(current_budget_rows[0][0])
            if choose_test(latest, left) is None:
                break
            status.info(f"Running synthetic test {i+1} (remaining {left} min)...")
            logs.append(run_one())
            meter.progress((i + 1) / max(1, len(tests)), text=f"Executed {i+1} synthetic tests in this run")
        st.session_state["testpilot_log"] = {"session": session_id, "output": "\n".join(logs)}
        st.rerun()
    except Exception as exc:
        st.session_state["testpilot_log"] = {"session": session_id, "output": "\n".join(logs)}
        status.error(f"Stopped after {len(logs)} completed runs. Error: {exc}")
        st.exception(exc)


tab_control, tab_graph, tab_whatif, tab_history = st.tabs([
    "🚀 Mission Control", "🕸️ Evidence Explorer", "🧠 Graph What-If Lab", "📜 History & Export"
])

with tab_control:
    if budget < all_duration and not executed:
        st.warning(f"All eight tests require {all_duration} simulated minutes. Your new session budget is {budget}, so some tests will remain pending.")
    st.subheader("Next graph-grounded action")
    if selected:
        score, tid, test = selected
        st.success(f"🎯 Recommended: **{tid} — {test['name']}**")
        c1, c2 = st.columns(2)
        c1.metric("Priority", f"{score:.3f}")
        c2.metric("Execution time", f"{test['duration']} min")
        evidence_rows = [
            {"Failure mode": fid, "Requirement": rid, "Risk": risk,
             "Detection probability": prob, "Concern multiplier": 2 if fid in suspected else 1}
            for fid, risk, prob, rid in test["links"]
        ]
        st.dataframe(evidence_rows, hide_index=True, width="stretch")
        a, b = st.columns(2)
        with a:
            if st.button("▶ Execute ONE synthetic test", type="primary", width="stretch"):
                execute_next()
        with b:
            if st.button("⚡ Execute ALL remaining eligible tests", width="stretch"):
                execute_all()
    else:
        st.info("No eligible tests remain in this session. It may be complete, time-limited, or blocked by prerequisites.")

    st.subheader("Eight-test validation matrix")
    catalogue = []
    for tid, test in sorted(tests.items()):
        missing = dependencies[tid] - passed
        state = result_map.get(tid, "BLOCKED" if missing else "PENDING")
        catalogue.append({"Test": tid, "Description": test["name"],
                          "Minutes": test["duration"], "Status": state,
                          "Prerequisite": ", ".join(sorted(dependencies[tid])) or "None"})
    st.dataframe(catalogue, hide_index=True, width="stretch")

    log = st.session_state.get("testpilot_log")
    if log and log.get("session") == session_id:
        with st.expander("Latest synthetic execution log", expanded=False):
            st.code(log.get("output", ""), language="text")

with tab_graph:
    st.subheader("Engineering evidence and dependency paths")
    st.caption("Every node/edge is sourced from the FalkorDB graph used by the planner.")
    chosen_id = st.selectbox("Inspect test", sorted(tests),
                             format_func=lambda tid: f"{tid} · {tests[tid]['name']}")
    inspected = tests[chosen_id]
    lines = [
        'digraph evidence {',
        'rankdir=LR; bgcolor="transparent"; pad="0.35"; nodesep="0.55";',
        'node [shape=box, style="rounded,filled", fillcolor="#24375b", color="#6dd6ff", fontcolor="white", fontname="Arial"];',
        'edge [color="#a7b8da", fontcolor="#d8e4ff", fontsize="10"];',
        f'"{chosen_id}" [label="{chosen_id}: {inspected["name"]}", fillcolor="#3746a2"];',
    ]
    for fid, risk, prob, rid in inspected["links"]:
        lines.extend([
            f'"{fid}" [label="{fid} · risk {risk:g}", fillcolor="#9d4c7f"];',
            f'"{rid}" [label="{rid}", fillcolor="#267b76"];',
            f'"{chosen_id}" -> "{fid}" [label="DETECTS p={prob:g}"];',
            f'"{fid}" -> "{rid}" [label="AFFECTS"];',
        ])
    for pre in sorted(dependencies[chosen_id]):
        lines.append(f'"{chosen_id}" -> "{pre}" [label="REQUIRES", style=dashed, color="#f0bf70"];')
    lines.append('}')
    try:
        st.graphviz_chart("\n".join(lines), width="stretch")
    except Exception:
        st.warning("Graph rendering unavailable; underlying graph links are shown in the table below.")
    st.dataframe([{"Test": chosen_id, "Failure": f, "Requirement": r,
                   "Risk": risk, "Probability": prob}
                  for f, risk, prob, r in inspected["links"]],
                 hide_index=True, width="stretch")
    if dependencies[chosen_id]:
        st.info("Prerequisites: " + ", ".join(sorted(dependencies[chosen_id])))

with tab_whatif:
    st.subheader("🧠 Graph What-If Lab: one edge, different decision")
    st.markdown("<div class='note'>Try removing one <b>DETECTS</b> relationship <i>temporarily</i>. "
                "The agent recomputes test priorities using FalkorDB-derived data. "
                "No real graph nodes, edges or session results are modified.</div>",
                unsafe_allow_html=True)
    hypothetical_fresh = st.toggle("Use a fresh hypothetical session (ignores executed-test history)", value=True)
    if hypothetical_fresh:
        hypothetical = (tests, dependencies, set(), set(), set())
        default_budget = 120
    else:
        hypothetical = context
        default_budget = max(1, remaining)
    hypothetical_budget = st.slider("What-if time budget", 1, 180, default_budget)
    test_options = sorted(tests)
    test_idx = test_options.index("TEST-002") if "TEST-002" in test_options else 0
    change_test = st.selectbox("Test evidence to alter", test_options, index=test_idx,
                              format_func=lambda t: f"{t} · {tests[t]['name']}")
    edges = tests[change_test]["links"]
    default_edge_idx = next((i for i, row in enumerate(edges) if row[0] == "FM-002"), 0)
    fid, risk, prob, rid = st.selectbox(
        "Remove this evidence relationship (hypothetically)", edges,
        index=default_edge_idx,
        format_func=lambda item: f"{change_test} DETECTS {item[0]} (p={item[2]:g})",
    )
    baseline, altered = comparison(hypothetical, hypothetical_budget, change_test, fid)
    def headline(rows):
        return (f"{rows[0]['test_id']} · {rows[0]['name']}", rows[0]['score']) if rows else ("No eligible test", 0)
    before_title, before_score = headline(baseline)
    after_title, after_score = headline(altered)
    left, right = st.columns(2)
    left.info(f"**Baseline decision**\n\n{before_title}\n\nScore: **{before_score:.3f}**")
    right.success(f"**After graph-edge removal**\n\n{after_title}\n\nScore: **{after_score:.3f}**")
    if baseline and altered and baseline[0]["test_id"] != altered[0]["test_id"]:
        st.warning("🔀 The top recommendation CHANGED when the graph evidence connection was removed.")
    else:
        st.caption("The leading test did not change in this scenario. Compare its score or try another edge.")
    score_lookup = {r["test_id"]: r["score"] for r in altered}
    compared = [
        {"Test": row["test_id"], "Baseline score": round(row["score"], 3),
         "After removal": round(score_lookup.get(row["test_id"], 0), 3)}
        for row in baseline
    ]
    st.dataframe(compared, hide_index=True, width="stretch")
    st.caption("The counterfactual is performed in Python on the graph context fetched from FalkorDB; it is not a graph write or a validated causal intervention.")

with tab_history:
    st.subheader("Persistent execution history")
    if history:
        st.dataframe(history, hide_index=True, width="stretch")
        st.bar_chart(pd.DataFrame(history).set_index("Test ID"), y="Duration (min)", color="#52d9e8")
    else:
        st.info("No tests in this session yet. Use Mission Control to run a synthetic test.")
    if decision_rows:
        st.subheader("Stored decisions")
        drows = [{"Test": tid, "Priority": round(float(score), 3), "Remaining before (min)": int(before)}
                 for tid, score, before in decision_rows]
        st.dataframe(sorted(drows, key=lambda r: -r["Remaining before (min)"]),
                     hide_index=True, width="stretch")
    report = {
        "project": "TestPilot AI",
        "session": session_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "synthetic_only": True,
        "initial_budget": budget,
        "remaining_budget": remaining,
        "executed": len(executed),
        "history": history,
        "decisions": [{"test_id": t, "score": s, "remaining_before": b}
                      for t, s, b in decision_rows],
        "suspected_failure_modes": sorted(suspected),
    }
    st.download_button("⬇ Download evidence report (JSON)",
                       data=json.dumps(report, indent=2),
                       file_name=f"{session_id}_report.json", mime="application/json")

st.caption("Hackathon prototype · Graph-powered deterministic decisions · Synthetic ECU data only · No physical device testing")
