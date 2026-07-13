"""
Tests for tools/prioritize_backlog.py — full branch coverage.
"""

import pytest

from tools.prioritize_backlog import (
    STALE_DAYS,
    _days_since,
    _feedback_reach,
    _keywords,
    prioritize_backlog_impl,
)

# ---------------------------------------------------------------------------
# Date helpers that don't depend on today's actual date
# ---------------------------------------------------------------------------
STALE_DATE = "2020-01-01"  # always > 90 days before any 2026+ run date
FRESH_DATE = "2099-01-01"  # future → negative days → never stale


# ---------------------------------------------------------------------------
# Item / feedback factory helpers
# ---------------------------------------------------------------------------


def _item(**kw):
    """Minimal backlog item; all grading-relevant fields overridable."""
    base = {
        "id": "BP-001",
        "title": "xyz qrs",  # 3-char words → no keywords from title by default
        "status": "planned",
        "priority": "P1",
        "effort_points": 5,
        "business_value_score": 5,
        "confidence_score": 5,
        "last_updated": FRESH_DATE,
        "tags": [],
        "dependencies": [],
        "squad_assignment": "platform",
    }
    base.update(kw)
    return base


def _fb(customer_id="CUST-01", text="generic feedback text"):
    return {"id": f"FB-{customer_id}", "customer_id": customer_id, "text": text}


# ===========================================================================
# _keywords
# ===========================================================================


class TestKeywords:
    def test_empty_item_returns_empty(self):
        assert _keywords({}) == set()

    def test_tags_split_on_hyphens(self):
        kw = _keywords({"tags": ["api-integrations"], "title": ""})
        assert "api" in kw
        assert "integrations" in kw
        assert "api-integrations" in kw

    def test_tags_split_on_underscores(self):
        kw = _keywords({"tags": ["platform_core"], "title": ""})
        assert "platform" in kw
        assert "core" in kw

    def test_title_minimum_4_chars(self):
        kw = _keywords({"tags": [], "title": "API rate limiting"})
        # "api" → 3 chars → excluded; "rate" → 4 → included; "limiting" → included
        assert "rate" in kw
        assert "limiting" in kw
        assert "api" not in kw

    def test_tags_and_title_combined(self):
        kw = _keywords({"tags": ["security"], "title": "auth overhaul"})
        assert "security" in kw
        assert "auth" in kw  # exactly 4 chars
        assert "overhaul" in kw


# ===========================================================================
# _feedback_reach
# ===========================================================================


class TestFeedbackReach:
    def test_empty_keywords_returns_zero(self):
        item = {"title": "hi", "tags": []}  # no 4+ char words, no tags
        assert _feedback_reach(item, [_fb("C1", "api test")]) == 0

    def test_no_matching_feedback_returns_zero(self):
        item = {"title": "auth revamp", "tags": ["auth"]}
        assert _feedback_reach(item, [_fb("C1", "xyz qrs uvw")]) == 0

    def test_counts_unique_customers_only(self):
        item = {"title": "", "tags": ["auth"]}
        fb = [
            _fb("C1", "auth is broken"),
            _fb("C2", "auth issue here"),
            _fb("C1", "more auth problems"),  # same customer → not counted twice
        ]
        assert _feedback_reach(item, fb) == 2  # C1 and C2

    def test_empty_feedback_list_returns_zero(self):
        item = {"title": "auth security", "tags": ["auth"]}
        assert _feedback_reach(item, []) == 0

    def test_fallback_to_id_field_when_no_customer_id(self):
        item = {"title": "", "tags": ["auth"]}
        fb = [{"id": "FB-1", "text": "auth problem"}]  # no customer_id
        assert _feedback_reach(item, fb) == 1


# ===========================================================================
# _days_since
# ===========================================================================


class TestDaysSince:
    def test_old_date_large_positive(self):
        assert _days_since("2020-01-01") > 365 * 2

    def test_future_date_negative(self):
        assert _days_since("2099-01-01") < 0

    def test_invalid_string_returns_zero(self):
        assert _days_since("not-a-date") == 0

    def test_empty_string_returns_zero(self):
        assert _days_since("") == 0


# ===========================================================================
# prioritize_backlog_impl
# ===========================================================================


