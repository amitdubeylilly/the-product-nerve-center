# the-product-nerve-center

PM Agent MCP server for the Claude Olympics challenge.

## Quick Links

- [challenge-brief.md](challenge-brief.md): full challenge statement and scoring rubric.
- [CLAUDE.md](CLAUDE.md): auto-loaded project context for new Claude chats.
- [SKILL.md](SKILL.md): implementation playbook for the 4 required tools.
- [KNOWLEDGE.md](KNOWLEDGE.md): consolidated challenge context, data contract, and discovery notes.

## Submission Structure

```
the-product-nerve-center/
├── server.py            # MCP server entry point
├── requirements.txt     # runtime dependencies (mcp, pydantic, httpx)
├── requirements-dev.txt # dev dependencies (pytest, black, etc.)
├── agent_config.json    # grader contract (entry, run command, env vars)
├── env_vars.json        # default env vars (PM_AGENT_DATA, MCP_DATA_URL)
├── olympics.json        # tool contract (tool names, data_env_var)
├── tools/               # tool implementations
│   ├── prioritize_backlog.py
│   ├── analyze_feedback.py
│   ├── assess_capacity.py
│   └── map_dependencies.py
├── data/                # local sample data for development
├── tests/               # 176 tests, 100% branch coverage
└── pyproject.toml       # black / isort / mypy / pytest config
```

## Data Sources

- `PM_AGENT_DATA` (env var): directory with `product_backlog.json`, `customer_feedback.json`, `sprint_history.json`.
- `MCP_DATA_URL` (env var): MCP data server providing `team_roster` and `dependency_map`. Falls back to local sample files if unreachable.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Tools

| Tool | Type | Data Source |
|---|---|---|
| `prioritize_backlog` | judgment | local files |
| `analyze_feedback` | judgment | local files |
| `assess_capacity` | discovery | MCP data server |
| `map_dependencies` | discovery | MCP data server |

Important: tools compute from mounted data — no hardcoded IDs or sample values.

