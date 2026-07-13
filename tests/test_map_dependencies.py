"""
Tests for tools/map_dependencies.py — full branch coverage.
"""

import pytest

from tools.map_dependencies import (
    _build_graph,
    _critical_path,
    _find_cycle,
    _normalize_edge,
    _trace_item,
    map_dependencies_impl,
)

# ---------------------------------------------------------------------------
# Edge factory helpers
# ---------------------------------------------------------------------------


def _edge(source, target, dep_type="blocks", external_team=None, external_eta=None):
    """Sample-schema edge."""
    return {
        "source_item_id": source,
        "target_item_id": target,
        "dependency_type": dep_type,
        "external_team": external_team,
        "external_eta": external_eta,
    }


def _oracle_edge(item_id, target_id, dep_type="blocks", external_team=None, external_eta=None):
    """Oracle-schema edge."""
    return {
        "item_id": item_id,
        "target_id": target_id,
        "type": dep_type,
        "external_team": external_team,
        "external_eta": external_eta,
    }


# ===========================================================================
# _normalize_edge
# ===========================================================================


class TestNormalizeEdge:
    def test_sample_schema(self):
        e = _normalize_edge(_edge("A", "B", "blocks"))
        assert e["source"] == "A"
        assert e["target"] == "B"
        assert e["type"] == "blocks"

    def test_oracle_schema(self):
        e = _normalize_edge(_oracle_edge("X", "Y", "soft"))
        assert e["source"] == "X"
        assert e["target"] == "Y"
        assert e["type"] == "soft"

    def test_preserves_external_fields(self):
        e = _normalize_edge(_edge("A", "EXT-1", "external", "Team Alpha", "2026-09-01"))
        assert e["external_team"] == "Team Alpha"
        assert e["external_eta"] == "2026-09-01"

    def test_defaults_type_to_blocks(self):
        raw = {"source_item_id": "A", "target_item_id": "B"}
        e = _normalize_edge(raw)
        assert e["type"] == "blocks"


# ===========================================================================
# _build_graph
# ===========================================================================


class TestBuildGraph:
    def test_empty_list(self):
        assert _build_graph([]) == {}

    def test_skips_edge_with_empty_source(self):
        g = _build_graph(
            [{"source_item_id": "", "target_item_id": "B", "dependency_type": "blocks"}]
        )
        assert g == {}

    def test_skips_edge_with_empty_target(self):
        g = _build_graph(
            [{"source_item_id": "A", "target_item_id": "", "dependency_type": "blocks"}]
        )
        assert g == {}

    def test_valid_edge_added(self):
        g = _build_graph([_edge("A", "B")])
        assert "A" in g
        assert g["A"][0]["target"] == "B"

    def test_multiple_edges_from_same_source(self):
        g = _build_graph([_edge("A", "B"), _edge("A", "C")])
        assert len(g["A"]) == 2


# ===========================================================================
# _find_cycle
# ===========================================================================


class TestFindCycle:
    def test_no_cycle_linear_chain(self):
        g = _build_graph([_edge("A", "B"), _edge("B", "C")])
        assert _find_cycle("A", g) is None

    def test_no_edges_returns_none(self):
        g = _build_graph([])
        assert _find_cycle("A", g) is None

    def test_no_cycle_diamond_hits_visited_branch(self):
        # A→B, A→C, B→D, C→D  — D visited twice, no cycle
        g = _build_graph([_edge("A", "B"), _edge("A", "C"), _edge("B", "D"), _edge("C", "D")])
        assert _find_cycle("A", g) is None

    def test_direct_cycle(self):
        g = _build_graph([_edge("A", "B"), _edge("B", "A")])
        cycle = _find_cycle("A", g)
        assert cycle is not None
        assert cycle[0] == cycle[-1]  # cycle path closes on itself
        assert "A" in cycle and "B" in cycle

    def test_indirect_cycle(self):
        g = _build_graph([_edge("A", "B"), _edge("B", "C"), _edge("C", "A")])
        cycle = _find_cycle("A", g)
        assert cycle is not None
        assert len(cycle) >= 3


# ===========================================================================
# _trace_item
# ===========================================================================


