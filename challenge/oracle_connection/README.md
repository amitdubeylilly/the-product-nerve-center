# Nimbus Oracle — Discovery Service (Participant Guide)

For Challenge 1, two of your four tools — `assess_capacity` and `map_dependencies` — are
built around rules we do **not** hand you in a file. Instead, you **discover** them by querying
this hosted oracle, then implement your own tools from what you learn.

You never see the oracle's data or its formula. You only get answers to the questions you ask.

## What the oracle exposes

- **`capacity_oracle(engineer_id)`** → an engineer's inputs (allocation, PTO, carry-over) and their `available_points`. It does **not** tell you how the number is computed — you infer the rule.
- **`capacity_oracle_roster()`** → the list of engineer_ids you can query (id + squad only).
- **`dependency_oracle(item_id)`** → the direct dependencies of a work item (type, and for external deps the team + ETA). Follow the returned ids to trace chains yourself.


## How to use it well (this is graded)

Your querying conversation is part of your submission (your Claude chat export), and it is scored on **Investigation Rigor**:

- Establish a baseline, then **isolate one variable at a time**.
- Form a hypothesis, then design the query that confirms or refutes it.
- Watch for surprises and chase them.

## Important

- Your submitted MCP server must **NOT** call this oracle. Implement the rule you discovered as
  standalone logic. At grading time your tools run against a different dataset with no oracle available.
- The oracle's engineer names and item ids are **not** the ones you'll be graded on — only the *rule* you inferred carries over.
