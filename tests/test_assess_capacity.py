"""
Tests for tools/assess_capacity.py — full branch coverage.
"""

import pytest

from tools.assess_capacity import (
    SPRINT_POINTS,
    _formula_str,
    _normalize,
    _to_float,
    _to_int,
    assess_capacity_impl,
)

# ---------------------------------------------------------------------------
# Engineer factory helpers
# ---------------------------------------------------------------------------


def _oracle_eng(**kw):
    """Engineer using oracle field names."""
    base = {
        "name": "Alice",
        "squad": "platform",
        "allocation_percent": 100,
        "pto_days": 0,
        "carry_over_points": 0,
        "skills": ["backend"],
    }
    base.update(kw)
    return base


def _sample_eng(**kw):
    """Engineer using sample_roster field names."""
    base = {
        "name": "Bob",
        "squad": "platform",
        "sprint_allocation_percent": 100,
        "pto_days_this_sprint": 0,
        "carry_over_items": [],
        "skills": ["frontend"],
    }
    base.update(kw)
    return base


# ===========================================================================
# _to_int / _to_float
# ===========================================================================


class TestCoercionHelpers:
    def test_to_int_returns_default_for_none(self):
        assert _to_int(None, 7) == 7

    def test_to_int_returns_default_for_invalid_value(self):
        assert _to_int({}, 7) == 7

    def test_to_float_returns_default_for_none(self):
        assert _to_float(None, 3.5) == 3.5

    def test_to_float_returns_default_for_invalid_value(self):
        assert _to_float({}, 3.5) == 3.5


# ===========================================================================
# _normalize
# ===========================================================================


class TestNormalize:
    def test_oracle_schema(self):
        raw = {
            "engineer_id": "Eve",
            "squad": "growth",
            "allocation_percent": 80,
            "pto_days": 2,
            "carry_over_points": 3,
            "skills": ["backend", "ml"],
        }
        eng = _normalize(raw)
        assert eng["name"] == "Eve"
        assert eng["squad"] == "growth"
        assert eng["allocation_percent"] == 80
        assert eng["pto_days"] == 2
        assert eng["carry_over_points"] == 3.0
        assert eng["skills"] == ["backend", "ml"]

    def test_sample_schema(self):
        raw = {
            "name": "SampleB",
            "squad": "experience",
            "sprint_allocation_percent": 50,
            "pto_days_this_sprint": 2,
            "carry_over_items": [{"id": "X", "points": 3}],
            "skills": ["frontend"],
        }
        eng = _normalize(raw)
        assert eng["name"] == "SampleB"
        assert eng["allocation_percent"] == 50
        assert eng["pto_days"] == 2
        assert eng["carry_over_points"] == 3.0

    def test_explicit_zero_allocation_not_overridden(self):
        # allocation_percent=0 is not None → should NOT fall back to sprint_allocation_percent
        raw = {
            "name": "X",
            "squad": "platform",
            "allocation_percent": 0,
            "sprint_allocation_percent": 80,
            "pto_days": 0,
            "carry_over_points": 0,
            "skills": [],
        }
        assert _normalize(raw)["allocation_percent"] == 0

    def test_missing_allocation_falls_back_to_sample_field(self):
        raw = {
            "name": "Y",
            "squad": "platform",
            "sprint_allocation_percent": 75,
            "pto_days_this_sprint": 1,
            "carry_over_items": [],
            "skills": [],
        }
        assert _normalize(raw)["allocation_percent"] == 75

    def test_defaults_when_all_fields_absent(self):
        eng = _normalize({"name": "Z", "squad": "platform"})
        assert eng["allocation_percent"] == 100
        assert eng["pto_days"] == 0
        assert eng["carry_over_points"] == 0.0

    def test_carry_over_from_items_list(self):
        raw = {
            "name": "W",
            "squad": "platform",
            "allocation_percent": 100,
            "pto_days": 0,
            "carry_over_items": [{"id": "A", "points": 2}, {"id": "B", "points": 5}],
            "skills": [],
        }
        assert _normalize(raw)["carry_over_points"] == 7.0


# ===========================================================================
# assess_capacity_impl
# ===========================================================================