class TestTraceItem:
    def test_no_dependencies(self):
        g = _build_graph([])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        assert result["direct_dependencies"] == []
        assert result["transitive_dependencies"] == []
        assert result["total_dependency_count"] == 0
        assert result["risk_flags"] == []

    def test_direct_dependency(self):
        g = _build_graph([_edge("A", "B")])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        assert len(result["direct_dependencies"]) == 1
        assert result["direct_dependencies"][0]["id"] == "B"
        assert result["direct_dependencies"][0]["depth"] == 1

    def test_transitive_dependency(self):
        g = _build_graph([_edge("A", "B"), _edge("B", "C")])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        assert len(result["direct_dependencies"]) == 1
        assert len(result["transitive_dependencies"]) == 1
        assert result["transitive_dependencies"][0]["id"] == "C"
        assert result["transitive_dependencies"][0]["depth"] == 2

    def test_max_depth_limits_traversal(self):
        # A→B→C→D: with max_depth=2, C is transitive but D is not processed
        g = _build_graph([_edge("A", "B"), _edge("B", "C"), _edge("C", "D")])
        result = _trace_item("A", g, max_depth=2, include_soft=True)
        dep_ids = {
            d["id"] for d in result["direct_dependencies"] + result["transitive_dependencies"]
        }
        assert "B" in dep_ids
        assert "C" in dep_ids
        assert "D" not in dep_ids

    def test_soft_deps_excluded_when_include_soft_false(self):
        g = _build_graph([_edge("A", "B", "blocks"), _edge("A", "C", "soft")])
        result = _trace_item("A", g, max_depth=5, include_soft=False)
        ids = {d["id"] for d in result["direct_dependencies"]}
        assert "B" in ids
        assert "C" not in ids

    def test_soft_deps_included_when_include_soft_true(self):
        g = _build_graph([_edge("A", "B", "blocks"), _edge("A", "C", "soft")])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        ids = {d["id"] for d in result["direct_dependencies"]}
        assert "B" in ids and "C" in ids

    def test_external_dep_null_eta_risk_flag(self):
        g = _build_graph([_edge("A", "EXT-1", "external", "Team X", None)])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        flags = [f["type"] for f in result["risk_flags"]]
        assert "external_no_eta" in flags

    def test_external_dep_tbd_eta_risk_flag(self):
        g = _build_graph([_edge("A", "EXT-1", "external", "Team X", "TBD")])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        flags = [f["type"] for f in result["risk_flags"]]
        assert "external_no_eta" in flags

    def test_external_dep_concrete_eta_flag(self):
        g = _build_graph([_edge("A", "EXT-1", "external", "Team X", "2026-09-01")])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        flags = [f["type"] for f in result["risk_flags"]]
        assert "external_dependency" in flags
        assert "external_no_eta" not in flags

    def test_long_chain_flag(self):
        # A→B→C→D: chain_len = 3 → long_chain flag
        g = _build_graph([_edge("A", "B"), _edge("B", "C"), _edge("C", "D")])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        assert any(f["type"] == "long_chain" for f in result["risk_flags"])

    def test_short_chain_no_long_chain_flag(self):
        g = _build_graph([_edge("A", "B")])  # chain_len=1
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        assert not any(f["type"] == "long_chain" for f in result["risk_flags"])

    def test_visited_prevents_re_enqueue(self):
        # Diamond A→B, A→C, B→C — C already visited when processing B's edges
        g = _build_graph([_edge("A", "B"), _edge("A", "C"), _edge("B", "C")])
        result = _trace_item("A", g, max_depth=5, include_soft=True)
        # C appears in both direct and transitive (counted twice)
        # chain_len = 3 → long_chain
        assert any(f["type"] == "long_chain" for f in result["risk_flags"])

    def test_include_external_false_filters_external_deps(self):
        g = _build_graph(
            [_edge("A", "B", "blocks"), _edge("A", "EXT-1", "external", "Team X", None)]
        )
        result = _trace_item("A", g, max_depth=5, include_soft=True, include_external=False)
        direct_ids = {d["id"] for d in result["direct_dependencies"]}
        assert "B" in direct_ids
        assert "EXT-1" not in direct_ids

    def test_include_external_true_keeps_external_deps(self):
        g = _build_graph([_edge("A", "EXT-1", "external", "Team X", None)])
        result = _trace_item("A", g, max_depth=5, include_soft=True, include_external=True)
        direct_ids = {d["id"] for d in result["direct_dependencies"]}
        assert "EXT-1" in direct_ids


