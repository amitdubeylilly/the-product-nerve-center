"""
analyze_feedback — Extract themes and bias signals from customer feedback.

Theme detection uses keyword matching against a domain taxonomy built from
observed backlog tags and common product-area vocabulary.  No external NLP
library is required.

Near-duplicate filtering:
    Same customer_id + Jaccard word-overlap ≥ 0.70 within a 14-day window
    → the later entry is flagged as a duplicate and excluded from theme counts.

Bias warnings raised when:
    volume_skew     a single customer accounts for > 25 % of (filtered) entries
    churned_signal  churned customers contribute > 20 % of entries
    tier_skew       a single tier accounts for > 60 % of entries
"""

import re
from collections import defaultdict
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Theme taxonomy — keyword lists per theme
# ---------------------------------------------------------------------------

THEME_KEYWORDS: dict[str, list[str]] = {
    "authentication_security": [
        "auth", "login", "jwt", "token", "sso", "saml", "password",
        "security", "mfa", "2fa", "session", "credential",
    ],
    "api_integrations": [
        "api", "webhook", "integration", "endpoint", "rest", "graphql",
        "sdk", "rate limit", "versioning", "oauth",
    ],
    "performance": [
        "slow", "performance", "load", "latency", "speed", "timeout",
        "fast", "dashboard", "loading", "lag", "response time",
    ],
    "cicd_pipeline": [
        "pipeline", "ci", "cd", "deploy", "deployment", "build",
        "trigger", "stage", "workflow", "release",
    ],
    "analytics_reporting": [
        "analytics", "report", "metric", "insight", "data", "export",
        "csv", "chart", "graph", "visibility",
    ],
    "notifications_alerts": [
        "notification", "alert", "email", "slack", "pager",
        "escalation", "on-call", "oncall", "notify",
    ],
    "onboarding_ux": [
        "onboarding", "setup", "wizard", "tooltip", "ux", "ui",
        "mobile", "responsive", "first-run", "first run", "usability",
    ],
    "compliance_audit": [
        "audit", "compliance", "soc", "gdpr", "log", "immutable",
        "retention", "rbac", "role", "access control",
    ],
    "infrastructure_reliability": [
        "infra", "infrastructure", "reliability", "uptime", "availability",
        "sla", "kubernetes", "k8s", "downtime", "incident",
    ],
    "search": [
        "search", "index", "elasticsearch", "find", "query", "filter",
    ],
    "incident_management": [
        "incident", "escalation", "response", "manual", "automated",
        "runbook", "pagerduty", "on-call",
    ],
    "collaboration_access": [
        "team", "collaboration", "comment", "share", "permission",
        "access", "role", "member",
    ],
}

