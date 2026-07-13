"""
PM Agent — MCP Server
=====================
Exposes four tools that help a PM make data-driven sprint decisions:

  1. prioritize_backlog   — score and rank backlog items (judgment tool)
  2. analyze_feedback     — extract themes from customer feedback (judgment tool)
  3. assess_capacity      — calculate real sprint capacity per engineer (discovery tool)
  4. map_dependencies     — trace dependency chains and surface risks (discovery tool)

DATA CONTRACT
-------------
Local files (backlog, feedback, sprint history) are read from PM_AGENT_DATA.
Team roster and dependency map are fetched from the MCP data server at MCP_DATA_URL,
falling back to local sample files if the server is unreachable.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.fastmcp import FastMCP

from tools.analyze_feedback import analyze_feedback_impl
from tools.assess_capacity import assess_capacity_impl
from tools.map_dependencies import map_dependencies_impl
from tools.prioritize_backlog import prioritize_backlog_impl

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[PM-Agent] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pm_agent")

mcp = FastMCP("PM Agent")

# ---------------------------------------------------------------------------
# Local data — injected by eval agent via PM_AGENT_DATA
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("PM_AGENT_DATA", Path(__file__).parent / "data"))


def _load(filename: str) -> list:
    """Load a JSON file from DATA_DIR; raises FileNotFoundError with context."""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}. "
            "Set PM_AGENT_DATA or place files in ./data for local development."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_with_fallback(primary: str, fallback: str) -> list:
    """Try primary filename; fall back to fallback if not present."""
    try:
        return _load(primary)
    except FileNotFoundError:
        return _load(fallback)


# ---------------------------------------------------------------------------
# Remote data — roster + deps via MCP data server at MCP_DATA_URL
# ---------------------------------------------------------------------------
MCP_DATA_URL = os.environ.get(
    "MCP_DATA_URL",
    "https://co-mcp-server-dev.apps-internal.lrl.lilly.com/mcp",
)


async def _fetch_from_mcp_server() -> dict:  # pragma: no cover
    """Fetch team roster and dependency map from the remote MCP data server."""
    async with streamable_http_client(MCP_DATA_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            roster_r = await session.call_tool("get_team_roster", {})
            deps_r = await session.call_tool("get_dependency_map", {})
    return {
        "roster": json.loads(roster_r.content[0].text),
        "deps": json.loads(deps_r.content[0].text),
    }


# ---------------------------------------------------------------------------
# Startup: load all data
# ---------------------------------------------------------------------------
try:
    BACKLOG = _load("product_backlog.json")
    FEEDBACK = _load("customer_feedback.json")
    SPRINT_HISTORY = _load("sprint_history.json")
    log.info(
        "Local data: %d backlog items, %d feedback entries, %d sprints",
        len(BACKLOG),
        len(FEEDBACK),
        len(SPRINT_HISTORY),
    )
except FileNotFoundError as exc:  # pragma: no cover
    print(f"STARTUP ERROR: {exc}", file=sys.stderr)
    sys.exit(1)

# Fetch roster + deps from MCP server; fall back to local files if unreachable
try:
    _mcp_data = asyncio.run(_fetch_from_mcp_server())  # pragma: no cover
    ROSTER = _mcp_data["roster"]  # pragma: no cover
    DEPENDENCIES = _mcp_data["deps"]  # pragma: no cover
    log.info(  # pragma: no cover
        "MCP data: %d roster entries, %d dependency edges",
        len(ROSTER),
        len(DEPENDENCIES),
    )
except Exception as _e:
    log.warning("MCP server unreachable (%s) — falling back to local files", _e)
    try:
        ROSTER = _load_with_fallback("team_roster.json", "sample_roster.json")
        DEPENDENCIES = _load_with_fallback("dependency_map.json", "sample_dependencies.json")
        log.info("Fallback: %d roster entries, %d deps", len(ROSTER), len(DEPENDENCIES))
    except Exception as _e2:  # pragma: no cover
        log.warning("Local fallback also failed (%s) — using empty data", _e2)  # pragma: no cover
        ROSTER = []  # pragma: no cover
        DEPENDENCIES = []  # pragma: no cover


# ---------------------------------------------------------------------------
# Tool 1: prioritize_backlog
# ---------------------------------------------------------------------------


@mcp.tool()
def prioritize_backlog(
    method: str = "rice",
    squad_filter: Optional[str] = None,
    filters: Optional[dict] = None,
    include_done: bool = False,
    include_dependency_check: bool = True,
    top_n: Optional[int] = None,
) -> dict:
    """Score and rank backlog items to surface the highest-value work for the sprint.

    Use this tool when Asha asks questions like:
      "What should we work on next sprint?", "Which items have the most customer
      signal?", "Are there stale or blocked items?", "Show me Platform squad items."

    Scoring (method="rice"):
        Reach × Impact × Confidence / Effort × priority_multiplier
        Reach = unique customers whose feedback matches item keywords (proxy).
        Impact = business_value_score (1-10). Confidence = confidence_score / 10.
        Effort = effort_points (1 when 0). Priority: P0→4x P1→3x P2→2x P3→1x.
    "executive-priority" tag → 1.2x score boost + flag.
    Unresolved blockers → flagged + sorted to bottom.

    Args:
        method:                   "rice" (default) or "value_effort".
        squad_filter:             Restrict to one squad name. None = all squads.
        filters:                  Dict with optional keys: squad, status, tags.
                                  Overrides squad_filter when "squad" key present.
        include_done:             Include status="done" items. Default False.
        include_dependency_check: Flag unresolved blockers. Default True.
        top_n:                    Return only top N items. None = all.

    Returns ranked_items list with score, score_components, flags, and summary.
    """
    log.info("prioritize_backlog: method=%s filters=%s squad=%s", method, filters, squad_filter)
    resolved_squad = squad_filter
    if filters:
        resolved_squad = filters.get("squad", resolved_squad)
    return prioritize_backlog_impl(
        backlog=BACKLOG,
        feedback=FEEDBACK,
        deps=DEPENDENCIES,
        method=method,
        squad_filter=resolved_squad,
        include_done=include_done,
        include_dependency_check=include_dependency_check,
        top_n=top_n,
    )


# ---------------------------------------------------------------------------
# Tool 2: analyze_feedback
# ---------------------------------------------------------------------------


@mcp.tool()
def analyze_feedback(
    group_by: str = "theme",
    customer_tier: Optional[str] = None,
    source: Optional[str] = None,
    time_range: Optional[dict] = None,
    include_churned: bool = True,
    top_n: int = 10,
    min_sentiment: Optional[float] = None,
) -> dict:
    """Extract themes and patterns from customer feedback, with bias warnings.

    Use this tool when Asha asks questions like:
      "What are customers asking for?", "What do enterprise customers complain about?",
      "Any recurring issues from churned accounts?", "Who gives the most feedback?"

    Near-duplicate detection: same customer + >=70% word overlap within 14 days.
    Bias warnings: volume_skew (>25% from one customer), churned_signal (>20%),
    tier_skew (>60% from one tier).

    Args:
        group_by:        "theme" (default) or "customer" or "source".
        customer_tier:   Filter: "enterprise", "mid_market", "startup". None = all.
        source:          Filter by channel: "support_ticket", "nps_survey",
                         "sales_call", "user_interview". None = all.
        time_range:      Filter by date: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}.
        include_churned: Include churned customer feedback. Default True.
        top_n:           Number of top themes / customers to return. Default 10.
        min_sentiment:   Lower-bound sentiment filter (-1.0 to 1.0).

    Returns themes/customers with counts, ARR, sentiment, bias_warnings.
    """
    log.info("analyze_feedback: group_by=%s tier=%s source=%s", group_by, customer_tier, source)
    return analyze_feedback_impl(
        feedback=FEEDBACK,
        group_by=group_by,
        customer_tier=customer_tier,
        source=source,
        time_range=time_range,
        include_churned=include_churned,
        top_n=top_n,
        min_sentiment=min_sentiment,
    )


# ---------------------------------------------------------------------------
# Tool 3: assess_capacity
# ---------------------------------------------------------------------------


@mcp.tool()
def assess_capacity(
    squad: Optional[str] = None,
    sprint_id: Optional[str] = None,
    sprint_days: int = 10,
    include_carry_over: bool = True,
    check_skill_fit: bool = False,
    required_skills: Optional[list] = None,
) -> dict:
    """Calculate real available sprint capacity per engineer and squad.

    Use this tool when Asha asks questions like:
      "Can we fit this into the sprint?", "How much capacity does Platform have?",
      "Who is available for backend work?", "Are any engineers overloaded?"

    Capacity formula (reverse-engineered from oracle):
        allocated  = 21 × (allocation_percent / 100)
        effective  = allocated × ((sprint_days - pto_days) / sprint_days)
        available  = max(0, effective - carry_over_points)

    Args:
        squad:           Squad filter. "all" or None = all squads.
        sprint_id:       Sprint identifier for context (informational).
        sprint_days:     Working days in the sprint. Default 10.
        include_carry_over: Deduct carry-over points from available. Default True.
        check_skill_fit: Flag engineers missing skills for assigned items.
        required_skills: Skills to check for. E.g. ["backend", "security"].

    Returns per-engineer breakdown, squad_totals, team_totals, and warnings.
    """
    log.info("assess_capacity: squad=%s sprint_id=%s days=%d", squad, sprint_id, sprint_days)
    resolved_squad = None if squad == "all" else squad
    return assess_capacity_impl(
        roster=ROSTER,
        squad=resolved_squad,
        sprint_days=sprint_days,
        include_carry_over=include_carry_over,
        check_skill_fit=check_skill_fit,
        required_skills=required_skills,
        sprint_id=sprint_id,
        sprints=SPRINT_HISTORY,
    )


# ---------------------------------------------------------------------------
# Tool 4: map_dependencies
# ---------------------------------------------------------------------------


@mcp.tool()
def map_dependencies(
    item_ids: Optional[list] = None,
    max_depth: int = 5,
    include_soft: bool = True,
    include_external: bool = True,
) -> dict:
    """Trace dependency chains, detect cycles, and surface delivery risks.

    Use this tool when Asha asks questions like:
      "What's blocking the API redesign?", "What does BP-109 depend on?",
      "Are there circular dependencies?", "What is the critical path?"

    Dependency types: blocks (hard blocker), soft (beneficial), external (outside squad).
    Risk flags: external_no_eta, external_dependency, long_chain (>=3 deps).
    Cycle detection reports the full cycle path.
    Critical path = longest blocks chain across requested items.

    Args:
        item_ids:         List of backlog item IDs to trace. None or empty =
                          all planned and in_progress items.
        max_depth:        Max traversal depth for transitive deps. Default 5.
        include_soft:     Include soft dependencies. Default True.
        include_external: Include external dependencies. Default True.

    Returns items with direct/transitive deps, cycles, critical_path, summary.
    """
    log.info("map_dependencies: item_ids=%s depth=%d", item_ids, max_depth)
    resolved_ids = item_ids or []
    if not resolved_ids:
        resolved_ids = [b["id"] for b in BACKLOG if b.get("status") in ("planned", "in_progress")]
    return map_dependencies_impl(
        dep_list=DEPENDENCIES,
        item_ids=resolved_ids,
        max_depth=max_depth,
        include_soft=include_soft,
        include_external=include_external,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) > 1 and sys.argv[1] == "http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = port
        mcp.run(transport="sse")
    else:
        mcp.run()
