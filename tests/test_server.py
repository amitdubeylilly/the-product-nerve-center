"""
Tests for server.py — verifies data loading, _load helpers, and tool wrappers.
"""

import json

import pytest

import server

# ===========================================================================
# Startup / data loading
# ===========================================================================


class TestStartupDataLoading:
    def test_backlog_loaded(self):
        assert isinstance(server.BACKLOG, list)
        assert len(server.BACKLOG) > 0

    def test_feedback_loaded(self):
        assert isinstance(server.FEEDBACK, list)
        assert len(server.FEEDBACK) > 0

    def test_sprint_history_loaded(self):
        assert isinstance(server.SPRINT_HISTORY, list)
        assert len(server.SPRINT_HISTORY) > 0

    def test_roster_loaded(self):
        assert isinstance(server.ROSTER, list)
        assert len(server.ROSTER) > 0

    def test_dependencies_loaded(self):
        assert isinstance(server.DEPENDENCIES, list)
        assert len(server.DEPENDENCIES) > 0

    def test_four_tools_registered(self):
        names = {t.name for t in server.mcp._tool_manager.list_tools()}
        assert "prioritize_backlog" in names
        assert "analyze_feedback" in names
        assert "assess_capacity" in names
        assert "map_dependencies" in names


# ===========================================================================
# _load helper
# ===========================================================================


class TestLoad:
    def test_load_existing_file_returns_list(self):
        # product_backlog.json exists in data/ directory
        result = server._load("product_backlog.json")
        assert isinstance(result, list)

    def test_load_missing_file_raises_with_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "DATA_DIR", tmp_path)
        with pytest.raises(FileNotFoundError, match="Data file not found"):
            server._load("does_not_exist.json")


# ===========================================================================
# _load_with_fallback helper
# ===========================================================================


class TestLoadWithFallback:
    def test_primary_used_when_it_exists(self, tmp_path, monkeypatch):
        (tmp_path / "primary.json").write_text(json.dumps(["item_a", "item_b"]))
        monkeypatch.setattr(server, "DATA_DIR", tmp_path)
        result = server._load_with_fallback("primary.json", "fallback.json")
        assert result == ["item_a", "item_b"]

    def test_fallback_used_when_primary_missing(self, tmp_path, monkeypatch):
        (tmp_path / "fallback.json").write_text(json.dumps([{"id": "X"}]))
        monkeypatch.setattr(server, "DATA_DIR", tmp_path)
        result = server._load_with_fallback("missing_primary.json", "fallback.json")
        assert result == [{"id": "X"}]

    def test_both_missing_raises_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "DATA_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            server._load_with_fallback("a.json", "b.json")


# ===========================================================================
# Tool wrapper functions
# ===========================================================================


class TestToolWrappers:
    def test_prioritize_backlog_returns_ranked_items(self):
        r = server.prioritize_backlog(top_n=2)
        assert "ranked_items" in r
        assert len(r["ranked_items"]) <= 2

    def test_prioritize_backlog_with_filters_dict(self):
        r = server.prioritize_backlog(filters={"squad": "platform"}, top_n=3)
        for item in r["ranked_items"]:
            assert item["squad"] == "platform"

    def test_analyze_feedback_returns_themes(self):
        r = server.analyze_feedback(top_n=3)
        assert "themes" in r
        assert r["total_entries_analyzed"] > 0

    def test_analyze_feedback_group_by_customer(self):
        r = server.analyze_feedback(group_by="customer", top_n=3)
        assert "customers" in r

    def test_assess_capacity_returns_engineers(self):
        r = server.assess_capacity()
        assert "engineers" in r
        assert "team_totals" in r

    def test_assess_capacity_squad_filter(self):
        r = server.assess_capacity(squad="nonexistent_squad_xyz")
        assert r["engineers"] == []

    def test_map_dependencies_valid_items(self):
        backlog_id = server.BACKLOG[0]["id"]
        r = server.map_dependencies(item_ids=[backlog_id])
        assert "items" in r
        assert r["items"][0]["item_id"] == backlog_id

    def test_map_dependencies_empty_item_ids_defaults_to_planned(self):
        """Server-level: empty item_ids resolves to all planned/in_progress items."""
        r = server.map_dependencies(item_ids=[])
        assert "items" in r
        # impl-level validation still raises error; server fills ids before calling


# ===========================================================================
# _load_optional / _resolve
# ===========================================================================


class TestLoadOptionalAndResolve:
    def test_load_optional_returns_list_when_present(self):
        assert isinstance(server._load_optional("product_backlog.json"), list)

    def test_load_optional_returns_empty_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "DATA_DIR", tmp_path)
        assert server._load_optional("nope.json") == []

    def test_resolve_prefers_fetched(self):
        assert server._resolve([{"name": "X"}], "a.json", "b.json") == [{"name": "X"}]

    def test_resolve_uses_primary_file_when_fetch_empty(self, tmp_path, monkeypatch):
        (tmp_path / "p.json").write_text(json.dumps([{"name": "P"}]))
        monkeypatch.setattr(server, "DATA_DIR", tmp_path)
        assert server._resolve([], "p.json", "f.json") == [{"name": "P"}]

    def test_resolve_returns_empty_when_nothing_available(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "DATA_DIR", tmp_path)
        assert server._resolve([], "p.json", "f.json") == []


