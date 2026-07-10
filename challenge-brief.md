# Challenge Brief

## Scenario

You are a Staff Engineer embedded in a cross-functional product team at DevPulse, a mid-stage B2B SaaS company that builds developer productivity tools. Your PM, Asha, is overwhelmed. She manages a growing backlog, processes a constant stream of customer feedback, juggles competing stakeholder demands, and tries to keep two engineering squads, Platform and Growth, productive without overloading anyone.

Asha has asked you:

> "I spend 60% of my time manually cross-referencing spreadsheets, checking if what customers are asking for aligns with what's on the backlog, figuring out who has capacity, tracing which features are blocked by what. I need a set of tools I can plug into Claude so it can help me make better decisions, faster. Not a dashboard. Not a report. Tools that Claude can call when I ask it questions like 'Can we fit this into the sprint?', 'What are customers actually asking for?', or 'What's blocking the API redesign?' and get back answers grounded in our actual data."

You will receive DevPulse's product context as a set of JSON files representing Asha's world: the product backlog, customer feedback corpus, team roster, dependency map, and sprint history. Your job is to build an MCP server that exposes tools Claude can use to help Asha make PM decisions.

## How You Will Work

This challenge uses Claude Chat for discovery and planning, and Claude Code for building.

### Phase 1: Discover (Claude Chat + pm-data-agent)

Two of your four tools, assess_capacity and map_dependencies, are built around rules we do not hand you. Instead, you connect Claude to the pm-data-agent (a hosted service; see oracle_connection/README.md) and query it to infer those rules: how available capacity is computed, and what the dependency graph looks like.

Establish a baseline, isolate one variable at a time, and form and test hypotheses. This querying conversation is part of your submission and is scored on Investigation Rigor.

### Phase 2: Plan (Claude Chat)

Explore the data files you were given (backlog, feedback, sprint history), design your tool schemas, and plan your implementation. Export these conversations; they are one of your submission artifacts.

### Phase 3: Build (Claude Code)

Use Claude Code to implement your MCP server locally. The starter kit gives you a working skeleton; you add the four tools.

- assess_capacity and map_dependencies must embody the rules you discovered, as standalone logic.
- Your server must not call the oracle at runtime.
- analyze_feedback and prioritize_backlog work from the given data files.

### Phase 4: Self-Test, Then Submit

Connect your running server to Claude Desktop or Claude Code and exercise your tools until you are confident they are correct and robust. Then push your code to a Git repo and submit the required artifacts.

## How Submission Is Evaluated

This section is critical because it changes how you should build.

After the round closes, the evaluation agent will:

1. Clone your repo.
2. Install dependencies.
3. Launch your MCP server.
4. Run a series of scenarios against your tools.
5. Compare outputs to an answer key.

### Implications for Implementation

- Do not hardcode item IDs, engineer names, or fixed numbers. Tools must compute from mounted data.
- Read data from the mounted path. Your server must read from PM_AGENT_DATA, with fallback to ./data for local development.
- The capacity and dependency rules must be discovered, not guessed.
- Do not call the oracle from submitted runtime code; at grading time, the oracle is unavailable and data is different.

## What You Are Building

An MCP server (Python) with four prescribed tools. Implement each exactly as specified.

The four tools fall into two groups:

- Judgment tools: prioritize_backlog and analyze_feedback. These work from provided data files, and you make and defend design decisions.
- Discovery tools: assess_capacity and map_dependencies. These rely on hidden rules inferred from pm-data-agent and are graded against definite answers.

### Tool 1: prioritize_backlog (judgment)

Purpose:
Score and rank backlog items based on a configurable method, surfacing conflicts and anomalies.

Expected output:
A ranked list of backlog items with a computed score per item, plus flags for:

- dependency conflicts
- stale items (more than 90 days since last update)
- unestimated items (effort = 0)
- items with no customer signal

If include_dependency_check is true, items with unresolved dependencies should be flagged and optionally deprioritized.

Design decisions you must make:

- How do you compute RICE without explicit Reach data? (Customer feedback volume is a proxy; you decide how to use it.)
- What do you do with items that score high but have unresolved blockers?
- How do you handle the executive-priority tag: ignore it, boost it, or flag it?

