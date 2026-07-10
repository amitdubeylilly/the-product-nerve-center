# PM Agent Challenge Skill Guide

## Objective
Build an MCP server that exposes exactly four tools:
- prioritize_backlog
- analyze_feedback
- assess_capacity
- map_dependencies

The implementation must work on any mounted dataset with the same schema.

## Hard Requirements
- Read data from PM_AGENT_DATA, fallback to ./data for local dev.
- Do not hardcode IDs, names, fixed counts, or sample values.
- Do not call Nimbus Oracle from submitted server code.
- Keep tool names exactly as required by olympics.json.
- Implement exact input schema from the official challenge brief.

## Tool Split
- Data-file tools:
  - prioritize_backlog
  - analyze_feedback
- Oracle-discovery tools:
  - assess_capacity
  - map_dependencies

Use the oracle only during discovery and hypothesis testing, then encode the discovered rules as local logic.

## Investigation Workflow (Scored)
1. Establish baseline query output.
2. Change one variable at a time.
3. Record hypothesis, expected output, and observed output.
4. Refine formula/graph rule.
5. Validate with counterexamples.

For capacity, isolate impact of:
- allocation_percent
- pto_days
- carry_over_points
- skill fit constraints

For dependencies, trace from one item through returned targets until leaf nodes:
- classify hard blockers vs soft links vs external dependencies
- capture external ETA risk states (date, TBD, null)

## Implementation Pattern
1. In server.py, load JSON once at startup from DATA_DIR.
2. Put business logic in tools/*.py functions.
3. Keep MCP tool functions thin wrappers over pure logic.
4. Return stable JSON-friendly structures with explicit fields.
5. Raise clear ValueError messages for invalid input.

## Suggested Output Design
- prioritize_backlog:
  - ranked_items[] with score breakdown and rationale
  - summary fields (counts by priority/risk)
- analyze_feedback:
  - themes[] with counts and impact
  - urgency signals and customer-segment cuts
- assess_capacity:
  - engineer_capacity[] and squad totals
  - warnings for overload, skill mismatch, carry-over pressure
- map_dependencies:
  - direct and transitive edges
  - blocker paths, cycle flags, and external risk annotations

## Local Validation Checklist
- Server starts with python server.py.
- All four tool names appear and are invokable.
- Works when PM_AGENT_DATA points to alternate directory.
- No network/oracle calls at runtime.
- Handles missing files and malformed inputs gracefully.

## Common Failure Modes
- Reading data from a hardcoded local folder instead of DATA_DIR.
- Overfitting formulas to sample files rather than discovered rules.
- Returning unstructured text instead of machine-usable JSON shape.
- Ignoring external dependency ETA uncertainty in risk logic.
- Forgetting to remove example-only assumptions from tool code.