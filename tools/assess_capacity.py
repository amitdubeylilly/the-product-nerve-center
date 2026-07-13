"""
assess_capacity — Calculate available sprint capacity for each engineer and squad.

Capacity formula (reverse-engineered from oracle probing):

    allocated_capacity  = SPRINT_POINTS * (allocation_percent / 100)
    effective_capacity  = allocated_capacity * ((sprint_days - pto_days) / sprint_days)
    available_capacity  = max(0, effective_capacity - carry_over_points)

Where SPRINT_POINTS = 21 (full sprint value at 100 % allocation, 10 working days).
PTO reduces capacity linearly: 1 PTO day out of 10 = 10 % reduction.
Engineers at 0 % allocation contribute 0 to squad totals.

Field name normalization:
    Oracle schema uses:   name/engineer_id, allocation_percent, pto_days,
                          carry_over_points, skills
    Sample schema uses:   name, sprint_allocation_percent, pto_days_this_sprint,
                          carry_over_items (list of {id, points}), skills
    Both are handled transparently.
"""

from typing import Any, Optional

SPRINT_POINTS = 21  # Full sprint capacity at 100 % allocation


def _to_int(value: Any, default: int) -> int:
    """Safely coerce values to int for mixed JSON field types."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float) -> float:
    """Safely coerce values to float for mixed JSON field types."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize(raw: dict) -> dict:
    """Unify field names from oracle schema and sample_roster schema."""
    name = raw.get("engineer_id") or raw.get("name", "unknown")
    squad = raw.get("squad", "")
    allocation = (
        raw.get("allocation_percent")
        if raw.get("allocation_percent") is not None
        else raw.get("sprint_allocation_percent", 100)
    )
    pto = (
        raw.get("pto_days")
        if raw.get("pto_days") is not None
        else raw.get("pto_days_this_sprint", 0)
    )
    skills = raw.get("skills", [])

    # carry_over_points may be an integer or derived from a list of items
    carry_over = raw.get("carry_over_points")
    if carry_over is None:
        carry_over = sum(item.get("points", 0) for item in raw.get("carry_over_items", []))

    return {
        "name": name,
        "squad": squad,
        "allocation_percent": _to_int(allocation, 100),
        "pto_days": _to_int(pto, 0),
        "skills": list(skills),
        "carry_over_points": _to_float(carry_over, 0.0),
    }


