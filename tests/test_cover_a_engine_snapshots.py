from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.analytics.cover_a_engine import (
    determine_demand_tier,
    evaluate_cover_a_issue,
)
from src.analytics.velocity import compute_timestamp_3d_delta


def _ts(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


@pytest.fixture
def base_issue():
    return {
        "locg_issue_id": 5001,
        "main_title": "Awesome Comic #1",
        "publisher": "Marvel Comics",
        "data_parent": 0,
        "is_primary_base_issue_one": True,
        "days_to_street_date": 35,
    }


def test_insufficient_snapshots_returns_insufficient_data(base_issue):
    same_book_snapshots = [
        {"recorded_at": _ts(1), "pull_count": 100, "locg_issue_id": 5001},
    ]

    result = evaluate_cover_a_issue(
        issue=base_issue, same_book_snapshots=same_book_snapshots
    )

    assert result["velocity_state"] == "INSUFFICIENT_DATA"
    assert "Insufficient snapshot history" in result["reason"]


def test_gap_detected_when_no_snapshot_near_72h(base_issue):
    same_book_snapshots = [
        {"recorded_at": _ts(1), "pull_count": 100, "locg_issue_id": 5001},
        {"recorded_at": _ts(0), "pull_count": 140, "locg_issue_id": 5001},
    ]

    result = evaluate_cover_a_issue(
        issue=base_issue, same_book_snapshots=same_book_snapshots
    )

    assert result["velocity_state"] == "INSUFFICIENT_DATA"
    assert "[GAP_DETECTED]" in result["reason"]


def test_timestamp_delta_early_solicitation_labels_early_momentum(base_issue):
    same_book_snapshots = [
        {"recorded_at": _ts(3), "pull_count": 100, "locg_issue_id": 5001},
        {"recorded_at": _ts(2), "pull_count": 110, "locg_issue_id": 5001},
        {"recorded_at": _ts(0), "pull_count": 130, "locg_issue_id": 5001},
    ]

    result = evaluate_cover_a_issue(
        issue=base_issue, same_book_snapshots=same_book_snapshots
    )

    assert result["delta_3d"] == 30
    assert result["evaluation_mode"] == "DEBUT_ISSUE_VELOCITY"
    assert result["demand_tier"] == "EARLY_MOMENTUM"
    assert result["is_early_breakout"] is True
    assert result["velocity_state"] == "WATCH_EARLY_VOLUME"


def test_debut_issue_near_foc_is_not_labeled_early_acceleration(base_issue):
    # Cold start on an Issue #1 that is already close to FOC / street
    base_issue["days_to_street_date"] = 5
    same_book_snapshots = [
        {"recorded_at": _ts(3), "pull_count": 100, "locg_issue_id": 5001},
        {"recorded_at": _ts(0), "pull_count": 140, "locg_issue_id": 5001},
    ]

    result = evaluate_cover_a_issue(
        issue=base_issue, same_book_snapshots=same_book_snapshots
    )

    assert result["evaluation_mode"] == "DEBUT_ISSUE_VELOCITY"  # series position
    assert result["demand_tier"] == "LATE_FOC_RUSH"  # solicitation phase
    assert result["is_early_breakout"] is False
    assert result["velocity_state"] == "WATCH_LATE_VOLUME"


def test_determine_demand_tier_phases():
    assert determine_demand_tier(False, True, 40) == (
        "EARLY_MOMENTUM",
        "WATCH_EARLY_VOLUME",
    )
    assert determine_demand_tier(False, True, 20) == (
        "MID_CYCLE_SURGE",
        "WATCH_MID_VOLUME",
    )
    assert determine_demand_tier(False, True, 7) == (
        "LATE_FOC_RUSH",
        "WATCH_LATE_VOLUME",
    )
    assert determine_demand_tier(True, True, 7) == (
        "CONFIRMED_BREAKOUT",
        "HOT_ACCELERATING",
    )


def test_compute_timestamp_3d_delta_prefers_closest_to_72h():
    snapshots = [
        {"recorded_at": _ts(4), "pull_count": 50, "locg_issue_id": 9},
        {"recorded_at": _ts(3), "pull_count": 100, "locg_issue_id": 9},
        {"recorded_at": _ts(1), "pull_count": 120, "locg_issue_id": 9},
        {"recorded_at": _ts(0), "pull_count": 160, "locg_issue_id": 9},
    ]

    velocity = compute_timestamp_3d_delta(snapshots)

    assert velocity.baseline_pulls == 100
    assert velocity.latest_pulls == 160
    assert velocity.normalized_3d_delta == 60


def test_extra_mid_points_do_not_change_index_fragile_selection(base_issue):
    same_book_snapshots = [
        {"recorded_at": _ts(3), "pull_count": 100, "locg_issue_id": 5001},
        {"recorded_at": _ts(2.5), "pull_count": 9999, "locg_issue_id": 5001},
        {"recorded_at": _ts(0), "pull_count": 130, "locg_issue_id": 5001},
    ]

    result = evaluate_cover_a_issue(
        issue=base_issue, same_book_snapshots=same_book_snapshots
    )

    assert result["delta_3d"] == 30
    assert result["baseline_pull_count"] == 100


def test_mid_series_with_trailing_subscriber_floor():
    now = datetime.now(timezone.utc)

    target_issue = {
        "locg_issue_id": 99913,
        "parent_id": 0,
        "sort_order": 13.0,
        "publisher": "Marvel Comics",
        "title": "Amazing Spider-Man #13",
        "days_to_street_date": 20,
    }

    same_book_snapshots = [
        {"recorded_at": now - timedelta(days=4), "pull_count": 1280},
        {"recorded_at": now - timedelta(days=3), "pull_count": 1315},
        {"recorded_at": now - timedelta(days=1), "pull_count": 1330},
        {"recorded_at": now, "pull_count": 1350},
    ]

    series_prior_issue_pulls = [1300, 1100]

    result = evaluate_cover_a_issue(
        issue=target_issue,
        same_book_snapshots=same_book_snapshots,
        series_prior_issue_pulls=series_prior_issue_pulls,
    )

    assert result["evaluation_mode"] == "MID_SERIES_EVALUATION"
    assert result["subscriber_floor"] == 1100
    assert result["manual_additions"] == 250
    assert result["delta_3d"] == 35
    # Acceleration may confirm; otherwise mid-cycle surge from raw spike + 20 days out
    assert result["demand_tier"] in {"MID_CYCLE_SURGE", "CONFIRMED_BREAKOUT"}
    assert result["is_early_breakout"] is False
    assert result["velocity_state"] != "STABLE"


def test_mid_series_fails_on_insignificant_manual_additions():
    now = datetime.now(timezone.utc)

    target_issue = {
        "locg_issue_id": 99914,
        "parent_id": 0,
        "sort_order": 14.0,
        "publisher": "DC Comics",
        "title": "Batman #14",
        "days_to_street_date": 10,
    }

    same_book_snapshots = [
        {"recorded_at": now - timedelta(days=3), "pull_count": 2010},
        {"recorded_at": now - timedelta(days=2), "pull_count": 2020},
        {"recorded_at": now, "pull_count": 2035},
    ]

    series_prior_issue_pulls = [2040, 2025, 2030]

    result = evaluate_cover_a_issue(
        issue=target_issue,
        same_book_snapshots=same_book_snapshots,
        series_prior_issue_pulls=series_prior_issue_pulls,
    )

    assert result["subscriber_floor"] == 2025
    assert result["manual_additions"] == 10
    assert result["is_early_breakout"] is False
    assert result["velocity_state"] == "STABLE"
    assert result["demand_tier"] == "UNFLAGGED"