class TestAssessCapacityImpl:
    # --- input validation ---

    def test_invalid_sprint_days_returns_error(self):
        r = assess_capacity_impl([], sprint_days=0)
        assert "error" in r

    def test_negative_sprint_days_returns_error(self):
        r = assess_capacity_impl([], sprint_days=-5)
        assert "error" in r

    # --- empty / no-match roster ---

    def test_empty_roster_returns_no_engineers_warning(self):
        r = assess_capacity_impl([], squad="platform")
        assert r["engineers"] == []
        assert any(w["type"] == "no_engineers" for w in r["warnings"])

    def test_squad_filter_no_match_returns_no_engineers(self):
        roster = [_oracle_eng(squad="platform")]
        r = assess_capacity_impl(roster, squad="growth")
        assert r["engineers"] == []

    # --- capacity formula correctness ---

    def test_sampleb_formula(self):
        """SampleB: 50 % alloc, 2 PTO days, 3 carry_over → known expected values."""
        roster = [
            {
                "name": "SampleB",
                "squad": "experience",
                "sprint_allocation_percent": 50,
                "pto_days_this_sprint": 2,
                "carry_over_items": [{"id": "SMP-2", "points": 3}],
                "skills": ["frontend"],
            }
        ]
        r = assess_capacity_impl(roster, sprint_days=10)
        eng = r["engineers"][0]
        assert eng["allocated_capacity"] == pytest.approx(10.5)
        assert eng["effective_capacity"] == pytest.approx(8.4)
        assert eng["available_capacity"] == pytest.approx(5.4)

    def test_full_allocation_no_pto_no_carryover(self):
        roster = [
            _oracle_eng(name="Alice", allocation_percent=100, pto_days=0, carry_over_points=0)
        ]
        eng = assess_capacity_impl(roster)["engineers"][0]
        assert eng["allocated_capacity"] == pytest.approx(21.0)
        assert eng["effective_capacity"] == pytest.approx(21.0)
        assert eng["available_capacity"] == pytest.approx(21.0)

    def test_carry_over_reduces_available(self):
        roster = [_oracle_eng(carry_over_points=5)]
        eng = assess_capacity_impl(roster)["engineers"][0]
        assert eng["available_capacity"] == pytest.approx(21.0 - 5)

    def test_available_never_negative(self):
        roster = [_oracle_eng(carry_over_points=999)]
        eng = assess_capacity_impl(roster)["engineers"][0]
        assert eng["available_capacity"] == 0.0

    # --- PTO ---

    def test_pto_capped_at_sprint_days(self):
        roster = [_oracle_eng(pto_days=15)]
        eng = assess_capacity_impl(roster, sprint_days=10)["engineers"][0]
        assert eng["pto_days"] == 10  # capped
        assert eng["effective_capacity"] == 0.0

    # --- per-engineer warnings ---

    def test_zero_allocation_warning(self):
        roster = [_oracle_eng(allocation_percent=0)]
        eng = assess_capacity_impl(roster)["engineers"][0]
        assert "zero_allocation" in eng["warnings"]

    def test_zero_effective_due_to_pto_warning(self):
        roster = [_oracle_eng(pto_days=10)]
        eng = assess_capacity_impl(roster, sprint_days=10)["engineers"][0]
        assert "zero_effective_due_to_pto" in eng["warnings"]

    def test_overloaded_warning(self):
        roster = [_oracle_eng(allocation_percent=50, carry_over_points=20)]
        eng = assess_capacity_impl(roster)["engineers"][0]
        assert any("overloaded" in w for w in eng["warnings"])

    def test_no_overloaded_when_effective_is_zero(self):
        # carry=5 but effective=0 (full PTO) → overloaded warning should NOT fire
        roster = [_oracle_eng(allocation_percent=100, pto_days=10, carry_over_points=5)]
        eng = assess_capacity_impl(roster, sprint_days=10)["engineers"][0]
        assert not any("overloaded" in w for w in eng["warnings"])

    def test_skill_mismatch_warning(self):
        roster = [_oracle_eng(skills=["frontend"])]
        eng = assess_capacity_impl(roster, required_skills=["backend"])["engineers"][0]
        assert any("skill_mismatch" in w for w in eng["warnings"])

    def test_skill_match_no_mismatch_warning(self):
        roster = [_oracle_eng(skills=["backend"])]
        eng = assess_capacity_impl(roster, required_skills=["backend"])["engineers"][0]
        assert not any("skill_mismatch" in w for w in eng["warnings"])

    # --- global warnings ---

    def test_global_overloaded_warning(self):
        roster = [_oracle_eng(allocation_percent=50, carry_over_points=20)]
        warnings = assess_capacity_impl(roster)["warnings"]
        assert any(w["type"] == "overloaded_engineers" for w in warnings)

    def test_global_zero_effective_warning(self):
        roster = [_oracle_eng(pto_days=10)]
        warnings = assess_capacity_impl(roster, sprint_days=10)["warnings"]
        assert any(w["type"] == "zero_effective_capacity" for w in warnings)

    def test_global_skill_mismatch_warning(self):
        roster = [_oracle_eng(skills=["frontend"])]
        warnings = assess_capacity_impl(roster, required_skills=["backend"])["warnings"]
        assert any(w["type"] == "skill_mismatch" for w in warnings)

    def test_global_no_warnings_for_healthy_team(self):
        roster = [_oracle_eng()]
        warnings = assess_capacity_impl(roster)["warnings"]
        assert warnings == []

    # --- squad totals ---

    def test_zero_alloc_excluded_from_squad_totals(self):
        roster = [
            _oracle_eng(name="Active", allocation_percent=100),
            _oracle_eng(name="Inactive", allocation_percent=0),
        ]
        r = assess_capacity_impl(roster)
        sq = r["squad_totals"]["platform"]
        # Only Active contributes 21 pts; Inactive is excluded
        assert sq["allocated"] == pytest.approx(21.0)
        assert sq["engineer_count"] == 2  # both counted for headcount

    def test_squad_totals_computed_correctly(self):
        roster = [
            _oracle_eng(name="A", squad="platform", allocation_percent=100),
            _oracle_eng(
                name="B", squad="growth", allocation_percent=50, pto_days=0, carry_over_points=0
            ),
        ]
        r = assess_capacity_impl(roster)
        assert "platform" in r["squad_totals"]
        assert "growth" in r["squad_totals"]

    def test_deterministic_sort_by_squad_then_name(self):
        roster = [
            _oracle_eng(name="Zoe", squad="platform"),
            _oracle_eng(name="Amy", squad="platform"),
            _oracle_eng(name="Bob", squad="growth"),
        ]
        names = [e["engineer"] for e in assess_capacity_impl(roster)["engineers"]]
        # growth before platform alphabetically; within platform Amy before Zoe
        assert names == ["Bob", "Amy", "Zoe"]

    def test_capacity_formula_in_output(self):
        r = assess_capacity_impl([_oracle_eng()])
        assert "capacity_formula" in r
        assert "21" in r["capacity_formula"]


# ===========================================================================
# _formula_str
# ===========================================================================


class TestFormulaStr:
    def test_returns_nonempty_string(self):
        s = _formula_str()
        assert isinstance(s, str)
        assert len(s) > 0
        assert "21" in s
        assert "allocation" in s