# ===========================================================================
# Data-server response parsers (used by the startup fetch)
# ===========================================================================


class TestDataServerParsers:
    def test_parse_members(self):
        assert server._parse_members("Team members: Rao, Mira, Otto") == ["Rao", "Mira", "Otto"]

    def test_parse_members_no_colon(self):
        assert server._parse_members("garbage") == []

    def test_parse_capacity(self):
        out = server._parse_capacity(
            "Rao — Capacity: 21 pts, Allocation: 100%, PTO this sprint: 0 days"
        )
        assert out == {
            "total_capacity_points": 21.0,
            "sprint_allocation_percent": 100,
            "pto_days_this_sprint": 0,
        }

    def test_parse_capacity_unparseable(self):
        assert server._parse_capacity("nothing here") == {}

    def test_parse_profile(self):
        assert server._parse_profile("Rao — Role: senior_engineer, Squad: core") == {
            "role": "senior_engineer",
            "squad": "core",
        }

    def test_parse_profile_missing(self):
        assert server._parse_profile("Rao — no fields") == {"role": "", "squad": ""}

    def test_parse_skills(self):
        assert server._parse_skills("Rao — Skills: backend, infra") == ["backend", "infra"]

    def test_parse_skills_none(self):
        assert server._parse_skills("Rao — no skills line") == []

    def test_parse_sprint_with_carry(self):
        out = server._parse_sprint(
            "Isa — Sprint assignments: NB-114, NB-115 | "
            "Carry-over: NB-114 (6pts, in_progress), NB-115 (5pts, in_progress)"
        )
        assert out["current_sprint_assignments"] == ["NB-114", "NB-115"]
        assert out["carry_over_items"] == [
            {"id": "NB-114", "points": 6, "status": "in_progress"},
            {"id": "NB-115", "points": 5, "status": "in_progress"},
        ]

    def test_parse_sprint_none(self):
        out = server._parse_sprint("Otto — Sprint assignments: none | Carry-over: none")
        assert out == {"current_sprint_assignments": [], "carry_over_items": []}

    def test_parse_sprint_no_labels(self):
        # neither "Carry-over:" nor "Sprint assignments:" present
        assert server._parse_sprint("Rao — idle") == {
            "current_sprint_assignments": [],
            "carry_over_items": [],
        }

    def test_parse_item_deps_none(self):
        assert server._parse_item_deps("NB-108", "NB-108 has no outgoing dependencies.") == []

    def test_parse_item_deps_empty_text(self):
        assert server._parse_item_deps("NB-108", "") == []

    def test_parse_item_deps_no_type_keyword(self):
        # target present but no type keyword -> defaults to "blocks", loop exhausts
        edges = server._parse_item_deps("NB-120", "NB-120 relates NB-121")
        assert edges[0]["target_item_id"] == "NB-121"
        assert edges[0]["dependency_type"] == "blocks"

    def test_parse_item_deps_populated(self):
        # Defensive/assumed populated format — documents what the parser expects.
        text = (
            "NB-120 -> NB-121 (blocks); "
            "NB-120 -> EXT-9 (external, team=Payments, eta=2026-07-01); junk"
        )
        edges = server._parse_item_deps("NB-120", text)
        assert len(edges) == 2
        assert edges[0]["target_item_id"] == "NB-121"
        assert edges[0]["dependency_type"] == "blocks"
        assert edges[0]["external_team"] is None
        assert edges[0]["external_eta"] is None
        assert edges[1]["target_item_id"] == "EXT-9"
        assert edges[1]["dependency_type"] == "external"
        assert edges[1]["external_team"] == "Payments"
        assert edges[1]["external_eta"] == "2026-07-01"

    def test_assemble_engineer(self):
        rec = server._assemble_engineer(
            "Rao",
            {
                "total_capacity_points": 21.0,
                "sprint_allocation_percent": 100,
                "pto_days_this_sprint": 0,
            },
            {"role": "senior_engineer", "squad": "core"},
            ["backend", "infra"],
            {
                "current_sprint_assignments": ["NB-108"],
                "carry_over_items": [{"id": "NB-108", "points": 5, "status": "in_progress"}],
            },
        )
        assert rec["name"] == "Rao"
        assert rec["squad"] == "core"
        assert rec["total_capacity_points"] == 21.0
        assert rec["skills"] == ["backend", "infra"]
        assert rec["carry_over_items"][0]["points"] == 5