### Tool 2: analyze_feedback (judgment)

Purpose:
Extract themes and patterns from customer feedback, accounting for biases in the data.

Expected output:
Top themes with frequency count, representative entry IDs, and customer-segment breakdown; bias warnings (over-represented customers, churned-customer signal, segment skew); and, when group_by is customer, a per-customer summary with status.

Design decisions you must make:

- How do you detect and handle near-duplicate feedback entries?
- Should churned-customer feedback be weighted differently, excluded, or flagged?
- If one customer has many more entries than others, do you normalize for volume or let it dominate?

### Tool 3: assess_capacity (discovery)

Purpose:
Calculate real available team capacity for a sprint, accounting for allocation, PTO, carry-over, and skill fit.

Expected output:
Per-engineer total, effective, and available capacity (after PTO and allocation, minus carry-over); team totals; and warnings for overloaded engineers, skill mismatches, and engineers with zero effective capacity.

Discover via the oracle, key questions:

- How exactly does allocation percent, PTO days, and carry-over convert to available_points?
- What does the oracle return for an engineer at 0 percent allocation, and what should that mean for squad totals?
- How does PTO prorate?

### Tool 4: map_dependencies (discovery)

Purpose:
Trace dependency chains, detect cycles, and surface risks for a given set of features.

Expected output:
For each item, direct and transitive dependencies (up to max_depth) with type (blocks, soft, external); cycle detection that reports the full cycle if one exists; risk flags for external dependencies with no ETA and long chains; and the critical path in the requested set.

Discover via the oracle, key questions:

- Query dependency_oracle(item_id) and follow target IDs to trace chains. What does the graph look like?
- Do soft dependencies get the same treatment as blocks?
- How should external dependencies with no ETA be flagged?

## What You Receive

### Data Files (Provided)

- product_backlog.json (35 backlog items)
- customer_feedback.json (90 feedback entries)
- sprint_history.json (last 6 sprints)
- data_dictionary.md (field definitions)
- sample_roster.json and sample_dependencies.json (tiny 2-3 record samples for local smoke testing only; not representative)

### Discovery Service (Query, Do Not Read)

The pm-data-agent is a hosted MCP service you query to infer capacity and dependency rules. See oracle_connection/README.md and the sample repo README for full setup details.

Note:
There may be initial setup issues with the hosted MCP service. Participants are expected to do basic troubleshooting, including using AI assistance, to get started.

### Starter

- mcp_starter: skeleton MCP server (Python) with data-path contract and one example tool, plus README and sample repo structure.

### Repo Contract Reference

- Sample repo link: [Claude Olympics Sample Repo](https://github.com/EliLillyCo/Claude-Olympics-Sample-Repo)
- Your submission repo must follow the sample repo structure so the evaluation agent can run it automatically.

## Requirements

- Entry point is server.py at repo root (or named in olympics.json).
- requirements.txt pins everything needed; the agent installs in a clean environment.
- Server reads data from PM_AGENT_DATA with fallback to ./data.
- Use the pre-submission validator to confirm your repo runs in the sandbox. A repo that runs locally but not in sandbox loses MCP Quality points.

## Scoring Dimensions

- MCP Implementation Quality: 35%
- Data Accuracy: 25%
- Investigation Rigor: 15%
- Technical Decision Log: 15%
- Output Craft: 10%

## Technical Decision Log Prompts

Answer all six in your Approach Summary (maximum 1,500 words total):

1. Schema Rationale: Why did you structure tool inputs and outputs this way? What alternatives did you reject?
2. Investigation and Trap Handling: How did you reverse-engineer capacity and dependency rules? What did you hypothesize, probe, and learn? What anomalies did you find in oracle and provided data, and how does each tool handle them?
3. Tool Description Craft: How did you write tool descriptions to guide Claude behavior? Give one example where description influenced tool selection or parameters.
4. Failure Modes: What does your server do with bad input, missing data, broken chains, and cycles? Give specific examples.
5. Custom Insight: What did this teach you about designing tools for AI use rather than human UI?
6. Production Scaling: If deployed across six product teams, what would you change in data layer, schemas, and error handling? What new tools would you add? What would you explicitly not automate, and why?
