# PM Agent — MCP Server Starter Kit

A minimal MCP server project to get you started. One example tool (`get_current_date`) is implemented as a reference. You add the **4 prescribed tools**.

## Two kinds of tools in this challenge
- `prioritize_backlog` and `analyze_feedback` work from the **data files** in `./data`.
- `assess_capacity` and `map_dependencies` are built around **rules you discover by querying the Nimbus Oracle** (a hosted service — see `../oracle_connection/README.md` to connect). You reverse-engineer the rules, then implement them here as standalone logic.

> **Your submitted server must NOT call the oracle.** The oracle is a *discovery aid* you use while building. At grading time it is not available to your server, and your tools run against a different dataset. Implement the rule you discovered, not a live call to the oracle.

## Prerequisites
- Python 3.10+
- `uv` (recommended) or `pip`

## Quick Start
```bash
cd mcp_starter
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python server.py
```
The server uses **stdio** transport — what Claude Desktop and Claude Code expect.

## DATA PATH CONTRACT (important)
Your server **must** read its dataset from the `PM_AGENT_DATA` environment variable, falling back to `./data` for local development:

```python
DATA_DIR = Path(os.environ.get("PM_AGENT_DATA", Path(__file__).parent / "data"))
```

At grading time the evaluation agent mounts a **different dataset** (same schema, different values) at `PM_AGENT_DATA`. Your tools must compute from whatever is mounted — **do not hardcode** IDs, names, or numbers from the sample data, and do not read from a committed copy instead of `DATA_DIR`.

## Local Development Data
Put the 5 sample JSON files in `./data` for local dev:
```bash
mkdir -p data
cp /path/to/sample/*.json data/
```

## Connecting to Claude Desktop
Config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "pm-agent": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": { "PM_AGENT_DATA": "/absolute/path/to/data" }
    }
  }
}
```
Use absolute paths. Restart Claude Desktop after editing.

## Connecting via Claude Code
```bash
claude mcp add pm-agent python server.py
```

## Submission Repo Structure
Your submitted repo must look like this so the eval agent can run it:
```
your-repo/
├── server.py            # entry point at repo root
├── requirements.txt     # pinned deps
├── tools/               # your implementations
├── data/                # sample data for local dev
├── olympics.json        # run contract (included here)
└── README.md
```

## Tips
- **Tool descriptions matter.** Claude uses them to decide when and how to call your tool.
- **Error handling matters.** Return clear errors for bad input rather than crashing.
- **Load data once** at startup, from `DATA_DIR`.
- **Use the pre-submission validator** in the app to confirm your repo runs in the sandbox before the deadline.
