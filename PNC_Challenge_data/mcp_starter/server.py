"""
PM Agent — MCP Server (Starter)
============================================
A starter MCP server with one example tool. Add your 4 prescribed tools below.

IMPORTANT — DATA PATH CONTRACT
------------------------------
Your server MUST read its dataset from the directory given by the PM_AGENT_DATA
environment variable, falling back to ./data for local development.

    DATA_DIR = Path(os.environ.get("PM_AGENT_DATA", Path(__file__).parent / "data"))

At grading time the evaluation harness mounts a DIFFERENT dataset (same schema,
different values) at PM_AGENT_DATA. Do NOT hardcode item IDs, names, or numbers
from the sample data — your tools must compute from whatever dataset is mounted.
Do NOT commit your own copy of the data and read from it directly; read from DATA_DIR.
"""

import json
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PM Agent")

# ---------------------------------------------------------------------------
# Data Loading — read from the mounted data directory (see DATA PATH CONTRACT)
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("PM_AGENT_DATA", Path(__file__).parent / "data"))

def load_json(filename: str):
    """Load a JSON file from the mounted data directory."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(
            f"Data file not found: {filepath}. "
            f"The harness sets PM_AGENT_DATA; locally, put files in ./data."
        )
    with open(filepath) as f:
        return json.load(f)

# Load once at startup. Read from DATA_DIR every run so the mounted dataset is used.
# product_backlog   = load_json("product_backlog.json")
# customer_feedback = load_json("customer_feedback.json")
# team_roster       = load_json("team_roster.json")
# dependency_map    = load_json("dependency_map.json")
# sprint_history    = load_json("sprint_history.json")


# ---------------------------------------------------------------------------
# Example Tool — get_current_date (remove once you have your own tools)
# ---------------------------------------------------------------------------
from tools.example import get_current_date_impl

@mcp.tool()
def get_current_date(format: str = "iso") -> str:
    """Get the current date and time.

    Args:
        format: "iso" for ISO 8601 (default), "human" for a readable format.
    Returns:
        The current date/time as a string.
    """
    return get_current_date_impl(format)


# ---------------------------------------------------------------------------
# YOUR 4 PRESCRIBED TOOLS GO HERE
#   1. prioritize_backlog
#   2. analyze_feedback
#   3. assess_capacity
#   4. map_dependencies
# Implement each with the EXACT input schema from the challenge brief.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    mcp.run()
