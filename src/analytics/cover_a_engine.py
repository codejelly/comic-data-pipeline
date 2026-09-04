# src/analytics/cover_a_engine.py
from __future__ import annotations

from typing import Any

from src.config import ACCELERATION_CONFIG, MAJOR_PUBLISHERS, PULL_THRESHOLDS
from src.parse.helpers import is_primary_base_issue_one


def evaluate_cover_a_issue(
    issue: dict[str, Any],
    snapshots: list[dict[str, Any]],
    has_issue_one_in_db: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Evaluates primary Cover A Issue #1 books using 3-day delta and 4-snapshot acceleration.
    """
    locg_id = issue.get("locg_issue_id")
    cfg = {**PULL_THRESHOLDS, **ACCELERATION_CONFIG, **(config or {})}

    # 1. Gatekeeper: Must be a true primary Cover A Issue #1 (data_parent == 0 AND #1 title check)
    if not is_primary_base_issue_one(issue):
        return {
            "locg_issue_id": locg_id,
            "evaluation_mode": "SKIPPED_NOT_COVER_A_ISSUE_ONE",
            "velocity_state": "INVALID_TIER",
            "is_early_breakout": False,
            "peak_spike_grade": "UNFLAGGED",
            "reason": "Does not qualify as a Primary Cover A Issue #1.",
        }

    # 2. Snapshot History Guardrail: Requires minimum 3 daily snapshots for 3D delta tracking
    if not snapshots or len(snapshots) < 3:
        return {
            "locg_issue_id": locg_id,
            "evaluation_mode": "COVER_A_ISSUE_ONE",
            "velocity_state": "INSUFFICIENT_DATA",
            "is_early_breakout": issue.get("is_early_breakout", False),
            "peak_spike_grade": issue.get("peak_spike_grade", "UNFLAGGED"),
            "reason": f"Insufficient snapshot history ({len(snapshots)}/3 points required)",
        }

    # Sort snapshots chronologically
    snapshots_sorted = sorted(snapshots, key=lambda x: x["recorded_at"])

    # Extract current and 3-day prior pull counts
    current_pulls = snapshots_sorted[-1]["pull_count"]
    pulls_3d_ago = snapshots_sorted[-3]["pull_count"]
    delta_3d = current_pulls - pulls_3d_ago

    # Determine publisher threshold (+25 for Majors, +10 for Small-Press)
    publisher = str(issue.get("publisher", "")).strip().lower()
    raw_threshold = cfg["MAJOR"] if publisher in MAJOR_PUBLISHERS else cfg["DEFAULT"]

    # 3. Calculate 3-Day Acceleration (Requires minimum 4 snapshots)
    acceleration = 0
    if len(snapshots_sorted) >= 4:
        prior_delta_3d = (
            snapshots_sorted[-2]["pull_count"] - snapshots_sorted[-4]["pull_count"]
        )
        acceleration = delta_3d - prior_delta_3d

    # Spike & Acceleration Evaluation
    is_raw_spike = delta_3d >= raw_threshold
    is_accelerating_spike = (delta_3d >= cfg["MIN_DELTA_3D"]) and (
        acceleration >= cfg["MIN_ACCELERATION"]
    )

    has_breakout = (
        is_raw_spike or is_accelerating_spike or issue.get("is_early_breakout", False)
    )
    current_grade = (
        "CLASS_A_BREAKOUT"
        if (is_raw_spike or is_accelerating_spike)
        else issue.get("peak_spike_grade", "UNFLAGGED")
    )

    return {
        "locg_issue_id": locg_id,
        "evaluation_mode": "EARLY_ISSUE_ONE_ACCELERATION",
        "current_pull_count": current_pulls,
        "delta_3d": delta_3d,
        "acceleration_3d": acceleration,
        "day_0_baseline": None,
        "manual_additions": current_pulls,
        "is_early_breakout": has_breakout,
        "peak_spike_grade": current_grade,
        "velocity_state": "HOT_ACCELERATING" if has_breakout else "STABLE",
    }
