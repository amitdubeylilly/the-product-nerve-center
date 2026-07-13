# Approach Summary — DevPulse PM Agent

This document answers the six Technical Decision Log prompts for the final implementation.

The server exposes four MCP tools as thin wrappers in `server.py`, with business logic in `tools/*.py`:
- Judgment: `prioritize_backlog`, `analyze_feedback`
- Discovery-derived: `assess_capacity`, `map_dependencies`

Runtime is oracle-free: data is loaded from `PM_AGENT_DATA` (fallback `./data`) and the discovered rules are implemented directly in code.

## 1. Schema Rationale

I separated wrapper contracts from computation logic to keep tool calling stable and logic testable. Inputs are composable: filters are explicit objects, not hidden free-form text. Outputs are JSON-first and machine-usable, with consistent keys, summary fields, and rationale artifacts (for example: `flags`, `warnings`, `score_components`, `bias_warnings`, `critical_path`).

Rejected alternatives:
- Free-form textual outputs (hard to chain reliably).
- One tool per narrow use case (too fragmented).
- Deep optional nesting in schemas (tool-call ambiguity).

## 2. Investigation and Trap Handling

During discovery, I queried pm-data-agent, changed one variable at a time, and then froze the resulting rules.

Capacity rule proven:
```
allocated = total_capacity_points * (allocation_percent / 100)
effective = allocated * ((sprint_days - pto_days) / sprint_days)
available = max(0, effective - carry_over_points)
```

Key findings:
- 0% allocation engineers are excluded from squad totals (not just counted as 0).
- PTO is multiplicative prorating, not point subtraction.
- Carry-over subtracts last and result is floored at 0.

Dependency findings:
- `blocks` edges define critical path.
- `soft` edges are traversed but excluded from critical path scoring.
- `external` edges carry external delivery risk via ETA state.

Schema traps handled via normalization:
- Capacity supports either scalar `carry_over_points` or carry-over item lists.
- Field aliases are mapped (`engineer_id`/`name`, `allocation_percent`/`sprint_allocation_percent`, `source_item_id`/`item_id`, etc.).

## 3. Tool Description Craft

Descriptions are written as operational prompts for Claude: when to use each tool, parameter intent, output contract, and caveats.

Examples:
- `prioritize_backlog` documents filters object semantics and unknown-method fallback to RICE.
- `assess_capacity` includes the exact formula for explainability.
- `map_dependencies` explains risk flags and critical-path behavior for downstream reasoning.

## 4. Failure Modes

- Missing required core files (`product_backlog`, `customer_feedback`, `sprint_history`) fails fast at startup with remediation.
- Missing optional files (`team_roster`, `dependency_map`) degrades to empty lists (no crash).
- `assess_capacity` validates `sprint_days > 0`, caps PTO at sprint length, and returns structured errors.
- `map_dependencies` validates `item_ids`/`max_depth`, detects cycles via DFS, and returns cycle paths.
- `prioritize_backlog` handles unknown methods via deterministic fallback and flags blocked or under-specified items.
- `analyze_feedback` removes near-duplicates, surfaces bias warnings, and preserves churn signal as explicit flags.
- Deterministic sort keys are used throughout for stable grading.

## 5. Custom Insight

For AI-facing tools, composability beats verbosity. Reliable orchestration comes from stable schemas, deterministic ordering, and explicit rationale fields instead of prose-only explanations. I optimized judgment tools for defensible heuristics and bias visibility, and discovery tools for rule fidelity and assumption guardrails.

## 6. Production Scaling

For multi-team scale, I would add:
- Typed ingestion and schema versioning with audit metadata (`data_version`, `loaded_at`, `source_hash`).
- Pagination and stricter API contracts (`strict_mode`, `assumptions_used`, `filters_applied`).
- Standard error envelopes, per-tool timings, and dataset drift/contract regression tests.

Candidate future tools: `what_if_capacity_change`, `dependency_impact_diff`, `backlog_health_report`.

I would keep final strategy tradeoffs and staffing commitments human-reviewed.

---

Validation: 195 tests pass at 100% branch coverage; lint/format/type checks are clean.