STALE_DEDUP_DAYS = 14
VOLUME_SKEW_THRESHOLD = 0.25
CHURNED_THRESHOLD = 0.20
TIER_SKEW_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _parse_date(date_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def _detect_themes(text: str) -> list[str]:
    """Return all theme keys that match the entry text."""
    word_tokens = _word_set(text)
    matched: list[str] = []
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            kw_tokens = _word_set(kw)
            if kw_tokens & word_tokens:
                matched.append(theme)
                break
    return matched or ["other"]


def _deduplicate(entries: list) -> tuple[list, list[str]]:
    """
    Remove near-duplicates (same customer, high text similarity, close date).
    Returns (deduplicated_entries, list_of_excluded_ids).
    """
    seen: list[dict] = []
    excluded_ids: list[str] = []

    for entry in entries:
        text_words = _word_set(entry.get("text", ""))
        cid = entry.get("customer_id", "")
        entry_date = _parse_date(entry.get("date", ""))
        is_dup = False

        for prev in seen:
            if prev.get("customer_id", "") != cid:
                continue
            prev_date = _parse_date(prev.get("date", ""))
            if entry_date and prev_date:
                if abs((entry_date - prev_date).days) > STALE_DEDUP_DAYS:
                    continue
            if _jaccard(text_words, _word_set(prev.get("text", ""))) >= 0.70:
                is_dup = True
                break

        if is_dup:
            excluded_ids.append(entry.get("id", ""))
        else:
            seen.append(entry)

    return seen, excluded_ids


def _bias_warnings(entries: list, total: int) -> list[dict]:
    warnings: list[dict] = []
    if total == 0:
        return warnings

    # Volume skew per customer
    cust_counts: dict[str, int] = defaultdict(int)
    for e in entries:
        cust_counts[e.get("customer_id", "")] += 1
    for cid, cnt in cust_counts.items():
        pct = cnt / total
        if pct > VOLUME_SKEW_THRESHOLD:
            warnings.append({
                "type": "volume_skew",
                "customer_id": cid,
                "message": (
                    f"Customer {cid} accounts for {round(pct * 100, 1)}% of feedback "
                    f"({cnt}/{total}). Themes may be biased toward their use case."
                ),
            })

    # Churned signal
    churned = sum(1 for e in entries if e.get("customer_status") == "churned")
    if total > 0 and churned / total > CHURNED_THRESHOLD:
        warnings.append({
            "type": "churned_signal",
            "churned_count": churned,
            "total": total,
            "message": (
                f"{round(churned / total * 100, 1)}% of feedback ({churned}/{total}) is from "
                "churned customers. Their priorities may not reflect current customer needs."
            ),
        })

    # Tier skew
    tier_counts: dict[str, int] = defaultdict(int)
    for e in entries:
        tier_counts[e.get("customer_tier", "unknown")] += 1
    for tier, cnt in tier_counts.items():
        if cnt / total > TIER_SKEW_THRESHOLD:
            warnings.append({
                "type": "tier_skew",
                "tier": tier,
                "message": (
                    f"Tier '{tier}' accounts for {round(cnt / total * 100, 1)}% of feedback "
                    f"({cnt}/{total}). Verify this represents your target segment."
                ),
            })

    return warnings


# ---------------------------------------------------------------------------
# Main implementation
# ---------------------------------------------------------------------------

def analyze_feedback_impl(
    feedback: list,
    group_by: str = "theme",
    customer_tier: Optional[str] = None,
    include_churned: bool = True,
    top_n: int = 10,
    min_sentiment: Optional[float] = None,
) -> dict:
    """Analyse customer feedback, extract themes, and surface data-quality warnings.

    Args:
        feedback:         Loaded customer_feedback.json list.
        group_by:         "theme" (default) groups by detected topic.
                          "customer" groups by submitting customer.
        customer_tier:    Optional filter: "enterprise", "mid_market", or "startup".
        include_churned:  If False, exclude feedback from churned customers entirely.
        top_n:            Number of top themes / customers to return (default 10).
        min_sentiment:    Optional lower-bound sentiment filter (-1.0 to 1.0).

    Returns:
        dict with keys:
            themes / customers    – top results
            bias_warnings         – data quality flags
            duplicate_ids_excluded
            total_entries_analyzed
            group_by
    """
    # ---- Filter ----
    filtered = list(feedback)
    if customer_tier:
        filtered = [f for f in filtered if f.get("customer_tier") == customer_tier]
    if not include_churned:
        filtered = [f for f in filtered if f.get("customer_status") != "churned"]
    if min_sentiment is not None:
        filtered = [f for f in filtered if (f.get("sentiment_score") or 0.0) >= min_sentiment]

    # ---- Deduplication ----
    unique_entries, dup_ids = _deduplicate(filtered)
    total = len(unique_entries)

    if total == 0:
        return {
            "themes" if group_by != "customer" else "customers": [],
            "bias_warnings": [],
            "duplicate_ids_excluded": dup_ids,
            "total_entries_analyzed": 0,
            "group_by": group_by,
        }

    # Attach detected themes to each entry (mutates local copies only)
    for entry in unique_entries:
        entry["_themes"] = _detect_themes(entry.get("text", ""))

    if group_by == "customer":
        return _aggregate_by_customer(unique_entries, dup_ids, top_n)
    return _aggregate_by_theme(unique_entries, dup_ids, top_n, total)


def _aggregate_by_theme(unique_entries, dup_ids, top_n, total) -> dict:
    theme_map: dict[str, dict] = defaultdict(lambda: {
        "count": 0,
        "customers": set(),
        "entry_ids": [],
        "churned_count": 0,
        "arr_sum": 0,
        "sentiment_sum": 0.0,
        "tier_counts": defaultdict(int),
    })

    for entry in unique_entries:
        for theme in entry["_themes"]:
            t = theme_map[theme]
            t["count"] += 1
            t["customers"].add(entry.get("customer_id", ""))
            t["entry_ids"].append(entry.get("id", ""))
            if entry.get("customer_status") == "churned":
                t["churned_count"] += 1
            t["arr_sum"] += entry.get("arr", 0)
            t["sentiment_sum"] += entry.get("sentiment_score", 0.0)
            t["tier_counts"][entry.get("customer_tier", "unknown")] += 1

    # Sort: count desc, theme name asc for determinism
    sorted_themes = sorted(
        theme_map.items(),
        key=lambda x: (-x[1]["count"], x[0]),
    )[:top_n]

    themes_out = []
    for theme, data in sorted_themes:
        n = data["count"]
        themes_out.append({
            "theme": theme,
            "count": n,
            "unique_customers": len(data["customers"]),
            "representative_ids": data["entry_ids"][:3],
            "avg_sentiment": round(data["sentiment_sum"] / n, 3) if n else 0.0,
            "total_arr": data["arr_sum"],
            "churned_count": data["churned_count"],
            "churned_pct": round(data["churned_count"] / n * 100, 1) if n else 0.0,
            "tier_breakdown": dict(data["tier_counts"]),
        })

    return {
        "themes": themes_out,
        "bias_warnings": _bias_warnings(unique_entries, total),
        "duplicate_ids_excluded": dup_ids,
        "total_entries_analyzed": total,
        "group_by": "theme",
    }


def _aggregate_by_customer(unique_entries, dup_ids, top_n) -> dict:
    customer_map: dict[str, dict] = defaultdict(lambda: {
        "name": "",
        "tier": "",
        "status": "",
        "arr": 0,
        "count": 0,
        "themes": set(),
        "entry_ids": [],
        "sentiment_sum": 0.0,
    })

    for entry in unique_entries:
        cid = entry.get("customer_id", "unknown")
        c = customer_map[cid]
        c["name"] = entry.get("customer_name", "")
        c["tier"] = entry.get("customer_tier", "")
        c["status"] = entry.get("customer_status", "")
        c["arr"] = max(c["arr"], entry.get("arr", 0))
        c["count"] += 1
        c["entry_ids"].append(entry.get("id", ""))
        c["sentiment_sum"] += entry.get("sentiment_score", 0.0)
        for theme in entry.get("_themes", []):
            c["themes"].add(theme)

    sorted_customers = sorted(
        customer_map.items(),
        key=lambda x: (-x[1]["count"], x[0]),
    )[:top_n]

    customers_out = []
    for cid, data in sorted_customers:
        n = data["count"]
        customers_out.append({
            "customer_id": cid,
            "customer_name": data["name"],
            "tier": data["tier"],
            "status": data["status"],
            "arr": data["arr"],
            "feedback_count": n,
            "top_themes": sorted(data["themes"])[:5],
            "avg_sentiment": round(data["sentiment_sum"] / n, 3) if n else 0.0,
            "entry_ids": data["entry_ids"][:5],
        })

    total = len(unique_entries)
    return {
        "customers": customers_out,
        "bias_warnings": _bias_warnings(unique_entries, total),
        "duplicate_ids_excluded": dup_ids,
        "total_entries_analyzed": total,
        "group_by": "customer",
    }
