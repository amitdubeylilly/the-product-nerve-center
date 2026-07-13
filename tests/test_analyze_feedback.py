"""
Tests for tools/analyze_feedback.py — full branch coverage.
"""

import pytest

from tools.analyze_feedback import (
    CHURNED_THRESHOLD,
    STALE_DEDUP_DAYS,
    TIER_SKEW_THRESHOLD,
    VOLUME_SKEW_THRESHOLD,
    _bias_warnings,
    _deduplicate,
    _detect_themes,
    _jaccard,
    _parse_date,
    _word_set,
    analyze_feedback_impl,
)

# ---------------------------------------------------------------------------
# Feedback entry factory
# ---------------------------------------------------------------------------


def _fb(
    id="FB-001",
    customer_id="CUST-01",
    text="generic feedback text",
    date="2026-06-01",
    customer_tier="enterprise",
    customer_status="active",
    arr=10000,
    sentiment_score=0.0,
    source="support_ticket",
):
    return {
        "id": id,
        "customer_id": customer_id,
        "text": text,
        "date": date,
        "customer_tier": customer_tier,
        "customer_status": customer_status,
        "arr": arr,
        "sentiment_score": sentiment_score,
        "customer_name": f"Company {customer_id}",
        "source": source,
    }


# ===========================================================================
# _word_set
# ===========================================================================


class TestWordSet:
    def test_empty_string(self):
        assert _word_set("") == set()

    def test_extracts_lowercase_words(self):
        assert _word_set("Hello World") == {"hello", "world"}

    def test_strips_punctuation(self):
        assert _word_set("api, auth!") == {"api", "auth"}


# ===========================================================================
# _jaccard
# ===========================================================================


