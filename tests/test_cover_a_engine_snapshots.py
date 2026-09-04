import pytest

from src.analytics.cover_a_engine import evaluate_cover_a_issue


@pytest.fixture
def base_issue():
    return {
        "locg_issue_id": 5001,
        "main_title": "Awesome Comic #1",
        "publisher": "Marvel Comics",
        "data_parent": 0,
        "is_primary_base_issue_one": True,
    }


def test_insufficient_snapshots_returns_insufficient_data(base_issue):
    # Only 2 snapshots provided (< 3 required)
    snapshots = [
        {"recorded_at": "2026-08-01", "pull_count": 100},
        {"recorded_at": "2026-08-02", "pull_count": 105},
    ]

    result = evaluate_cover_a_issue(issue=base_issue, snapshots=snapshots)

    assert result["velocity_state"] == "INSUFFICIENT_DATA"
    assert "Insufficient snapshot history" in result["reason"]


def test_three_snapshots_calculates_delta_without_acceleration(base_issue):
    # Exactly 3 snapshots (Calculates 3D delta, acceleration defaults to 0)
    snapshots = [
        {"recorded_at": "2026-08-01", "pull_count": 100},
        {"recorded_at": "2026-08-02", "pull_count": 110},
        {"recorded_at": "2026-08-03", "pull_count": 130},  # +30 delta vs day 1
    ]

    result = evaluate_cover_a_issue(issue=base_issue, snapshots=snapshots)

    assert result["delta_3d"] == 30
    assert result["acceleration_3d"] == 0
    assert result["is_early_breakout"] is True  # Meets Marvel +25 threshold


def test_four_snapshots_calculates_acceleration(base_issue):
    # 4 snapshots allowing acceleration tracking:
    # Day 1 -> Day 3 delta = 120 - 100 = +20
    # Day 2 -> Day 4 delta = 150 - 105 = +45
    # Acceleration = 45 - 20 = +25
    snapshots = [
        {"recorded_at": "2026-08-01", "pull_count": 100},
        {"recorded_at": "2026-08-02", "pull_count": 105},
        {"recorded_at": "2026-08-03", "pull_count": 120},
        {"recorded_at": "2026-08-04", "pull_count": 150},
    ]

    result = evaluate_cover_a_issue(issue=base_issue, snapshots=snapshots)

    assert result["delta_3d"] == 45
    assert result["acceleration_3d"] == 25
