# Local self-test fixtures (dev only — NOT used at grading)

These files let you exercise `assess_capacity` and `map_dependencies` on realistic,
oracle-schema data instead of the tiny 2-record samples in `../data`.

The server reads `PM_AGENT_DATA` first and falls back to `../data` — it never reads
this folder unless you explicitly point `PM_AGENT_DATA` here. So nothing in `fixtures/`
can affect grading.

Important: this folder is not a complete standalone dataset. Before pointing
`PM_AGENT_DATA` here, copy in `product_backlog.json`, `customer_feedback.json`,
and `sprint_history.json` as shown below.

## What's here

- `team_roster.json` — 8 engineers in the **oracle** schema (`engineer_id`,
  `allocation_percent`, `pto_days`, `carry_over_points`, `skills`) covering every
  edge case: 100% baseline, partial-allocation-with-PTO (the case that distinguishes
  the capacity formula), zero-effective (full PTO), carry-over > effective (overload),
  and 0% allocation (excluded from squad totals).
- `dependency_map.json` — an **oracle**-schema graph over real backlog IDs with a
  3-deep `blocks` chain, a `soft` edge, an external dep with an ETA, an external dep
  with `TBD` (no ETA), and a deliberate cycle (`BP-120 → BP-121 → BP-122 → BP-120`).

## Run a full self-test

```bash
# complete the fixture dir with the three shipped data files, then launch on it
cp ../data/product_backlog.json ../data/customer_feedback.json ../data/sprint_history.json .
PM_AGENT_DATA="$(pwd)" python ../server.py
```

After completing the copy step above, point Claude Desktop / Claude Code at this
folder via the `PM_AGENT_DATA` env var in the MCP server config, then ask
capacity/dependency questions and confirm:

- Omar (50% alloc, 2 PTO) → available 8.4 (multiplicative proration)
- Quinn (full PTO) → zero effective, `zero_effective_due_to_pto`
- Tess (carry 12 > effective 8.4) → available 0, `overloaded`
- Uma (0% alloc) → `zero_allocation`, excluded from squad totals
- `map_dependencies(["BP-120"])` → reports the cycle
- `map_dependencies(["BP-108"])` → `long_chain`, external ETA vs no-ETA split,
  critical path `BP-108 → BP-110 → BP-112 → BP-115`
