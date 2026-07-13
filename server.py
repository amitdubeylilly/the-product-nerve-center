"""
PM Agent — MCP Server
=====================
Exposes four tools that help a PM make data-driven sprint decisions:

  1. prioritize_backlog   — score and rank backlog items (judgment tool)
  2. analyze_feedback     — extract themes from customer feedback (judgment tool)
  3. assess_capacity      — calculate real sprint capacity per engineer (discovery tool)
  4. map_dependencies     — trace dependency chains and surface risks (discovery tool)

DATA PATH CONTRACT
------------------
Data is read from the directory given by the PM_AGENT_DATA environment variable,
falling back to ./data for local development.  Do NOT hardcode IDs or file paths.
"""

import json
import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from tools.prioritize_backlog import prioritize_backlog_impl
from tools.analyze_feedback import analyze_feedback_impl
from tools.assess_capacity import assess_capacity_impl
from tools.map_dependencies import map_dependencies_impl

mcp = FastMCP("PM Agent")

# ---------------------------------------------------------------------------
# Data loading
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


# Load once at startup
try:
    BACKLOG = _load("product_backlog.json")
    FEEDBACK = _load("customer_feedback.json")
    SPRINT_HISTORY = _load("sprint_history.json")
    ROSTER = _load_with_fallback("team_roster.json", "sample_roster.json")
    DEPENDENCIES = _load_with_fallback("dependency_map.json", "sample_dependencies.json")