# ===========================================================================
# _critical_path
# ===========================================================================


class TestCriticalPath:
    def test_empty_item_ids(self):
        g = _build_graph([_edge("A", "B")])
        assert _critical_path([], g) == []

    def test_single_item_no_blocks_edges(self):
        g = _build_graph([_edge("A", "B", "soft")])
        # No blocks edges, but item itself starts the path → [A]
        path = _critical_path(["A"], g)
        assert path == ["A"]

    def test_blocks_chain(self):
        g = _build_graph([_edge("A", "B"), _edge("B", "C")])
        path = _critical_path(["A"], g)
        assert path == ["A", "B", "C"]

    def test_longest_chain_wins(self):
        g = _build_graph([_edge("A", "B"), _edge("B", "C"), _edge("X", "Y")])
        # A→B→C is length 3; X→Y is length 2
        path = _critical_path(["A", "X"], g)
        assert path == ["A", "B", "C"]

    def test_soft_edges_ignored_in_critical_path(self):
        # A→B (soft), A→C (blocks) → critical path should follow blocks
        g = _build_graph([_edge("A", "B", "soft"), _edge("A", "C", "blocks")])
        path = _critical_path(["A"], g)
        assert "B" not in path
        assert "C" in path


# ===========================================================================
# map_dependencies_impl
# ===========================================================================


class TestMapDependenciesImpl:
    def test_empty_item_ids_returns_error(self):
        r = map_dependencies_impl([], [])
        assert "error" in r
        assert r["items"] == []

    def test_max_depth_less_than_one_returns_error(self):
        r = map_dependencies_impl([], ["A"], max_depth=0)
        assert "error" in r

    def test_normal_case(self):
        deps = [_edge("BP-001", "BP-002")]
        r = map_dependencies_impl(deps, ["BP-001"])
        assert not r["has_cycles"]
        assert r["summary"]["items_analyzed"] == 1
        assert r["summary"]["total_unique_deps"] == 1

    def test_cycle_detected_and_reported(self):
        deps = [_edge("A", "B"), _edge("B", "A")]
        r = map_dependencies_impl(deps, ["A"])
        assert r["has_cycles"]
        assert len(r["cycles"]) >= 1
        assert "cycle" in r["cycles"][0]
        assert "message" in r["cycles"][0]

    def test_same_cycle_not_duplicated_across_items(self):
        # Both A and B are in the cycle A→B→A; querying both should not produce
        # duplicate cycle entries
        deps = [_edge("A", "B"), _edge("B", "A")]
        r = map_dependencies_impl(deps, ["A", "B"])
        assert len(r["cycles"]) == 1

    def test_critical_path_in_output(self):
        deps = [_edge("A", "B"), _edge("B", "C")]
        r = map_dependencies_impl(deps, ["A"])
        assert r["critical_path"] == ["A", "B", "C"]
        assert r["critical_path_length"] == 3

    def test_external_risks_counted_in_summary(self):
        deps = [_edge("A", "EXT-1", "external", "Team X", None)]
        r = map_dependencies_impl(deps, ["A"])
        assert r["summary"]["external_risks"] >= 1

    def test_long_chains_counted_in_summary(self):
        deps = [_edge("A", "B"), _edge("B", "C"), _edge("C", "D")]
        r = map_dependencies_impl(deps, ["A"])
        assert r["summary"]["long_chains"] == 1

    def test_include_soft_false_filters_soft_deps(self):
        deps = [_edge("A", "B", "blocks"), _edge("A", "C", "soft")]
        r = map_dependencies_impl(deps, ["A"], include_soft=False)
        item = r["items"][0]
        direct_ids = {d["id"] for d in item["direct_dependencies"]}
        assert "B" in direct_ids
        assert "C" not in direct_ids

    def test_no_deps_item_has_empty_results(self):
        r = map_dependencies_impl([], ["ISOLATED"])
        item = r["items"][0]
        assert item["direct_dependencies"] == []
        assert item["transitive_dependencies"] == []
        assert item["total_dependency_count"] == 0
