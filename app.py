
"""TestPilot AI - Streamlit hackathon MVP."""

import subprocess
import sys
from pathlib import Path

import streamlit as st
from falkordb import FalkorDB

from src.run_agent import (
    load_context,
    choose_test,
    session_budget,
)

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="TestPilot AI",
    page_icon="🧪",
    layout="wide",
)

st.title("TestPilot AI")
st.caption(
    "Graph-powered autonomous ECU test planning "
    "| FalkorDB | Synthetic demonstration"
)


@st.cache_resource
def get_graph():
    db = FalkorDB(host="127.0.0.1", port=6379)
    return db.select_graph("testpilot_ai")


st.sidebar.header("Validation Session")

session_id = st.sidebar.text_input(
    "Session ID", value="DEMO-UI-001"
).strip()

budget = st.sidebar.number_input(
    "Initial time budget (minutes)",
    min_value=1,
    max_value=240,
    value=60,
)

st.sidebar.info(
    "The initial budget applies only when a new "
    "session is created. Existing sessions resume "
    "from their saved graph state."
)

if not session_id:
    st.warning("Enter a session ID.")
    st.stop()

try:
    graph = get_graph()

    remaining = session_budget(
        graph, session_id, int(budget)
    )
    context = load_context(graph, session_id)
    selection = choose_test(context, remaining)

    history_rows = graph.ro_query("""
        MATCH (s:Session {id:$sid})
              -[:HAS_RUN]->(r:TestRun)
              -[:FOR_TEST]->(t:Test)
        RETURN t.id, t.name,
               r.outcome, r.duration_min
        ORDER BY t.id
    """, params={"sid": session_id}).result_set

except Exception as exc:
    st.error("Unable to load the FalkorDB session.")
    st.exception(exc)
    st.stop()


executed = context[2]
suspected = context[4]

c1, c2, c3, c4 = st.columns(4)

c1.metric("Remaining time", f"{remaining} min")
c2.metric("Tests completed", f"{len(executed)}/8")
c3.metric(
    "Failed tests",
    sum(row[2] == "FAIL" for row in history_rows),
)
c4.metric("Suspected failure modes", len(suspected))

st.divider()

st.subheader("Agent Recommendation")

if selection:
    score, test_id, test = selection

    st.success(
        f"Next test: {test_id} — {test['name']}"
    )

    st.write(
        f"**Priority score:** {score:.3f} | "
        f"**Duration:** {test['duration']} minutes"
    )

    st.write("**Graph-backed evidence**")

    evidence = [
        {
            "Test": test_id,
            "Failure mode": fid,
            "Requirement": rid,
            "Risk weight": risk,
            "Detection probability": prob,
            "Concern multiplier":
                2.0 if fid in suspected else 1.0,
        }
        for fid, risk, prob, rid in test["links"]
    ]

    st.dataframe(
        evidence,
        use_container_width=True,
        hide_index=True,
    )

    execute = st.button(
        "Execute next synthetic test",
        type="primary",
    )

    if execute:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "src" / "run_agent.py"),
                    "--session",
                    session_id,
                    "--budget",
                    str(int(budget)),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )

            st.session_state["last_run"] = {
                "session": session_id,
                "output": result.stdout,
            }

            st.rerun()

        except Exception as exc:
            st.error("Test execution failed.")
            st.exception(exc)

else:
    st.info(
        "No eligible test remains for the current "
        "time budget and prerequisites."
    )


last_run = st.session_state.get("last_run")

if last_run and last_run["session"] == session_id:
    with st.expander(
        "Latest agent execution log", expanded=True
    ):
        st.code(last_run["output"], language="text")


st.divider()
st.subheader("Persistent Test History")

if history_rows:
    history = [
        {
            "Test ID": tid,
            "Test name": name,
            "Outcome": outcome,
            "Duration (min)": duration,
        }
        for tid, name, outcome, duration in history_rows
    ]

    st.dataframe(
        history,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.write("No tests have been executed in this session.")

st.caption(
    "All test outcomes are synthetic. This application "
    "does not control physical automotive hardware."
)