def assess_capacity_impl(
    roster: list,
    squad: Optional[str] = None,
    sprint_days: int = 10,
    required_skills: Optional[list] = None,
    sprint_id: Optional[str] = None,  # sprint identifier; informational
    include_carry_over: bool = True,  # if False, ignore carry_over_points
    check_skill_fit: bool = False,  # alias for required_skills check
    sprints: Optional[list] = None,  # sprint history; accepted for interface compat
) -> dict:
    """Calculate per-engineer and squad sprint capacity with warnings.

    Args:
        roster:          Loaded team_roster.json (or sample_roster.json) list.
        squad:           Optional squad filter ("platform", "growth", etc.).
                         None returns all squads.
        sprint_days:     Working days in the sprint (default 10 = 2-week sprint).
        required_skills: If provided, flag engineers who lack all these skills.

    Returns:
        dict with keys:
            engineers      – per-engineer capacity breakdown
            squad_totals   – aggregated by squad
            team_totals    – across all squads in the result set
            warnings       – overload, zero-capacity, skill-mismatch alerts
            capacity_formula – the formula string for transparency
    """
    if sprint_days <= 0:
        return {
            "error": f"sprint_days must be > 0, got {sprint_days}.",
            "engineers": [],
        }

    engineers = [_normalize(r) for r in roster]
    if squad:
        engineers = [e for e in engineers if e["squad"] == squad]

    if not engineers:
        return {
            "engineers": [],
            "squad_totals": {},
            "team_totals": {"allocated": 0, "effective": 0, "available": 0, "engineer_count": 0},
            "warnings": [
                {"type": "no_engineers", "message": f"No engineers found for squad='{squad}'."}
            ],
            "squad_filter": squad,
            "sprint_days": sprint_days,
            "capacity_formula": _formula_str(),
        }

    results = []
    squad_buckets: dict[str, dict] = {}
    global_warnings: list[dict] = []

    for eng in engineers:
        alloc = eng["allocation_percent"]
        pto = min(eng["pto_days"], sprint_days)  # cap PTO at full sprint
        carry = eng["carry_over_points"]

        allocated = round(SPRINT_POINTS * (alloc / 100), 2)
        effective = round(allocated * ((sprint_days - pto) / sprint_days), 2)
        carry_applied = carry if include_carry_over else 0.0
        available = round(max(0.0, effective - carry_applied), 2)

        eng_warnings: list[str] = []
        if alloc == 0:
            eng_warnings.append("zero_allocation")
        elif effective == 0:
            eng_warnings.append("zero_effective_due_to_pto")
        if carry_applied > effective and effective > 0:
            eng_warnings.append("overloaded: carry_over exceeds effective capacity")
        # check_skill_fit=True behaves like required_skills=[all unique skills in backlog]
        # For simplicity: if check_skill_fit but no required_skills, skip detailed check
        skill_check = required_skills or []
        if skill_check:
            missing = [s for s in skill_check if s not in eng["skills"]]
            if missing:
                eng_warnings.append(f"skill_mismatch: missing {missing}")

        sq = eng["squad"]
        if sq not in squad_buckets:
            squad_buckets[sq] = {
                "allocated": 0.0,
                "effective": 0.0,
                "available": 0.0,
                "engineers": 0,
            }
        sb = squad_buckets[sq]
        sb["engineers"] += 1
        if alloc > 0:  # 0 % engineers excluded from squad capacity totals
            sb["allocated"] += allocated
            sb["effective"] += effective
            sb["available"] += available

        results.append(
            {
                "engineer": eng["name"],
                "squad": sq,
                "allocation_percent": alloc,
                "pto_days": pto,
                "skills": eng["skills"],
                "allocated_capacity": allocated,
                "effective_capacity": effective,
                "carry_over_points": carry,
                "available_capacity": available,
                "warnings": eng_warnings,
            }
        )

    # Deterministic ordering
    results.sort(key=lambda x: (x["squad"], x["engineer"]))

    # Global warnings
    overloaded = [r["engineer"] for r in results if any("overloaded" in w for w in r["warnings"])]
    if overloaded:
        global_warnings.append(
            {
                "type": "overloaded_engineers",
                "engineers": overloaded,
                "message": (
                    f"{len(overloaded)} engineer(s) have carry-over "
                    "exceeding effective capacity."
                ),
            }
        )
    zero_eff = [
        r["engineer"]
        for r in results
        if r["effective_capacity"] == 0 and r["allocation_percent"] > 0
    ]
    if zero_eff:
        global_warnings.append(
            {
                "type": "zero_effective_capacity",
                "engineers": zero_eff,
                "message": (
                    f"{len(zero_eff)} engineer(s) have zero effective "
                    "capacity (full PTO coverage)."
                ),
            }
        )
    if required_skills or check_skill_fit:
        skill_check = required_skills or []
        mismatched = [
            r["engineer"] for r in results if any("skill_mismatch" in w for w in r["warnings"])
        ]
        if mismatched:
            global_warnings.append(
                {
                    "type": "skill_mismatch",
                    "engineers": mismatched,
                    "required_skills": skill_check,
                    "message": (
                        f"{len(mismatched)} engineer(s) are missing "
                        f"required skills: {skill_check}."
                    ),
                }
            )

    squad_totals_out = {
        sq: {
            "allocated": round(v["allocated"], 2),
            "effective": round(v["effective"], 2),
            "available": round(v["available"], 2),
            "engineer_count": v["engineers"],
        }
        for sq, v in squad_buckets.items()
    }

    team_totals = {
        "allocated": round(sum(v["allocated"] for v in squad_buckets.values()), 2),
        "effective": round(sum(v["effective"] for v in squad_buckets.values()), 2),
        "available": round(sum(v["available"] for v in squad_buckets.values()), 2),
        "engineer_count": len(results),
    }

    return {
        "engineers": results,
        "squad_totals": squad_totals_out,
        "team_totals": team_totals,
        "warnings": global_warnings,
        "squad_filter": squad,
        "sprint_days": sprint_days,
        "capacity_formula": _formula_str(),
    }


def _formula_str() -> str:
    return (
        "allocated = 21 × (allocation_percent / 100); "
        "effective = allocated × ((sprint_days − pto_days) / sprint_days); "
        "available = max(0, effective − carry_over_points)"
    )
