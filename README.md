
# TestPilot AI

Graph-Powered Autonomous Automotive ECU Test Planning

## Hackathon
Graph Hacks 2026 — WeMakeDevs × FalkorDB

Primary track: Agents That Act on Connected Data

## Problem
Automotive ECU validation requires engineers to choose tests
under limited time budgets while considering risk coverage,
test dependencies, and previous results.

## Solution
TestPilot AI uses FalkorDB as its central context layer.

The application:
1. Retrieves engineering relationships from FalkorDB.
2. Calculates test priorities using risk and detection scores.
3. Checks test prerequisites and remaining time.
4. Executes deterministic synthetic test scenarios.
5. Saves decisions and results in FalkorDB.
6. Replans automatically using previous observations.

## Technology
- Python 3.12
- FalkorDB
- Cypher
- Streamlit
- Docker Compose
- Pytest

## Graph Data Model
Node labels:
ECU, Subsystem, Test, FailureMode, Requirement,
Session, Decision, TestRun

Relationship types:
CONTAINS, HAS_TEST, DETECTS, AFFECTS, REQUIRES,
HAS_DECISION, SELECTS, HAS_RUN, FOR_TEST, SUSPECTS

FalkorDB is essential for retrieving test dependencies,
risk coverage, and persistent decision history.

## Enhanced Interactive Dashboard

The Streamlit application provides:

- Mission Control with ECU validation status
- One-click execution of all eligible synthetic tests
- Interactive engineering evidence-path visualization
- Graph What-If Lab for non-destructive evidence ablation
- Persistent session history and JSON evidence export
- 60-minute constrained and 120-minute full-test scenarios

The What-If Lab temporarily excludes one FalkorDB-derived
DETECTS relationship in memory and recalculates test
priorities. It does not modify the stored graph.

All outcomes are synthetic. The application does not
operate physical ECU test equipment.


## Technical Documentation

- [Graph architecture and data model](docs/graph_model.md)
- [FalkorDB Cypher queries](docs/queries.cypher)

The graph stores test coverage, prerequisite
dependencies, persistent validation history,
and agent decisions.

The application uses these relationships to
select and replan synthetic ECU tests.


## Installation

Requirements:
- Python 3.12
- Docker Desktop
- Git

Clone the repository:

```powershell
git clone https://github.com/safiul167/TestPilot-AI.git
cd TestPilot-AI
```

Start FalkorDB:

```powershell
docker compose up -d
```

Create and install the Python environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Initialize the graph on a fresh database only:

```powershell
.\.venv\Scripts\python.exe src\seed_graph.py
.\.venv\Scripts\python.exe src\seed_validation_data.py
```

Run automated tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent.py -v
```

Launch the application:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501


## Demo
Create a new session with a 60-minute budget.

The agent initially recommends Power Rail Monitoring.
A synthetic failure changes the next recommendation.
Test outcomes and agent decisions remain stored in FalkorDB.

## Important Limitations
- Synthetic engineering dataset
- No connection to physical ECU hardware
- No actual diagnostic or safety certification
- Greedy test-priority heuristic, not globally optimal scheduling
- Local demonstration deployment

## AI Assistance Disclosure
AI coding assistance was used for architecture discussions,
code drafting, debugging guidance, and documentation.
The participant implemented, executed, and verified the
submitted application and is responsible for its technical
decisions.

## License
To be determined by the repository owner.
