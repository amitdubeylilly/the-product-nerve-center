# Approach Summary — DevPulse PM Agent

This document answers the six Technical Decision Log prompts. It is written against the final code and repository state.

The server exposes four MCP tools — `prioritize_backlog`, `analyze_feedback` (judgment) and `assess_capacity`, `map_dependencies` (discovery) — as thin wrappers in `server.py` over pure logic in `tools/*.py`. **All data is read from `PM_AGENT_DATA` (fallback `./data`); the server never calls the pm-data-agent oracle at runtime.** The capacity and dependency rules were reverse-engineered during the discovery phase and are embodied as standalone, deterministic code.

## 1. Schema Rationale

I split thin MCP wrappers (stable, LLM-friendly signatures) from pure business logic (testable, deterministic). 

Inputs: `prioritize_backlog` accepts direct controls (`method`, `squad_filter`, `include_done`, `top_n`) plus an optional `filters` object (`squad`, `status`, `tags`) so Claude can express intent in one payload. `analyze_feedback` takes composable filters (`customer_tier`, `source`, `time_range`, `include_churned`, `min_sentiment`) and a `group_by` of theme or customer. `assess_capacity` takes `squad`, `sprint_days`, `include_carry_over`, and optional skill-fit. `map_dependencies` takes `item_ids`, `max_depth`, and soft/external toggles.

Outputs: all tools return JSON-friendly dicts with explicit top-level keys, a summary block, and machine-usable fields — `ranked_items` + per-item flags; `themes`/`customers` + `bias_warnings` + `duplicate_ids_excluded`; `engineers` + `squad_totals` + `team_totals` + `capacity_formula`; per-item traces + `cycles` + `critical_path`.

Rejected alternatives: free-form text (hard for an orchestrator to chain); deeply nested optional branches (tool-call ambiguity); one tool per filter variation (fragments behavior, hurts composability).

## 2. Investigation and Trap Handling

Discovery ran in Claude Chat against the pm-data-agent, isolating one variable at a time, then froze the findings as code.

**Capacity** — from a baseline I isolated each variable:
- Sana (100%, 0 PTO, 0 carry) → 21.0 ⇒ base = `total_capacity_points` (21) × allocation.
- Otto (100%, 4 PTO) → 12.6 = 21 × (10−4)/10 ⇒ PTO prorates *multiplicatively* over a 10-day sprint, not as a point subtraction.
- Lux (50%, 2 PTO) → 8.4 = 21 × 0.5 × 0.8 ⇒ allocation and PTO compose.
- Rao (carry 5) → 16.0; Isa (carry 6+5) → 10.0 ⇒ carry-over is subtracted last and floored at 0.
- Vik (0%) → 0.0, flagged `zero_allocation` and **excluded** from squad totals (this answers "what does 0% mean for squad totals").

Frozen formula (per engineer, `sprint_days`=10):
```
allocated = total_capacity_points × (allocation_percent / 100)
effective = allocated × ((sprint_days − pto_days) / sprint_days)
available = max(0, effective − carry_over_points)
```
Squad/team totals sum only allocation>0 engineers. Re-running the logic on the discovered 8-person roster reproduced every oracle figure exactly (squads 54.1 / 35.2, team 89.3), which is my confidence check that the rule is right.

**Dependencies** — the dependency summary showed 12 edges (8 blocks, 2 soft, 2 external). Types get different treatment: `blocks` form the critical path; `soft` is traversable but excluded from the critical path; `external` carries `external_team`/`external_eta` and is risk-flagged by ETA state.

**Anomalies handled:**
- A 0%-allocation engineer must be *excluded* from squad capacity, not merely contribute 0.
- The oracle exposes carry-over as a list of in-progress items `{id, points, status}`, while the data dictionary documents an integer `carry_over_points`. `_normalize` accepts either (sums the item points or reads the int) and also maps `engineer_id`/`name`, `allocation_percent`/`sprint_allocation_percent`, `pto_days`/`pto_days_this_sprint`. The dependency normalizer likewise accepts `source_item_id`/`item_id`, `target_item_id`/`target_id`, `dependency_type`/`type`, so the tools work whichever schema the grader mounts.
- Backlog data contains unestimated items (`effort_points`=0), items with no customer signal, and the `executive-priority` tag — each handled explicitly (§4).

