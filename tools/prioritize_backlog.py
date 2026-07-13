"""
prioritize_backlog — Score and rank backlog items using a RICE-derived model.

Scoring formula (RICE):
    Reach      = unique customers whose feedback text matches item keywords (proxy)
    Impact     = business_value_score (1–10 field on the backlog item)
    Confidence = confidence_score / 10  (normalised to 0–1)
    Effort     = effort_points  (set to 1 when 0 to avoid division by zero)
    RICE score = (Reach × Impact × Confidence) / Effort

Priority multiplier applied after RICE:  P0→×4  P1→×3  P2→×2  P3→×1
"executive-priority" tag     → score boosted ×1.2 and flag raised
Unresolved blockers          → flagged; sorted to bottom when dependency check on

Flags emitted per item:
    executive-priority        item has the executive-priority tag
    stale                     last_updated > 90 days ago
    unestimated               effort_points == 0
    no_customer_signal        no feedback entries matched the item
    blocked_by:<ID>           dependency exists and is not done
    missing_dependency:<ID>   dependency ID not found in backlog
"""

import re
from datetime import date, datetime
from typing import Optional

PRIORITY_WEIGHT: dict[str, int] = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}
STALE_DAYS = 90
EXECUTIVE_TAG = "executive-priority"
KNOWN_METHODS = {"rice", "value_effort"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _keywords(item: dict) -> set[str]:
    """All significant words from an item's title and tags."""
    words: set[str] = set()
    for tag in item.get("tags", []):
        words.update(re.split(r"[-_]", tag.lower()))
        words.add(tag.lower())
    for word in re.findall(r"[a-z]{4,}", item.get("title", "").lower()):
        words.add(word)
    return words


def _feedback_reach(item: dict, feedback: list) -> int:
    """Count unique customers whose feedback text overlaps item keywords."""
    kw = _keywords(item)
    if not kw:
        return 0
    customers: set[str] = set()
    for fb in feedback:
        text_words = set(re.findall(r"[a-z]+", fb.get("text", "").lower()))
        if kw & text_words:
            cid = fb.get("customer_id") or fb.get("id", "")
            customers.add(cid)
    return len(customers)


def _days_since(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Main implementation
# ---------------------------------------------------------------------------


def prioritize_backlog_impl(
    backlog: list,
    feedback: list,
    method: str = "rice",
    squad_filter: Optional[str] = None,
    include_done: bool = False,
    include_dependency_check: bool = True,
    top_n: Optional[int] = None,
    deps: Optional[list] = None,  # dependency data; accepted for interface compat
    filters: Optional[dict] = None,  # alternate filter dict; overrides squad_filter
) -> dict:
    """Score and rank backlog items, returning flags and score breakdowns.

    Args:
        backlog:                   Loaded product_backlog.json list.
        feedback:                  Loaded customer_feedback.json list.
        method:                    Scoring method. "rice" (default) or "value_effort".
        squad_filter:              Only include items for this squad. None = all squads.
        include_done:              If False (default), skip items with status "done".
        include_dependency_check:  If True, flag and deprioritise items with unresolved
                                   dependencies.
        top_n:                     Return only the top N ranked items. None = all.

    Returns:
        dict with keys:
            ranked_items  – list of scored/flagged item dicts
            summary       – counts and metadata
    """
    done_ids = {item["id"] for item in backlog if item.get("status") == "done"}
    all_ids = {item["id"] for item in backlog}

    # filters dict overrides individual params when present
    status_filter: Optional[set] = None
    tags_filter: Optional[set] = None
    if filters:
        squad_filter = filters.get("squad", squad_filter)
        raw_status = filters.get("status")
        if raw_status:
            status_filter = {raw_status} if isinstance(raw_status, str) else set(raw_status)
        raw_tags = filters.get("tags")
        if raw_tags:
            raw_tags = [raw_tags] if isinstance(raw_tags, str) else raw_tags
            tags_filter = {t.lower() for t in raw_tags}

    # Unknown scoring methods fall back to the documented default ("rice") rather
    # than silently switching to value_effort.
    effective_method = method if method in KNOWN_METHODS else "rice"

    results = []
    for item in backlog:
        status = item.get("status", "")
        # An explicit status filter governs; otherwise apply the include_done rule.
        if status_filter is not None:
            if status not in status_filter:
                continue
        elif not include_done and status == "done":
            continue
        if squad_filter and item.get("squad_assignment") != squad_filter:
            continue
        if tags_filter is not None:
            item_tags = {t.lower() for t in item.get("tags", [])}
            if not (tags_filter & item_tags):
                continue

        effort = item.get("effort_points") or 1  # guard against 0 / None
        bv = item.get("business_value_score", 5)
        conf = (item.get("confidence_score", 5)) / 10.0
        reach = _feedback_reach(item, feedback)

        if effective_method == "rice":
            base_score = (reach * bv * conf) / effort
        else:
            base_score = (bv * conf) / effort

        priority = item.get("priority", "P2")
        base_score *= PRIORITY_WEIGHT.get(priority, 2)

        flags: list[str] = []
        tags_lower = [t.lower() for t in item.get("tags", [])]

        # Executive-priority boost + flag
        if EXECUTIVE_TAG in tags_lower:
            base_score *= 1.2
            flags.append("executive-priority")

        # Staleness
        if item.get("last_updated") and _days_since(item["last_updated"]) > STALE_DAYS:
            flags.append("stale")

        # Unestimated
        if item.get("effort_points", -1) == 0:
            flags.append("unestimated")

        # Customer signal
        if reach == 0:
            flags.append("no_customer_signal")

        # Dependency check
        has_unresolved_blocker = False
        if include_dependency_check:
            for dep_id in item.get("dependencies", []):
                if dep_id not in done_ids:
                    if dep_id in all_ids:
                        flags.append(f"blocked_by:{dep_id}")
                        has_unresolved_blocker = True
                    else:
                        flags.append(f"missing_dependency:{dep_id}")
                        has_unresolved_blocker = True

        results.append(
            {
                "id": item["id"],
                "title": item.get("title", ""),
                "status": status,
                "priority": priority,
                "squad": item.get("squad_assignment", ""),
                "effort_points": item.get("effort_points", 0),
                "score": round(base_score, 4),
                "score_components": {
                    "reach_customers": reach,
                    "impact": bv,
                    "confidence": round(conf, 2),
                    "effort": effort,
                    "priority_multiplier": PRIORITY_WEIGHT.get(priority, 2),
                },
                "flags": flags,
                "has_unresolved_blocker": has_unresolved_blocker,
            }
        )

    # Sort: blocked items pushed to bottom; then score desc; tie-break priority then id
    priority_rank = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}

    def _sort_key(r: dict) -> tuple:
        blocker_penalty = 1 if (include_dependency_check and r["has_unresolved_blocker"]) else 0
        return (
            blocker_penalty,
            -r["score"],
            -priority_rank.get(r["priority"], 0),
            r["id"],
        )

    results.sort(key=_sort_key)

    if top_n is not None:
        results = results[:top_n]

    summary = {
        "total_ranked": len(results),
        "method": effective_method,
        "squad_filter": squad_filter,
        "flags_summary": {
            "stale": sum(1 for r in results if "stale" in r["flags"]),
            "unestimated": sum(1 for r in results if "unestimated" in r["flags"]),
            "no_customer_signal": sum(1 for r in results if "no_customer_signal" in r["flags"]),
            "blocked": sum(1 for r in results if r["has_unresolved_blocker"]),
            "executive_priority": sum(1 for r in results if "executive-priority" in r["flags"]),
        },
    }
    if method not in KNOWN_METHODS:
        summary["method_warning"] = f"Unknown method '{method}'; defaulted to 'rice'."

    return {"ranked_items": results, "summary": summary}
