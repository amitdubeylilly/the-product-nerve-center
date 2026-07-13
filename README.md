# the-product-nerve-center

PM Agent MCP server for the Claude Olympics challenge.

## Quick Links

- [challenge-brief.md](challenge-brief.md): full challenge statement and scoring rubric.
- [CLAUDE.md](CLAUDE.md): auto-loaded project context for new Claude chats.
- [SKILL.md](SKILL.md): implementation playbook for the 4 required tools.
- [KNOWLEDGE.md](KNOWLEDGE.md): consolidated challenge context, data contract, and discovery notes.
- [APPROACH_SUMMARY.md](APPROACH_SUMMARY.md): six-part technical decision log response draft.
- [ORACLE_VERIFICATION_WORKBOOK.md](ORACLE_VERIFICATION_WORKBOOK.md): workbook to close oracle-rule verification.
- [SUBMISSION_ARTIFACTS_CHECKLIST.md](SUBMISSION_ARTIFACTS_CHECKLIST.md): final artifact readiness tracker.

## Submission Structure

```
the-product-nerve-center/
├── server.py            # MCP server entry point
├── requirements.txt     # runtime dependencies (mcp, pydantic)
├── requirements-dev.txt # dev dependencies (pytest, black, etc.)
├── agent_config.json    # grader contract (entry, run command, env vars)
├── env_vars.json        # default env vars (PM_AGENT_DATA)
├── olympics.json        # tool contract (tool names, data_env_var)
├── tools/               # tool implementations
│   ├── prioritize_backlog.py
│   ├── analyze_feedback.py
│   ├── assess_capacity.py
│   └── map_dependencies.py
├── data/                # local sample data for development
├── tests/               # 195 tests, 100% branch coverage
└── pyproject.toml       # black / isort / mypy / pytest config
```

## Data Sources

- `PM_AGENT_DATA` (env var): directory with `product_backlog.json`, `customer_feedback.json`, `sprint_history.json`, `team_roster.json`, and `dependency_map.json`.
- Local development fallback is `./data` when `PM_AGENT_DATA` is not set.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Validation Snapshot

- Runtime data contract: reads from `PM_AGENT_DATA` with `./data` fallback for local development.
- Runtime safety: no network/oracle calls in submitted server runtime path.
- Tool contract: exact required tool names are exposed via `server.py` and `olympics.json`.
- Quality status: 195 tests passing with 100% line and branch coverage.

## Tools

| Tool | Type | Data Source |
|---|---|---|
| `prioritize_backlog` | judgment | local files |
| `analyze_feedback` | judgment | local files |
| `assess_capacity` | discovery | mounted files (`PM_AGENT_DATA`) |
| `map_dependencies` | discovery | mounted files (`PM_AGENT_DATA`) |

Important: tools compute from mounted data — no hardcoded IDs or sample values.

