# src/analytics/cover_a_engine.py
from __future__ import annotations

from typing import Any

from src.analytics.velocity import (
    compute_timestamp_3d_delta,
    compute_timestamp_acceleration,
)
from src.config import ACCELERATION_CONFIG, MAJOR_PUBLISHERS, PULL_THRESHOLDS
from src.parse.helpers import is_primary_base_issue_one


def determine_demand_tier(
    is_accelerating: bool,
    is_raw_spike: bool,
    days_to_street_date: int | None,
    current_tier: str = "UNFLAGGED",
) -> tuple[str, str]:
    """Assigns demand tier and velocity state based on mathematical triggers
    and the solicitation timeline to avoid cold-start labeling bias.

    Issue number alone must not imply "early acceleration" — a debut issue
    discovered near FOC is a late-cycle rush, not early momentum.
    """
    if not (is_accelerating or is_raw_spike):
        return current_tier, "STABLE"

    # Multi-window acceleration confirmed (independent of solicitation phase)
    if is_accelerating:
        return "CONFIRMED_BREAKOUT", "HOT_ACCELERATING"

    # Raw velocity: label by days-to-street / FOC proximity
    if days_to_street_date is not None:
        if days_to_street_date > 28:
            return "EARLY_MOMENTUM", "WATCH_EARLY_VOLUME"
        if days_to_street_date >= 14:
            return "MID_CYCLE_SURGE", "WATCH_MID_VOLUME"
        return "LATE_FOC_RUSH", "WATCH_LATE_VOLUME"

    # Fallback if days_to_street_date is null/unpopulated
    return "VELOCITY_SPIKE", "WATCH_ACTIVE_VOLUME"


def evaluate_cover_a_issue(
    issue: dict[str, Any],
    same_book_snapshots: list[dict[str, Any]],
    series_prior_issue_pulls: list[int] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluates Cover A base releases (parent_id == 0).

    - Issues #1-#3: debut-window math (pure timestamp velocity / acceleration).
    - Issues #4+: mid-series math (subscriber floor + manual additions).
    - Solicitation phase (early / mid / late FOC) comes from days_to_street_date,
      not from issue number — so cold starts near FOC are not called early accel.
    """
    locg_id = issue.get("locg_issue_id")
    parent_id = (
        issue.get("parent_id")
        if issue.get("parent_id") is not None
        else issue.get("data_parent", 0)
    )

    # 1. Gatekeeper: Target issue must be a primary Cover A master release
    if parent_id != 0:
        return {
            "locg_issue_id": locg_id,
            "evaluation_mode": "SKIPPED_NOT_COVER_A",
            "velocity_state": "INVALID_TIER",
            "is_early_breakout": False,
            "demand_tier": "UNFLAGGED",
            "reason": "Filtered: Issue is a variant or ratio incentive.",
        }

    # 2. History Guardrail: Minimum 2 timed points for timestamp-based 72h window matching
    if not same_book_snapshots or len(same_book_snapshots) < 2:
        return {
            "locg_issue_id": locg_id,
            "evaluation_mode": "COVER_A_EVALUATION",
            "velocity_state": "INSUFFICIENT_DATA",
            "is_early_breakout": issue.get("is_early_breakout", False),
            "demand_tier": issue.get("demand_tier", "UNFLAGGED"),
            "reason": (
                f"Insufficient snapshot history ({len(same_book_snapshots) if same_book_snapshots else 0}/2 "
                "points required for timestamp delta)"
            ),
        }

    # 3. Timestamp-Anchored Velocity & Acceleration
    try:
        velocity = compute_timestamp_3d_delta(same_book_snapshots)
        delta_3d = velocity.normalized_3d_delta
        current_pulls = velocity.latest_pulls
        acceleration = compute_timestamp_acceleration(same_book_snapshots)
    except ValueError as err:
        return {
            "locg_issue_id": locg_id,
            "evaluation_mode": "COVER_A_EVALUATION",
            "velocity_state": "INSUFFICIENT_DATA",
            "is_early_breakout": issue.get("is_early_breakout", False),
            "demand_tier": issue.get("demand_tier", "UNFLAGGED"),
            "reason": str(err),
        }

    cfg = {**PULL_THRESHOLDS, **ACCELERATION_CONFIG, **(config or {})}

    # 4. Series-position math window (#1-#3 vs #4+)
    # NOT "early in solicitation" — only debut vs mid-series scoring rules.
    is_issue_one = is_primary_base_issue_one(issue)
    sort_order = float(issue.get("sort_order", 1.0))
    is_debut_window = is_issue_one or (sort_order < 4.0)

    # 5. Subscriber floor for ongoing mid-series books
    subscriber_floor = 0
    if not is_debut_window and series_prior_issue_pulls:
        valid_priors = [p for p in series_prior_issue_pulls if p >= 50]
        if len(valid_priors) >= 2:
            subscriber_floor = min(valid_priors[:3])

    manual_additions = (
        max(0, current_pulls - subscriber_floor)
        if subscriber_floor > 0
        else current_pulls
    )

    publisher = str(issue.get("publisher", "")).strip().lower()
    raw_threshold = cfg["MAJOR"] if publisher in MAJOR_PUBLISHERS else cfg["DEFAULT"]

    # 6. Mathematical spike / acceleration triggers
    if is_debut_window:
        is_raw_spike = delta_3d >= raw_threshold
        is_accelerating_spike = (delta_3d >= cfg["MIN_DELTA_3D"]) and (
            acceleration >= cfg["MIN_ACCELERATION"]
        )
    else:
        is_raw_spike = (delta_3d >= raw_threshold) and (
            manual_additions >= raw_threshold
        )
        is_accelerating_spike = (
            (delta_3d >= cfg["MIN_DELTA_3D"])
            and (acceleration >= cfg["MIN_ACCELERATION"])
            and (manual_additions >= cfg["MIN_DELTA_3D"])
        )

    # 7. FOC / solicitation-phase labeling
    days_to_street = issue.get("days_to_street_date")
    persisted_tier = issue.get("demand_tier", "UNFLAGGED")
    demand_tier, velocity_state = determine_demand_tier(
        is_accelerating=is_accelerating_spike,
        is_raw_spike=is_raw_spike,
        days_to_street_date=days_to_street,
        current_tier=persisted_tier,
    )

    return {
        "locg_issue_id": locg_id,
        "evaluation_mode": (
            "DEBUT_ISSUE_VELOCITY" if is_debut_window else "MID_SERIES_EVALUATION"
        ),
        "current_pull_count": current_pulls,
        "subscriber_floor": subscriber_floor,
        "manual_additions": manual_additions,
        "delta_3d": delta_3d,
        "acceleration_3d": acceleration,
        "elapsed_hours": velocity.elapsed_hours,
        "baseline_pull_count": velocity.baseline_pulls,
        # Only true for early-in-solicitation momentum (>28 days out)
        "is_early_breakout": demand_tier == "EARLY_MOMENTUM",
        "demand_tier": demand_tier,
        "velocity_state": velocity_state,
        "days_to_street_date": days_to_street,
    }
