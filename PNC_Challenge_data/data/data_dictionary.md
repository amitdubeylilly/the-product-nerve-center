# DevPulse Data Dictionary

Reference documentation for all dataset files provided in this challenge.

---

## product_backlog.json

Each entry represents a backlog item in DevPulse's product backlog.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (format: `BP-NNN`) |
| `title` | string | Short descriptive title of the backlog item |
| `description` | string | 2-3 sentence description of the work |
| `status` | enum | Current status: `proposed`, `planned`, `in_progress`, `done` |
| `priority` | enum | Priority level: `P0` (critical), `P1` (high), `P2` (medium), `P3` (low) |
| `effort_points` | integer | Story point estimate (0-21, Fibonacci-ish scale) |
| `business_value_score` | integer | Business value rating (1-10, where 10 = highest value) |
| `confidence_score` | integer | Estimation confidence (1-10, where 10 = highest confidence) |
| `requester` | string | Person or team that requested this item |
| `requested_date` | string | Date the item was first requested (YYYY-MM-DD) |
| `last_updated` | string | Date of most recent update to this item (YYYY-MM-DD) |
| `tags` | array[string] | Categorization tags |
| `dependencies` | array[string] | IDs of backlog items this item depends on |
| `squad_assignment` | enum | Assigned squad: `platform`, `growth`, `unassigned` |
| `acceptance_criteria` | array[string] | Conditions that must be met for item to be considered done |

---

## customer_feedback.json

Each entry represents a piece of customer feedback from any channel.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (format: `FB-NNN`) |
| `customer_id` | string | Customer identifier (format: `CUST-NN`) |
| `customer_name` | string | Customer company name |
| `customer_tier` | enum | Customer tier: `enterprise`, `mid_market`, `startup` |
| `customer_status` | enum | Current customer status: `active`, `churned`, `trial` |
| `arr` | integer | Annual recurring revenue in USD (0 for trial customers) |
| `source` | enum | Feedback channel: `support_ticket`, `nps_survey`, `sales_call`, `user_interview` |
| `date` | string | Date feedback was received (YYYY-MM-DD) |
| `text` | string | The feedback text (1-3 sentences) |
| `sentiment_score` | float | Sentiment analysis score (-1.0 = very negative, 0.0 = neutral, 1.0 = very positive) |

---

## Team capacity & dependencies — DISCOVERED VIA THE ORACLE (not shipped as files)

For this challenge, the team roster and the dependency map are **not** provided as data files.
Instead, you **discover** how capacity is computed and what the dependency graph looks like by
querying the **Nimbus Oracle** (see `oracle_connection/README.md` for how to connect). You then implement
your `assess_capacity` and `map_dependencies` tools from what you learn.

The fields you will encounter through the oracle are documented below so you know the shape of the
data — but the **rules** (how the fields combine into an answer, and the structure of the graph) are
what you must reverse-engineer.

### Engineer fields (via `capacity_oracle`)

| Field | Type | Description |
|-------|------|-------------|
| `engineer_id` | string | Engineer's name (query key) |
| `squad` | string | Primary squad assignment |
| `allocation_percent` | integer | Percentage of time allocated to this squad (0-100). Remaining time is on another team. |
| `pto_days` | integer | Number of PTO days in the current sprint (a sprint is 10 working days) |
| `carry_over_points` | integer | Points of in-progress work carried over from the previous sprint |
| `available_points` | number | The engineer's available capacity for the sprint — **the oracle gives you this; how it is derived from the fields above is for you to discover** |

(An engineer also has `skills` — `backend`, `frontend`, `infra`, `ml`, `mobile`, `security` — relevant
for skill-fit checks in your tool. `total_capacity_points` at 100% allocation is 21.)

### Dependency fields (via `dependency_oracle`)

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | string | The item whose dependencies you queried |
| `target_id` | string | An item it directly depends on. May be a backlog ID or an external reference (`EXT-NNN`). |
| `type` | enum | `blocks` (hard blocker), `soft` (beneficial, not blocking), `external` (outside team) |
| `external_team` | string or null | Name of the external team (only for `external` type) |
| `external_eta` | string or null | Expected delivery date, `"TBD"`, or null (only for `external` type) |

**For local development only:** the data folder includes tiny `sample_roster.json` and
`sample_dependencies.json` files (2-3 records each) so you can run your tool code without it crashing.
They are NOT representative and are far too small to reverse-engineer anything from — use the oracle
for real discovery.

---

## sprint_history.json

Each entry represents a completed sprint.

| Field | Type | Description |
|-------|------|-------------|
| `sprint_id` | string | Unique sprint identifier (format: `S-NN`) |
| `sprint_number` | integer | Sequential sprint number |
| `start_date` | string | Sprint start date (YYYY-MM-DD) |
| `end_date` | string | Sprint end date (YYYY-MM-DD) |
| `planned_points` | integer | Total story points planned at sprint start |
| `completed_points` | integer | Total story points completed at sprint end |
| `items_planned` | integer | Number of backlog items planned |
| `items_completed` | integer | Number of backlog items completed |
| `items_carried_over` | integer | Number of items not completed, carried to next sprint |
| `velocity` | integer | Sprint velocity (= completed_points) |
| `notes` | string | Sprint retrospective notes and context |

---

## Context

- **Current Sprint**: Sprint 47 (May 12–23, 2026, 10 working days)
- **Sprint Cadence**: 2-week sprints (10 working days)
- **Point Scale**: Modified Fibonacci (1, 2, 3, 5, 8, 13, 21)
- **Squads**: Platform (infrastructure, APIs, security) and Growth (user-facing features, analytics, onboarding)
- **Team Size**: 8 engineers + 1 PM (Asha) + 1 EM (Kiran)
