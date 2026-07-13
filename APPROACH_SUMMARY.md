# Approach Summary (PM Agent Challenge)

This document answers the six required Technical Decision Log prompts from the challenge brief. It is written against the implemented code and current repository state.

## 1. Schema Rationale

I designed the server around thin MCP wrappers in server.py and pure business logic in tools/*.py. The wrapper functions expose stable tool signatures that are easy for Claude to call, while the tool modules encapsulate scoring, filtering, traversal, and capacity math in deterministic code paths that are easy to test.

Input schema choices:
- prioritize_backlog accepts both direct controls (method, squad_filter, include_done, top_n) and an optional filters object. The filters object supports squad, status, and tags so Claude can express user intent in one argument group.
- analyze_feedback keeps filters composable (customer_tier, source, time_range, include_churned, min_sentiment) and supports both theme and customer grouping.
- assess_capacity supports squad filtering, sprint_days, carry-over inclusion, and optional skill-fit checks.
- map_dependencies supports explicit item_ids plus max_depth and inclusion toggles for soft and external dependencies.

Output schema choices:
- All tools return JSON-friendly dicts with explicit top-level keys, summary blocks, and machine-usable fields.
- prioritize_backlog returns ranked_items plus summary and per-item flags.
- analyze_feedback returns themes or customers plus bias_warnings and duplicate_ids_excluded.
- assess_capacity returns engineers, squad_totals, team_totals, warnings, and capacity_formula.
- map_dependencies returns per-item traces, cycles, critical_path, and summary.

Alternatives I rejected:
- Free-form text outputs: rejected because they are hard for an LLM orchestrator to reliably parse and chain.
- Deeply nested schemas with many optional branches: rejected because they increase tool-call ambiguity and hurt reliability.
- Separate tools per filter variation (for example, one tool for planned items, one for tag search): rejected because it fragments behavior and hurts composability.

## 2. Investigation and Trap Handling

The challenge requires discovered behavior for capacity and dependencies, and robust behavior for all tools on mounted data.

Investigation approach used:
- Baseline-first framing: treat each rule as hypothesis-driven, not assumption-driven.
- Isolate one variable at a time for capacity reasoning (allocation, PTO, carry-over, zero-allocation behavior).
- Validate dependency traversal with explicit graph patterns (direct edges, long chain, cycle, external ETA states).
- Keep runtime implementation oracle-free and deterministic.

Capacity traps and handling:
- Core trap: PTO proration may be multiplicative or subtractive; both can look similar for full-allocation cases.
- Implemented formula currently is:
  allocated = 21 * (allocation_percent / 100)
  effective = allocated * ((sprint_days - pto_days) / sprint_days)
  available = max(0, effective - carry_over_points)
- I added a discovery aid script (.log/capacity_formula_fitter.py) to compare candidate formulas against oracle outputs once records are pasted.
- I also created fixture cases that discriminate key behaviors (partial allocation with PTO, overload floor, zero allocation, full PTO) to harden implementation and tests.

Dependency traps and handling:
- Schema normalization is required because input may use source_item_id/target_item_id/dependency_type or item_id/target_id/type.
- I normalize both forms before graph traversal.
- Cycle detection is explicit and returns full cycle path.
- Critical path is intentionally blocks-only to avoid over-prioritizing soft links.
- External dependencies are risk-flagged differently for known ETA vs missing/TBD ETA.

Data and runtime anomalies handled:
- Missing files: startup fails with explicit error context.
- Unknown methods in prioritize_backlog: now default to rice with method_warning (instead of silently changing scoring mode).
- Previously ignored status/tags filters in prioritize_backlog were implemented and regression-tested.
- Empty or invalid inputs return structured error objects in discovery tools (for example, max_depth < 1, empty item_ids in impl-level map_dependencies).

## 3. Tool Description Craft

Tool descriptions were written as operational guidance for Claude, not as static API docs. Each description explicitly states:
- when to use the tool,
- parameter intent,
- output shape,
- and important behavioral caveats.

Example where description directly influences invocation:
- prioritize_backlog now documents that filters supports squad, status, and tags, with string-or-list behavior for status/tags and that unknown methods fall back to rice.
- This nudges Claude to send a single structured filters payload for intent like "planned growth items with security tags" instead of splitting context across partial arguments.

Other description choices:
- assess_capacity includes the formula in the docstring for transparency.
- map_dependencies describes risk flags and critical-path semantics so downstream reasoning can explain why an item is risky.

## 4. Failure Modes

The server is designed to fail clearly and predictably.

Startup/data failures:
- server._load raises FileNotFoundError with path and remediation hint.
- server exits at startup if required files are missing.

Input failures and edge handling:
- assess_capacity returns structured error when sprint_days <= 0.
- map_dependencies_impl returns structured errors for empty item_ids and invalid max_depth.
- prioritize_backlog handles unknown scoring method by explicit fallback and warning.
- prioritize_backlog dependency flags distinguish blocked_by and missing_dependency.

Data-quality and bias handling:
- analyze_feedback deduplicates near-duplicates and returns duplicate_ids_excluded.
- It adds bias warnings for customer-volume skew, churned-signal dominance, and tier skew.

Graph/path failures:
- map_dependencies guards traversal depth and tracks visited nodes.
- Cycle detection is explicit and surfaced in cycles with a human-readable message.

Determinism under ties:
- prioritize_backlog sorting is deterministic using blocker penalty, score, priority rank, and ID tie-break.

## 5. Custom Insight

Designing tools for AI use is different from designing dashboards for humans.

Key insight:
- The best tool output is not the most verbose output; it is the most composable output.
- LLM orchestration benefits from stable keys, explicit warnings, deterministic ordering, and clear failure contracts.

What changed in practice:
- I prioritized predictable structures over display formatting.
- I encoded rationale as fields (flags, warnings, score_components) rather than prose.
- I treated descriptions as behavioral prompts to steer tool selection and parameter shape.

Another insight:
- Judgment tools and discovered-rule tools need different optimization strategies.
- Judgment tools need explicit, defensible heuristics and bias surfacing.
- Discovery tools need rule fidelity and hard guardrails around assumptions.

## 6. Production Scaling

If this were deployed across six product teams, I would scale data, schemas, and safeguards in phases.

Data layer changes:
- Replace startup-only JSON loading with a typed data-access layer that supports schema versioning and periodic refresh.
- Add data validation contracts (for example, Pydantic models) at ingestion boundaries.
- Introduce audit metadata (data_version, loaded_at, source_hash) in outputs for traceability.

Schema and API changes:
- Add explicit pagination and cursor controls for large feedback sets.
- Add explainability fields consistently across all tools (for example, assumptions_used, filters_applied).
- Add optional strict_mode to fail on unknown enum values instead of defaulting.

Error handling and reliability:
- Standardize error envelopes with error_code, message, retryable, and context.
- Add per-tool timing and fallback annotations.
- Add contract tests against multiple synthetic datasets and drift tests against known answer sets.

Additional tools I would add:
- what_if_capacity_change: simulate PTO/allocation/carry-over changes before sprint planning.
- dependency_impact_diff: compare risk before/after backlog adjustments.
- backlog_health_report: summarize stale/unestimated/no-signal trends over time.

What I would not automate:
- Final priority decisions that encode strategy tradeoffs (for example, enterprise retention vs growth bets).
- Customer-sensitive escalations where context outside data files matters.
- Team-level staffing commitments without manager review.

Human-in-the-loop remains required for strategic accountability; the tools should compress analysis time, not replace PM judgment.

---

Current status note:
- Implementation quality is validated by passing tests and deterministic outputs.
- Oracle-grounded capacity confirmation still depends on available oracle records; the workbook in ORACLE_VERIFICATION_WORKBOOK.md defines the exact final closure step.
