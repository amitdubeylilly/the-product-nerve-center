"""
map_dependencies — Trace dependency chains, detect cycles, and surface risks.

Dependency types (from oracle-discovered schema):
    blocks    hard blocker: target must be done before source can start
    soft      beneficial but not strictly blocking
    external  depends on a team outside the squads; may have an ETA

Graph loaded from dependency_map.json (fallback: sample_dependencies.json).
Each record: {source_item_id, target_item_id, dependency_type,
               external_team, external_eta}
Oracle schema variant: {item_id, target_id, type, external_team, external_eta}
Both schemas are normalized transparently.

Risk flags:
    external_no_eta     external dep with null or "TBD" ETA
    external_dependency external dep with a concrete ETA (informational)
    long_chain          total dependency count ≥ 3 for one item

Cycle detection uses iterative DFS with a path set.
Critical path is the longest blocks-chain across the requested item set.
"""

from collections import defaultdict, deque
from typing import Optional


def _normalize_edge(raw: dict) -> dict:
    """Normalize from oracle schema (item_id/target_id/type) or sample schema."""
    return {
        "source": raw.get("source_item_id") or raw.get("item_id", ""),
        "target": raw.get("target_item_id") or raw.get("target_id", ""),
        "type": raw.get("dependency_type") or raw.get("type", "blocks"),
        "external_team": raw.get("external_team"),
        "external_eta": raw.get("external_eta"),
    }


def _build_graph(dep_list: list) -> dict[str, list[dict]]:
    graph: dict[str, list[dict]] = defaultdict(list)
    for raw in dep_list:
        edge = _normalize_edge(raw)
        if edge["source"] and edge["target"]:
            graph[edge["source"]].append(edge)
    return graph


def _find_cycle(start: str, graph: dict) -> Optional[list[str]]:
    """Return cycle path if one exists reachable from start, else None."""
    visited: set[str] = set()
    path: list[str] = []
    path_set: set[str] = set()

    def dfs(node: str) -> Optional[list[str]]:
        if node in path_set:
            idx = path.index(node)
            return path[idx:] + [node]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        path_set.add(node)
        for edge in graph.get(node, []):
            result = dfs(edge["target"])
            if result:
                return result
        path.pop()
        path_set.discard(node)
        return None

    return dfs(start)


def _trace_item(
    item_id: str,
    graph: dict,
    max_depth: int,
    include_soft: bool,
) -> dict:
    """BFS from item_id, collecting direct and transitive dependencies."""
    direct: list[dict] = []
    transitive: list[dict] = []
    risk_flags: list[dict] = []
    visited: set[str] = {item_id}
    # queue entries: (node, depth)
    queue: deque[tuple[str, int]] = deque([(item_id, 0)])

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in graph.get(node, []):
            dep_type = edge["type"]
            if not include_soft and dep_type == "soft":
                continue
            target = edge["target"]
            entry = {
                "id": target,
                "type": dep_type,
                "via": node,
                "depth": depth + 1,
                "external_team": edge.get("external_team"),
                "external_eta": edge.get("external_eta"),
            }
            if depth == 0:
                direct.append(entry)
            else:
                transitive.append(entry)

            # Risk assessment
            if dep_type == "external":
                eta = edge.get("external_eta")
                if not eta or eta == "TBD":
                    risk_flags.append(
                        {
                            "type": "external_no_eta",
                            "item": target,
                            "via": node,
                            "team": edge.get("external_team", "unknown"),
                            "message": (
                                f"{target} is an external dependency with no confirmed ETA "
                                f"(team: {edge.get('external_team', 'unknown')})."
                            ),
                        }
                    )
                else:
                    risk_flags.append(
                        {
                            "type": "external_dependency",
                            "item": target,
                            "via": node,
                            "team": edge.get("external_team", "unknown"),
                            "eta": eta,
                            "message": (
                                f"{target} is an external dependency "
                                f"(team: {edge.get('external_team', 'unknown')}, ETA: {eta})."
                            ),
                        }
                    )

            if target not in visited:
                visited.add(target)
                queue.append((target, depth + 1))

    chain_len = len(direct) + len(transitive)
    if chain_len >= 3:
        risk_flags.append(
            {
                "type": "long_chain",
                "chain_length": chain_len,
                "message": (
                    f"{item_id} has a dependency chain of {chain_len} items, "
                    "increasing delivery risk."
                ),
            }
        )

    return {
        "item_id": item_id,
        "direct_dependencies": direct,
        "transitive_dependencies": transitive,
        "total_dependency_count": chain_len,
        "risk_flags": risk_flags,
    }