class TestJaccard:
    def test_empty_a_returns_zero(self):
        assert _jaccard(set(), {"a"}) == 0.0

    def test_empty_b_returns_zero(self):
        assert _jaccard({"a"}, set()) == 0.0

    def test_no_overlap(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_full_overlap(self):
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_partial_overlap(self):
        # |{b}| / |{a,b,c}| = 1/3
        result = _jaccard({"a", "b"}, {"b", "c"})
        assert result == pytest.approx(1 / 3)


# ===========================================================================
# _parse_date
# ===========================================================================


class TestParseDate:
    def test_valid_date(self):
        d = _parse_date("2026-06-01")
        assert d is not None
        assert d.year == 2026 and d.month == 6 and d.day == 1

    def test_invalid_string_returns_none(self):
        assert _parse_date("not-a-date") is None

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None


# ===========================================================================
# _detect_themes
# ===========================================================================


class TestDetectThemes:
    def test_api_theme_matched(self):
        themes = _detect_themes("the api integration is broken")
        assert "api_integrations" in themes

    def test_no_match_returns_other(self):
        themes = _detect_themes("zzz www qqq unrecognized")
        assert themes == ["other"]

    def test_multiple_themes_detected(self):
        themes = _detect_themes("api is slow and performance is degraded")
        assert "api_integrations" in themes
        assert "performance" in themes

    def test_single_theme_only(self):
        themes = _detect_themes("auth login issue")
        assert "authentication_security" in themes
        assert len(themes) >= 1


# ===========================================================================
# _deduplicate
# ===========================================================================


class TestDeduplicate:
    def test_different_customers_not_deduped(self):
        entries = [
            _fb("FB-1", "C1", "the api is slow"),
            _fb("FB-2", "C2", "the api is slow"),  # same text, diff customer
        ]
        unique, dups = _deduplicate(entries)
        assert len(unique) == 2
        assert dups == []

    def test_same_customer_similar_text_within_window_is_dup(self):
        entries = [
            _fb("FB-1", "C1", "the api is slow", "2026-06-01"),
            _fb("FB-2", "C1", "the api is slow today", "2026-06-05"),  # 4 days → dup
        ]
        unique, dups = _deduplicate(entries)
        assert len(unique) == 1
        assert "FB-2" in dups

    def test_same_customer_low_similarity_not_dup(self):
        entries = [
            _fb("FB-1", "C1", "api is broken now", "2026-06-01"),
            _fb("FB-2", "C1", "onboarding wizard totally different topic", "2026-06-03"),
        ]
        unique, dups = _deduplicate(entries)
        assert len(unique) == 2
        assert dups == []

    def test_same_customer_outside_14_day_window_not_dup(self):
        entries = [
            _fb("FB-1", "C1", "the api is slow", "2026-01-01"),
            _fb("FB-2", "C1", "the api is slow today", "2026-02-01"),  # 31 days
        ]
        unique, dups = _deduplicate(entries)
        assert len(unique) == 2

    def test_missing_dates_falls_through_to_jaccard(self):
        # No date → skip date check, rely solely on Jaccard
        entries = [
            _fb("FB-1", "C1", "the api is slow", date=""),
            _fb("FB-2", "C1", "the api is slow today", date=""),
        ]
        unique, dups = _deduplicate(entries)
        # Jaccard("the api is slow", "the api is slow today") = 4/5 = 0.8 ≥ 0.7
        assert len(unique) == 1
        assert "FB-2" in dups

    def test_entry_date_none_prev_date_valid_falls_to_jaccard(self):
        # entry has no date, prev has date → if entry_date and prev_date = False → Jaccard
        entries = [
            _fb("FB-1", "C1", "the api is slow", date="2026-06-01"),
            _fb("FB-2", "C1", "the api is slow today", date=""),  # entry_date=None
        ]
        unique, dups = _deduplicate(entries)
        assert len(unique) == 1
        assert "FB-2" in dups

    def test_empty_entries(self):
        unique, dups = _deduplicate([])
        assert unique == []
        assert dups == []


# ===========================================================================
# _bias_warnings
# ===========================================================================


class TestBiasWarnings:
    def test_empty_total_returns_no_warnings(self):
        assert _bias_warnings([], 0) == []

    def test_volume_skew_triggered(self):
        # 3 entries, 1 customer has 2 (66 % > 25 %)
        entries = [
            _fb("FB-1", "SKEW-CUST"),
            _fb("FB-2", "SKEW-CUST"),
            _fb("FB-3", "OTHER-CUST"),
        ]
        warnings = _bias_warnings(entries, 3)
        types = [w["type"] for w in warnings]
        assert "volume_skew" in types

    def test_volume_skew_not_triggered_below_threshold(self):
        entries = [_fb(f"FB-{i}", f"CUST-{i}") for i in range(10)]
        warnings = _bias_warnings(entries, 10)
        assert not any(w["type"] == "volume_skew" for w in warnings)

    def test_churned_signal_triggered(self):
        entries = [
            _fb("FB-1", customer_status="churned"),
            _fb("FB-2", customer_status="churned"),
            _fb("FB-3", customer_status="active"),
        ]
        warnings = _bias_warnings(entries, 3)
        assert any(w["type"] == "churned_signal" for w in warnings)

    def test_churned_signal_not_triggered_below_threshold(self):
        entries = [
            _fb("FB-1", customer_status="churned"),
            _fb("FB-2", customer_status="active"),
            _fb("FB-3", customer_status="active"),
            _fb("FB-4", customer_status="active"),
            _fb("FB-5", customer_status="active"),
            _fb("FB-6", customer_status="active"),
        ]
        warnings = _bias_warnings(entries, 6)
        assert not any(w["type"] == "churned_signal" for w in warnings)

    def test_tier_skew_triggered(self):
        # 4 enterprise out of 5 total = 80 % > 60 %
        entries = [_fb(f"FB-{i}", customer_tier="enterprise") for i in range(4)] + [
            _fb("FB-5", customer_tier="startup")
        ]
        warnings = _bias_warnings(entries, 5)
        assert any(w["type"] == "tier_skew" for w in warnings)

    def test_tier_skew_not_triggered_below_threshold(self):
        entries = [
            _fb("FB-1", customer_tier="enterprise"),
            _fb("FB-2", customer_tier="enterprise"),
            _fb("FB-3", customer_tier="startup"),
            _fb("FB-4", customer_tier="mid_market"),
        ]
        warnings = _bias_warnings(entries, 4)
        assert not any(w["type"] == "tier_skew" for w in warnings)


# ===========================================================================
# analyze_feedback_impl
# ===========================================================================


class TestAnalyzeFeedbackImpl:
    def test_empty_feedback_returns_empty_themes(self):
        r = analyze_feedback_impl([])
        assert r["themes"] == []
        assert r["total_entries_analyzed"] == 0

    def test_empty_feedback_group_by_customer(self):
        r = analyze_feedback_impl([], group_by="customer")
        assert r["customers"] == []

    def test_group_by_theme_default(self):
        entries = [_fb("FB-1", text="api integration webhook")]
        r = analyze_feedback_impl(entries)
        assert "themes" in r
        assert any(t["theme"] == "api_integrations" for t in r["themes"])

    def test_group_by_customer(self):
        entries = [
            _fb("FB-1", "C1", text="api slow"),
            _fb("FB-2", "C1", text="api broken"),
            _fb("FB-3", "C2", text="auth issue"),
        ]
        r = analyze_feedback_impl(entries, group_by="customer", top_n=5)
        assert "customers" in r
        ids = [c["customer_id"] for c in r["customers"]]
        assert "C1" in ids
        assert "C2" in ids

    def test_customer_tier_filter(self):
        entries = [
            _fb("FB-1", customer_tier="enterprise"),
            _fb("FB-2", customer_tier="startup"),
        ]
        r = analyze_feedback_impl(entries, customer_tier="enterprise")
        assert r["total_entries_analyzed"] == 1

    def test_include_churned_false_excludes_churned(self):
        entries = [
            _fb("FB-1", customer_status="churned"),
            _fb("FB-2", customer_status="active"),
        ]
        r = analyze_feedback_impl(entries, include_churned=False)
        assert r["total_entries_analyzed"] == 1

    def test_min_sentiment_filter(self):
        entries = [
            _fb("FB-1", sentiment_score=-0.8),
            _fb("FB-2", sentiment_score=0.5),
        ]
        r = analyze_feedback_impl(entries, min_sentiment=0.0)
        assert r["total_entries_analyzed"] == 1

    def test_top_n_limits_results(self):
        # Generate 15 entries with distinct themes by varying text
        entries = [
            _fb(f"FB-{i}", f"CUST-{i}", text=f"api auth deploy incident {i}") for i in range(15)
        ]
        r = analyze_feedback_impl(entries, top_n=3)
        assert len(r["themes"]) <= 3

    def test_near_duplicate_excluded_from_count(self):
        entries = [
            _fb("FB-1", "C1", "api is slow", "2026-06-01"),
            _fb("FB-2", "C1", "api is slow today", "2026-06-03"),  # near-dup
        ]
        r = analyze_feedback_impl(entries)
        assert "FB-2" in r["duplicate_ids_excluded"]
        assert r["total_entries_analyzed"] == 1

    def test_theme_includes_churned_count(self):
        entries = [
            _fb("FB-1", customer_status="churned", text="api is down"),
            _fb("FB-2", customer_status="active", text="api broken"),
        ]
        r = analyze_feedback_impl(entries)
        api_theme = next((t for t in r["themes"] if t["theme"] == "api_integrations"), None)
        assert api_theme is not None
        assert api_theme["churned_count"] == 1

    def test_customer_summary_includes_top_themes(self):
        entries = [
            _fb("FB-1", "C1", text="api slow auth issue"),
            _fb("FB-2", "C1", text="api broken again"),
        ]
        r = analyze_feedback_impl(entries, group_by="customer", top_n=5)
        c1 = next(c for c in r["customers"] if c["customer_id"] == "C1")
        assert c1["feedback_count"] == 2
        assert len(c1["top_themes"]) >= 1

    def test_bias_warnings_present_in_output(self):
        entries = [
            _fb("FB-1", "SKEW", text="api"),
            _fb("FB-2", "SKEW", text="api"),
            _fb("FB-3", "OTHER", text="auth"),
        ]
        r = analyze_feedback_impl(entries)
        assert "bias_warnings" in r

    def test_source_filter(self):
        entries = [
            _fb("FB-1", source="support_ticket", text="api slow"),
            _fb("FB-2", source="nps_survey", text="api slow"),
        ]
        r = analyze_feedback_impl(entries, source="support_ticket")
        assert r["total_entries_analyzed"] == 1

    def test_time_range_start_and_end(self):
        entries = [
            _fb("FB-1", date="2026-01-01", text="api issue"),
            _fb("FB-2", date="2026-06-01", text="api issue"),
            _fb("FB-3", date="2026-12-01", text="api issue"),
        ]
        r = analyze_feedback_impl(entries, time_range={"start": "2026-03-01", "end": "2026-09-30"})
        assert r["total_entries_analyzed"] == 1

    def test_time_range_start_only(self):
        entries = [
            _fb("FB-1", date="2026-01-01", text="api issue"),
            _fb("FB-2", date="2026-06-01", text="api issue"),
        ]
        r = analyze_feedback_impl(entries, time_range={"start": "2026-03-01"})
        assert r["total_entries_analyzed"] == 1

    def test_time_range_end_only(self):
        entries = [
            _fb("FB-1", date="2026-01-01", text="api issue"),
            _fb("FB-2", date="2026-06-01", text="api issue"),
        ]
        r = analyze_feedback_impl(entries, time_range={"end": "2026-03-31"})
        assert r["total_entries_analyzed"] == 1