## 3. Tool Description Craft

Descriptions are operational guidance for Claude, not static API docs: each states when to use the tool, parameter intent, output shape, and behavioral caveats. Example: `prioritize_backlog` documents that `filters` accepts `squad`, `status`, and `tags` (string-or-list) and that unknown methods fall back to RICE — this nudges Claude to send one structured `filters` payload for intent like "planned growth items tagged security" instead of splitting context across arguments. `assess_capacity` embeds the capacity formula in its docstring for transparency, and `map_dependencies` names its risk flags and critical-path semantics so downstream reasoning can explain *why* an item is risky.

## 4. Failure Modes

- **Missing required files** (`product_backlog`/`customer_feedback`/`sprint_history`): startup exits with a path + remediation message.
- **Missing `team_roster`/`dependency_map`**: degrade to empty lists — never crash. `assess_capacity` returns empty engineers; `map_dependencies` returns no edges. At grading these are mounted in `PM_AGENT_DATA`; locally the tiny `sample_*` files stand in.
- **`assess_capacity`**: `sprint_days` ≤ 0 → structured error; PTO capped at sprint length.
- **`map_dependencies`**: `max_depth` < 1 and empty `item_ids` → structured errors at the impl level; the server wrapper pre-fills planned/in-progress items so an empty request still works; cycles are detected via DFS and returned with the full cycle path.
- **`prioritize_backlog`**: unknown method → RICE fallback with a `method_warning`; blocked items flagged (`blocked_by` vs `missing_dependency`) and optionally deprioritized; RICE Reach uses customer-feedback volume as the proxy; `executive-priority` is applied as a bounded boost *and* surfaced as a flag (never silently decisive).
- **`analyze_feedback`**: near-duplicates removed and reported as `duplicate_ids_excluded`; bias warnings for customer-volume skew, churned-signal dominance, and tier skew; churned feedback is flagged rather than silently dropped.
- **Determinism**: stable multi-key sorts throughout, so outputs line up with an answer key.

## 5. Custom Insight

Designing for AI use differs from designing dashboards. The best output is not the most verbose — it is the most *composable*: stable keys, explicit warnings, deterministic ordering, and clear failure contracts. I encoded rationale as fields (`flags`, `warnings`, `score_components`) rather than prose, and treated descriptions as behavioral prompts that steer tool selection and parameter shape. Judgment tools and discovery tools also need different optimizations: judgment tools need defensible heuristics and bias surfacing; discovery tools need rule fidelity and hard guardrails against assumptions.

## 6. Production Scaling

Across six teams I would evolve three areas. **Data layer:** replace startup-only JSON with a typed data-access layer (Pydantic models at ingestion), schema versioning, periodic refresh, and audit metadata (`data_version`, `loaded_at`, `source_hash`) in outputs. **Schemas/APIs:** add pagination/cursors for large feedback sets, consistent explainability fields (`assumptions_used`, `filters_applied`), and an optional `strict_mode` that fails on unknown enums instead of defaulting. **Reliability:** standardize error envelopes (`error_code`, `message`, `retryable`, `context`), add per-tool timing, and run contract + drift tests against multiple synthetic datasets. New tools: `what_if_capacity_change` (simulate PTO/allocation/carry-over), `dependency_impact_diff` (risk before/after backlog edits), `backlog_health_report` (stale/unestimated/no-signal trends). I would **not** automate final priority decisions that encode strategy tradeoffs (enterprise retention vs growth bets), customer-sensitive escalations, or staffing commitments without manager review — the tools compress analysis time, they do not replace PM accountability.

---

**Validation:** 195 tests pass at 100% branch coverage; `black`, `isort`, and `flake8` are clean. The variable-isolation discovery log and oracle evidence are in `ORACLE_VERIFICATION_WORKBOOK.md`.