class TestPrioritizeBacklogImpl:
    # --- basics ---

    def test_empty_backlog(self):
        r = prioritize_backlog_impl([], [])
        assert r["ranked_items"] == []
        assert r["summary"]["total_ranked"] == 0

    def test_excludes_done_by_default(self):
        items = [_item(id="BP-001", status="done"), _item(id="BP-002", status="planned")]
        ids = {r["id"] for r in prioritize_backlog_impl(items, [])["ranked_items"]}
        assert "BP-001" not in ids
        assert "BP-002" in ids

    def test_includes_done_when_requested(self):
        items = [_item(id="BP-001", status="done"), _item(id="BP-002", status="planned")]
        ids = {
            r["id"] for r in prioritize_backlog_impl(items, [], include_done=True)["ranked_items"]
        }
        assert "BP-001" in ids and "BP-002" in ids

    def test_squad_filter_keeps_matching(self):
        items = [
            _item(id="BP-001", squad_assignment="platform"),
            _item(id="BP-002", squad_assignment="growth"),
        ]
        ids = {
            r["id"]
            for r in prioritize_backlog_impl(items, [], squad_filter="platform")["ranked_items"]
        }
        assert ids == {"BP-001"}

    def test_squad_filter_none_returns_all(self):
        items = [_item(id="BP-001"), _item(id="BP-002")]
        r = prioritize_backlog_impl(items, [], squad_filter=None)
        assert len(r["ranked_items"]) == 2

    # --- scoring methods ---

    def test_method_value_effort(self):
        item = _item(
            id="BP-001", business_value_score=8, confidence_score=8, effort_points=4, priority="P1"
        )
        r = prioritize_backlog_impl([item], [], method="value_effort")["ranked_items"][0]
        # score = (8 * 0.8) / 4 * 3 = 4.8
        assert r["score"] == pytest.approx(4.8, abs=0.01)

    def test_method_rice_uses_reach(self):
        item = _item(
            id="BP-001",
            title="auth security",
            tags=["auth"],
            business_value_score=9,
            confidence_score=9,
            effort_points=3,
            priority="P0",
        )
        fb = [_fb("C1", "auth login problem"), _fb("C2", "security auth issue")]
        r = prioritize_backlog_impl([item], fb)["ranked_items"][0]
        # reach=2, impact=9, conf=0.9, effort=3, priority_mult=4
        # score = 2*9*0.9/3 * 4 = 21.6
        assert r["score_components"]["reach_customers"] == 2
        assert r["score"] == pytest.approx(21.6, abs=0.01)

    # --- effort edge cases ---

    def test_zero_effort_treated_as_one(self):
        item = _item(id="BP-001", effort_points=0)
        r = prioritize_backlog_impl([item], [], method="value_effort")["ranked_items"][0]
        assert r["score_components"]["effort"] == 1

    def test_none_effort_treated_as_one(self):
        item = _item(id="BP-001")
        item["effort_points"] = None  # type: ignore[assignment]
        r = prioritize_backlog_impl([item], [], method="value_effort")["ranked_items"][0]
        assert r["score_components"]["effort"] == 1

    # --- unknown priority ---

    def test_unknown_priority_uses_default_multiplier(self):
        item = _item(id="BP-001", priority="CUSTOM")
        r = prioritize_backlog_impl([item], [])["ranked_items"][0]
        assert r["score_components"]["priority_multiplier"] == 2

    # --- flags ---

    def test_executive_priority_flag_and_boost(self):
        base = _item(
            id="BP-001",
            tags=[],
            business_value_score=5,
            confidence_score=5,
            effort_points=1,
            priority="P1",
        )
        exec_item = _item(
            id="BP-002",
            tags=["executive-priority"],
            business_value_score=5,
            confidence_score=5,
            effort_points=1,
            priority="P1",
        )
        # Use value_effort to avoid zero RICE when reach=0
        result = prioritize_backlog_impl([base, exec_item], [], method="value_effort")
        by_id = {r["id"]: r for r in result["ranked_items"]}
        assert "executive-priority" in by_id["BP-002"]["flags"]
        assert by_id["BP-002"]["score"] > by_id["BP-001"]["score"]

    def test_stale_flag_on_old_item(self):
        item = _item(id="BP-001", last_updated=STALE_DATE)
        r = prioritize_backlog_impl([item], [])["ranked_items"][0]
        assert "stale" in r["flags"]

    def test_stale_flag_absent_on_future_date(self):
        item = _item(id="BP-001", last_updated=FRESH_DATE)
        r = prioritize_backlog_impl([item], [])["ranked_items"][0]
        assert "stale" not in r["flags"]

    def test_stale_flag_absent_when_no_last_updated(self):
        item = _item(id="BP-001")
        item["last_updated"] = None  # type: ignore[assignment]
        r = prioritize_backlog_impl([item], [])["ranked_items"][0]
        assert "stale" not in r["flags"]

    def test_unestimated_flag(self):
        item = _item(id="BP-001", effort_points=0)
        r = prioritize_backlog_impl([item], [])["ranked_items"][0]
        assert "unestimated" in r["flags"]

    def test_no_customer_signal_flag(self):
        item = _item(id="BP-001", tags=[], title="xyz qrs")
        r = prioritize_backlog_impl([item], [])["ranked_items"][0]  # no feedback
        assert "no_customer_signal" in r["flags"]

    # --- dependency checks ---

    def test_done_dependency_does_not_flag_blocker(self):
        done = _item(id="BP-000", status="done")
        dependent = _item(id="BP-001", status="planned", dependencies=["BP-000"])
        result = prioritize_backlog_impl([done, dependent], [])
        bp001 = next(r for r in result["ranked_items"] if r["id"] == "BP-001")
        assert not bp001["has_unresolved_blocker"]

    def test_blocked_by_flag_for_undone_dependency(self):
        blocker = _item(id="BP-000", status="planned")
        dependent = _item(id="BP-001", dependencies=["BP-000"])
        result = prioritize_backlog_impl([blocker, dependent], [])
        bp001 = next(r for r in result["ranked_items"] if r["id"] == "BP-001")
        assert bp001["has_unresolved_blocker"]
        assert any(f.startswith("blocked_by:BP-000") for f in bp001["flags"])

    def test_missing_dependency_flag(self):
        item = _item(id="BP-001", dependencies=["BP-999"])  # BP-999 not in backlog
        result = prioritize_backlog_impl([item], [])
        r = result["ranked_items"][0]
        assert r["has_unresolved_blocker"]
        assert any("missing_dependency" in f for f in r["flags"])

    def test_dependency_check_false_suppresses_flags(self):
        blocker = _item(id="BP-000", status="planned")
        dependent = _item(id="BP-001", dependencies=["BP-000"])
        result = prioritize_backlog_impl([blocker, dependent], [], include_dependency_check=False)
        bp001 = next(r for r in result["ranked_items"] if r["id"] == "BP-001")
        assert not bp001["has_unresolved_blocker"]
        assert not any("blocked_by" in f for f in bp001["flags"])

    # --- sorting and top_n ---

    def test_blocked_items_pushed_to_bottom(self):
        blocker = _item(id="BP-000")
        blocked = _item(id="BP-001", priority="P0", dependencies=["BP-000"])
        free = _item(id="BP-002", priority="P3")
        ids = [
            r["id"] for r in prioritize_backlog_impl([blocker, blocked, free], [])["ranked_items"]
        ]
        assert ids[-1] == "BP-001"  # P0 blocked item still sorted to end

    def test_top_n_limits_output(self):
        items = [_item(id=f"BP-{i:03d}") for i in range(10)]
        r = prioritize_backlog_impl(items, [], top_n=4)
        assert len(r["ranked_items"]) == 4

    def test_deterministic_id_tiebreaker(self):
        # Same score components and same priority → sort by id asc
        a = _item(
            id="BP-AAA", priority="P2", business_value_score=5, confidence_score=5, effort_points=5
        )
        b = _item(
            id="BP-ZZZ", priority="P2", business_value_score=5, confidence_score=5, effort_points=5
        )
        ids = [r["id"] for r in prioritize_backlog_impl([b, a], [])["ranked_items"]]
        assert ids == ["BP-AAA", "BP-ZZZ"]

    def test_summary_flags_counts(self):
        items = [
            _item(id="BP-001", last_updated=STALE_DATE),
            _item(id="BP-002", effort_points=0),
            _item(id="BP-003", tags=["executive-priority"]),
        ]
        s = prioritize_backlog_impl(items, [])["summary"]["flags_summary"]
        assert s["stale"] == 1
        assert s["unestimated"] == 1
        assert s["executive_priority"] == 1