except FileNotFoundError as exc:
    import sys
    print(f"STARTUP ERROR: {exc}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Tool 1: prioritize_backlog
# ---------------------------------------------------------------------------

@mcp.tool()
def prioritize_backlog(
    method: str = "rice",
    squad_filter: Optional[str] = None,
    include_done: bool = False,
    include_dependency_check: bool = True,
    top_n: Optional[int] = None,
) -> dict:
    """Score and rank backlog items to surface the highest-value work for the sprint.

    Use this tool when Asha asks questions like:
      • "What should we work on next sprint?"
      • "Which items have the most customer signal?"
      • "Are there any stale or blocked items we should flag?"
      • "Show me the top Platform squad items."

    Scoring (method="rice"):
        Reach      = unique customers whose feedback matches the item (proxy for audience size)
        Impact     = business_value_score field (1–10)
        Confidence = confidence_score / 10
        Effort     = effort_points (treated as 1 when 0 to avoid division by zero)
        RICE       = (Reach × Impact × Confidence) / Effort × priority_multiplier

    Priority multipliers:  P0→4×  P1→3×  P2→2×  P3→1×
    "executive-priority" tag boosts score by 20 % and raises a flag.
    Items with unresolved blockers are sorted to the bottom of the list.

    Args:
        method:                   Scoring method. "rice" (default) or "value_effort".
        squad_filter:             Restrict to one squad: "platform", "growth", or None
                                  for all squads.
        include_done:             Include items with status "done". Default False.
        include_dependency_check: Flag items with unresolved dependencies and push
                                  them to the bottom. Default True.
        top_n:                    Return only the top N items. None returns all.

    Returns a dict with:
        ranked_items  – list ordered by score; each item includes id, title, status,
                        priority, score, score_components, and flags
        summary       – total ranked, flag counts (stale / unestimated / blocked / etc.)
    """
    return prioritize_backlog_impl(
        backlog=BACKLOG,
        feedback=FEEDBACK,
        method=method,
        squad_filter=squad_filter,
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
    include_churned: bool = True,
    top_n: int = 10,
    min_sentiment: Optional[float] = None,
) -> dict:
    """Extract themes and patterns from customer feedback, with bias warnings.

    Use this tool when Asha asks questions like:
      • "What are customers actually asking for?"
      • "What do our enterprise customers complain about most?"
      • "Are there recurring issues from churned accounts?"
      • "Which customers are giving the most feedback?"

    Near-duplicate entries (same customer, ≥ 70 % word overlap, within 14 days)
    are excluded from theme counts to avoid signal inflation.

    Bias warnings are raised for:
      • volume_skew    — one customer accounts for > 25 % of filtered feedback
      • churned_signal — churned customers account for > 20 % of feedback
      • tier_skew      — one tier accounts for > 60 % of feedback

    Args:
        group_by:        "theme" (default) groups by detected topic area;
                         "customer" groups results by submitting customer.
        customer_tier:   Filter to a tier: "enterprise", "mid_market", or "startup".
                         None = all tiers.
        include_churned: Include feedback from churned customers. Default True.
                         Set False to focus on active / trial accounts.
        top_n:           Number of top themes or customers to return. Default 10.
        min_sentiment:   Optional lower-bound sentiment filter (-1.0 to 1.0).
                         E.g. -0.5 to surface only strongly negative feedback.

    Returns a dict with:
        themes / customers      – ranked results with counts, ARR, sentiment, tier breakdown
        bias_warnings           – data-quality flags
        duplicate_ids_excluded  – IDs removed as near-duplicates
        total_entries_analyzed
    """
    return analyze_feedback_impl(
        feedback=FEEDBACK,
        group_by=group_by,
        customer_tier=customer_tier,
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
    sprint_days: int = 10,
    required_skills: Optional[list] = None,
) -> dict:
    """Calculate real available sprint capacity per engineer and squad.

    Use this tool when Asha asks questions like:
      • "Can we fit this into the sprint?"
      • "How much capacity does the Platform squad have?"
      • "Who is available for backend work this sprint?"
      • "Are any engineers overloaded with carry-over?"

    Capacity formula (reverse-engineered from oracle probing):
        allocated  = 21 × (allocation_percent / 100)
        effective  = allocated × ((sprint_days − pto_days) / sprint_days)
        available  = max(0, effective − carry_over_points)

    The constant 21 is the full sprint value at 100 % allocation for a 10-day sprint.
    Engineers at 0 % allocation are included for visibility but excluded from totals.

    Warnings are raised for:
      • overloaded engineers (carry-over > effective capacity)
      • engineers with zero effective capacity (full PTO)
      • skill mismatches when required_skills is specified

    Args:
        squad:           Filter to one squad: "platform", "growth", etc. None = all.
        sprint_days:     Working days in the sprint. Default 10.
        required_skills: Check whether engineers have all listed skills.
                         E.g. ["backend", "security"]. None = no skill check.

    Returns a dict with:
        engineers      – per-engineer breakdown (allocated / effective / available)
        squad_totals   – aggregated by squad
        team_totals    – across all squads in the result set
        warnings       – overload, zero-capacity, and skill-mismatch alerts
        capacity_formula – formula string for auditability
    """
    return assess_capacity_impl(
        roster=ROSTER,
        squad=squad,
        sprint_days=sprint_days,
        required_skills=required_skills,
    )


# ---------------------------------------------------------------------------
# Tool 4: map_dependencies
# ---------------------------------------------------------------------------

@mcp.tool()
def map_dependencies(
    item_ids: list,
    max_depth: int = 5,
    include_soft: bool = True,
) -> dict:
    """Trace dependency chains, detect cycles, and surface delivery risks.

    Use this tool when Asha asks questions like:
      • "What's blocking the API redesign?"
      • "What does BP-109 depend on?"
      • "Are there any circular dependencies?"
      • "What is the critical path for the CI/CD milestone?"

    Each item's dependencies are traversed up to max_depth levels.
    Dependency types:
        blocks    hard blocker — must be resolved before work can start
        soft      beneficial but not strictly required
        external  depends on a team outside the squads; may carry ETA risk

    Risk flags raised per item:
        external_no_eta     external dependency with null or "TBD" ETA
        external_dependency external dependency with a concrete ETA
        long_chain          dependency chain ≥ 3 items

    Cycle detection runs full DFS; the complete cycle path is reported.
    Critical path is the longest chain of 'blocks' edges across all requested items.

    Args:
        item_ids:     List of backlog item IDs to analyse (e.g. ["BP-109", "BP-112"]).
                      Must be non-empty.
        max_depth:    Maximum traversal depth for transitive dependencies. Default 5.
        include_soft: If True (default), include soft dependencies in the trace.
                      Set False to show only hard blockers and external dependencies.

    Returns a dict with:
        items            – per-item trace with direct and transitive deps + risk flags
        cycles           – any circular dependency paths found
        critical_path    – longest blocking chain across the requested items
        has_cycles       – boolean shortcut
        summary          – aggregate counts (items analysed, total deps, external risks)
    """
    return map_dependencies_impl(
        dep_list=DEPENDENCIES,
        item_ids=item_ids,
        max_depth=max_depth,
        include_soft=include_soft,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