def _critical_path(item_ids: list[str], graph: dict) -> list[str]:
    """Longest chain of 'blocks' edges starting from any item in item_ids."""
    best: list[str] = []

    def dfs(node: str, path: list[str], in_path: set[str]) -> None:
        nonlocal best
        if len(path) > len(best):
            best = list(path)
        for edge in graph.get(node, []):
            if edge["type"] != "blocks":
                continue
            t = edge["target"]
            if t not in in_path:
                dfs(t, path + [t], in_path | {t})

    for iid in item_ids:
        dfs(iid, [iid], {iid})

    return best


def map_dependencies_impl(
    dep_list: list,
    item_ids: list,
    max_depth: int = 5,
    include_soft: bool = True,
) -> dict:
    """Trace dependency chains and surface risks for a set of backlog items.

    Args:
        dep_list:     Loaded dependency_map.json (or sample_dependencies.json) list.
        item_ids:     Backlog item IDs to analyse (e.g. ["BP-109", "BP-112"]).
        max_depth:    Maximum traversal depth for transitive dependencies (default 5).
        include_soft: If True (default), include soft dependencies in the trace.
                      Set False to only trace hard blockers.

    Returns:
        dict with keys:
            items            – per-item trace (direct, transitive, risk_flags)
            cycles           – any circular dependency paths detected
            critical_path    – longest blocking chain across the requested items
            has_cycles       – boolean shortcut
            summary          – aggregate counts
    """
    if not item_ids:
        return {
            "error": "item_ids must be a non-empty list.",
            "items": [],
            "cycles": [],
            "critical_path": [],
            "has_cycles": False,
            "summary": {},
        }

    if max_depth < 1:
        return {
            "error": "max_depth must be ≥ 1.",
            "items": [],
            "cycles": [],
            "critical_path": [],
            "has_cycles": False,
            "summary": {},
        }

    graph = _build_graph(dep_list)
    items_out: list[dict] = []
    all_cycles: list[dict] = []
    seen_cycle_keys: set[tuple] = set()

    for iid in item_ids:
        trace = _trace_item(iid, graph, max_depth, include_soft)
        items_out.append(trace)

        cycle = _find_cycle(iid, graph)
        if cycle:
            ck = tuple(sorted(set(cycle)))
            if ck not in seen_cycle_keys:
                seen_cycle_keys.add(ck)
                all_cycles.append(
                    {
                        "cycle": cycle,
                        "message": f"Circular dependency: {' → '.join(cycle)}",
                    }
                )

    critical = _critical_path(item_ids, graph)

    return {
        "items": items_out,
        "cycles": all_cycles,
        "critical_path": critical,
        "critical_path_length": len(critical),
        "has_cycles": len(all_cycles) > 0,
        "summary": {
            "items_analyzed": len(item_ids),
            "total_unique_deps": sum(t["total_dependency_count"] for t in items_out),
            "external_risks": sum(
                len([f for f in t["risk_flags"] if "external" in f["type"]]) for t in items_out
            ),
            "long_chains": sum(
                1 for t in items_out if any(f["type"] == "long_chain" for f in t["risk_flags"])
            ),
        },
    }
