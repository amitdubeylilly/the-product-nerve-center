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

    def test_prioritize_backlog_squad_filter(self):
        r = server.prioritize_backlog(squad_filter="platform", top_n=5)
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

    def test_map_dependencies_empty_item_ids_returns_error(self):
        r = server.map_dependencies(item_ids=[])
        assert "error" in r
