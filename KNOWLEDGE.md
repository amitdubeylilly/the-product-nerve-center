# PM Agent Challenge Knowledge Base

## Challenge Snapshot

- Domain: Product planning and execution decision support.
- Runtime: MCP server over stdio.
- Language: Python (starter includes mcp and pydantic).
- Entrypoint contract: olympics.json -> server.py.
- Required tools: prioritize_backlog, analyze_feedback, assess_capacity, map_dependencies.

## Data Contract

- Evaluation mounts data at PM_AGENT_DATA.
- Local fallback is ./data.
- Schema is stable, values differ at grading time.

## Available Local Files

- product_backlog.json
- customer_feedback.json
- sprint_history.json
- sample_roster.json (tiny local-only fallback)
- sample_dependencies.json (tiny local-only fallback)

## Data Dictionary Highlights

Backlog item fields include:

- id, status, priority, effort_points
- business_value_score, confidence_score
- tags, dependencies, squad_assignment

Feedback fields include:

- customer_tier, customer_status, arr
- source, date, text, sentiment_score

Sprint history includes:

- planned/completed points
- completed/carried items
- notes context

## Oracle-Discovered Areas

Not directly provided as full dataset files for grading:

- Capacity rule behind available_points
- Dependency graph behavior beyond direct edges

Oracle endpoints used only for discovery:

- capacity_oracle(engineer_id)
- capacity_oracle_roster()
- dependency_oracle(item_id)

## Current Sample Data Signals (Local Only)

- Active backlog items (planned + proposed + in_progress): 27
- Status counts: done=8, in_progress=10, planned=12, proposed=5
- Priority counts: P0=6, P1=16, P2=10, P3=3
- Feedback entries: 90
- Feedback by tier: enterprise=21, mid_market=49, startup=20
- Feedback by source: support_ticket=43, nps_survey=27, user_interview=17, sales_call=3
- Sprint history entries: 6 (latest sample sprint S-46, velocity 36, carry_over 4)

These values are for orientation only and must not be hardcoded.

## Grading-Sensitive Behaviors

- Investigation rigor is part of scoring.
- Tool descriptions and error handling affect reliability in orchestration.
- Solutions should be data-driven and generalizable, not sample-specific.

## Recommended Engineering Approach

- Keep formulas and ranking weights explicit and testable.
- Separate data loading, scoring logic, and tool wrappers.
- Add deterministic tie-breakers in ranking to avoid unstable output.
- Build unit tests around synthetic fixtures, including edge cases:
  - missing optional fields
  - zero ARR and trial customers
  - unknown dependency targets
  - circular dependency detection
