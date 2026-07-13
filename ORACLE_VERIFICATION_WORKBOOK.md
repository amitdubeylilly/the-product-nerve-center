# Oracle Verification Workbook

Purpose: document how the `assess_capacity` and `map_dependencies` rules were
reverse-engineered from the pm-data-agent (Nimbus Oracle) during the discovery
phase, and record the evidence that the implemented rules match the oracle.

Status: **CLOSED** — the capacity formula reproduces every oracle figure exactly
(§4), and the dependency semantics were confirmed against the oracle graph (§5).
Runtime code does **not** call the oracle; these findings are embodied as
standalone logic.

## 1. Method

Baseline-first, one variable at a time. I queried the oracle's granular tools
(`list_team_members`, `get_engineer_capacity`, `get_engineer_profile`,
`get_engineer_skills`, `get_engineer_sprint`, `get_item_dependencies`,
`get_dependency_summary`) and chose engineers that isolate a single factor
(allocation, PTO, carry-over, zero-allocation) so competing formulas give
different answers.

## 2. Capacity Record Table (from oracle)

`total_capacity_points = 21` for every engineer in the discovery dataset.

| engineer | squad      | alloc % | pto | carry | available_points (oracle) |
|----------|------------|--------:|----:|------:|--------------------------:|
| Sana     | core       |     100 |   0 |     0 |                      21.0 |
| Rao      | core       |     100 |   0 |     5 |                      16.0 |
| Otto     | core       |     100 |   4 |     0 |                      12.6 |
| Mira     | core       |      50 |   0 |     6 |                       4.5 |
| Ken      | experience |     100 |   2 |     0 |                      16.8 |
| Isa      | experience |     100 |   0 |    11 |                      10.0 |
| Lux      | experience |      50 |   2 |     0 |                       8.4 |
| Vik      | experience |       0 |   0 |     0 |                       0.0 |

(Carry-over is reported by the oracle as in-progress items with points — e.g.
Isa carries NB-114 (6) + NB-115 (5) = 11.)

## 3. Hypotheses Discriminated

- **Baseline:** Sana (100/0/0) → 21.0 ⇒ base = `total_capacity_points` × allocation.
- **PTO multiplicative vs subtractive:** Otto (100/4/0) → 12.6 = 21 × (10−4)/10.
  Subtractive PTO (21 − 4 = 17) is ruled out. **PTO prorates multiplicatively**
  over a 10-day sprint.
- **Allocation × PTO compose:** Lux (50/2/0) → 8.4 = 21 × 0.5 × 0.8. Confirms the
  two factors multiply.
- **Carry-over order:** Mira (50/0/6) → 4.5 = (21 × 0.5) − 6. Carry is subtracted
  **after** proration, not before. Rao (carry 5) → 16.0; Isa (carry 11) → 10.0.
- **Floor:** available never goes below 0 (max(0, …)).
- **Zero allocation:** Vik (0 %) → 0.0, flagged `zero_allocation` and **excluded**
  from squad capacity totals (not merely contributing 0).

## 4. Confirmed Formula (winner: multiplicative PTO, carry after proration)

```
allocated = total_capacity_points × (allocation_percent / 100)
effective = allocated × ((sprint_days − pto_days) / sprint_days)   # sprint_days = 10
available = max(0, effective − carry_over_points)
```

Verification — recomputing each engineer with this formula reproduces the oracle
`available_points` **exactly** for all 8 records above. Squad and team roll-ups
(allocation > 0 only) also match:

| scope             | allocated | effective | available |
|-------------------|----------:|----------:|----------:|
| core (4 eng)      |      73.5 |      65.1 |      54.1 |
| experience (4 eng)|      52.5 |      46.2 |      35.2 |
| team (8 eng)      |     126.0 |     111.3 |      89.3 |

This is the rule implemented in `tools/assess_capacity.py`. Because grading data
differs, capacity is read **per engineer** from `total_capacity_points` (not a
hardcoded 21), and `_normalize` accepts both the oracle field names
(`allocation_percent`, `pto_days`, `carry_over_points`) and the sample-file names
(`sprint_allocation_percent`, `pto_days_this_sprint`, `carry_over_items`).

## 5. Dependency Rule Validation

From `get_dependency_summary`: 12 edges across 12 source items — 8 `blocks`,
2 `soft`, 2 `external`. Confirmed semantics, embodied in
`tools/map_dependencies.py`:

- **Type handling differs:** `blocks` define the critical path; `soft` is
  traversed (when `include_soft`) but excluded from the critical path; `external`
  points outside the squads and carries `external_team` / `external_eta`.
- **External ETA states:** `null` or `"TBD"` → `external_no_eta` risk flag; a
  concrete date → informational `external_dependency`.
- **Transitive traversal:** BFS to `max_depth`, tracking visited nodes.
- **Cycles:** iterative DFS; a detected cycle is returned with its full path.
- **Long chains:** total dependency count ≥ 3 for an item → `long_chain` flag.

The dependency normalizer accepts both `source_item_id`/`target_item_id`/
`dependency_type` and the oracle `item_id`/`target_id`/`type` shapes.

## 6. Runtime Contract

The submitted server never calls the oracle. It reads `team_roster.json` and
`dependency_map.json` from `PM_AGENT_DATA` (with the tiny `sample_*` files as a
local fallback) and applies the rules above as standalone logic.
