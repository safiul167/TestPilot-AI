
# TestPilot AI — Graph Architecture

## 1. Purpose

TestPilot AI is a graph-powered automotive ECU
test-planning prototype.

FalkorDB stores:
- Engineering entities and their relationships
- Test coverage and prerequisites
- Test execution history
- Agent decisions
- Suspected failure modes

All engineering data and test outcomes are synthetic.

## 2. Technology Architecture

Streamlit Dashboard
        |
        v
Python Test Planning Agent
        |
        +---- Graph Queries ----> FalkorDB
        |
        +---- Test Simulator
        |
        +---- Persistent Results --> FalkorDB

The Python agent uses FalkorDB through its official
Python client and Cypher queries.

## 3. Engineering Graph Model

Node types:

| Label | Description |
|---|---|
| ECU | Automotive electronic control unit |
| Subsystem | ECU hardware subsystem |
| Test | Validation test and duration |
| FailureMode | Possible failure mechanism |
| Requirement | Engineering verification requirement |
| Session | Persistent validation session |
| TestRun | Individual synthetic test outcome |
| Decision | Agent-selected test and score |

Relationships:

| From | Relationship | To |
|---|---|---|
| ECU | CONTAINS | Subsystem |
| Subsystem | HAS_TEST | Test |
| Test | DETECTS | FailureMode |
| FailureMode | AFFECTS | Requirement |
| Test | REQUIRES | Test |
| Session | HAS_RUN | TestRun |
| TestRun | FOR_TEST | Test |
| Session | HAS_DECISION | Decision |
| Decision | SELECTS | Test |
| TestRun | SUSPECTS | FailureMode |

REQUIRES points from the dependent test to
its prerequisite.

SUSPECTS represents a hypothesis, not a
confirmed root cause.

## 4. Initial Synthetic Dataset

- 1 ADAS Camera ECU
- 4 subsystems
- 8 validation tests
- 6 failure modes
- 6 requirements

Initial graph:
- 25 nodes
- 32 relationships

Session execution adds further nodes
and relationships.

## 5. Graph-Powered Decision Logic

For each eligible test:

Priority = SUM(risk_weight * detection_probability
               * concern_multiplier) / duration

The concern multiplier is:
- 2.0 for previously suspected failure modes
- 1.0 otherwise

A test is eligible only if:
- It has not already been executed in the session
- All its prerequisites have passed
- Its duration fits the remaining budget

The agent selects the highest-scoring eligible test.
Tie-breaking uses test ID.

This is a greedy heuristic, not a globally
optimal test scheduling algorithm.

## 6. Persistent Agent Workflow

1. Load the session from FalkorDB.
2. Retrieve test coverage and prerequisites.
3. Retrieve past outcomes and suspected failures.
4. Calculate eligible test priorities.
5. Select and execute a synthetic test.
6. Store the decision and outcome in FalkorDB.
7. Update the remaining session budget.
8. Recalculate the next recommendation.

The session state survives Python and
Streamlit application restarts while
FalkorDB storage remains available.

## 7. Why FalkorDB Is Essential

FalkorDB is the source of truth for:
- Test-to-failure coverage
- Engineering requirement relationships
- Test execution dependencies
- Session memory
- Agent decisions and investigation concerns

Removing FalkorDB prevents the current
agent workflow from retrieving the evidence
and session history needed for planning.

The graph is used for decisions, not only
for visualization.

## 8. Demonstration

Synthetic scenario:

1. Initial recommendation: TEST-002
2. TEST-002 reports FAIL
3. The session records suspected FM-002
4. The agent replans and recommends TEST-001
5. TEST-001 reports PASS
6. The agent recommends TEST-005

These transitions demonstrate
graph-dependent decision changes.

## 9. Limitations

- Synthetic test outcomes only
- No connection to physical ECU test equipment
- No ISO 26262 compliance claim
- No verified root-cause diagnosis
- No globally optimal schedule guarantee
- Current agent uses deterministic graph-based
  reasoning rather than an LLM
