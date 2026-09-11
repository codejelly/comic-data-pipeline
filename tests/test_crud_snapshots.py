from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.db.crud import (
    append_issue_snapshot,
    fetch_recent_snapshots,
    upsert_master_issue,
    upsert_velocity_flags,
)
from src.db.models import IssueMaster, IssueSnapshot, IssueVariant, IssueVelocityFlags
from src.parse.helpers import parse_issue_number, parse_sort_order


def test_parse_sort_order_extracts_issue_number_from_title():
    assert parse_sort_order({"main_title": "Spawn #1"}) == Decimal(1)
    assert parse_sort_order({"main_title": "Avengers: Armageddon #2"}) == Decimal(2)
    assert parse_sort_order({"issue_number": "X-Men #12.1"}) == Decimal("12.1")
    # Unnumbered specials must not look like debut #1 or real #0 books
    assert parse_sort_order({"main_title": "Spawn HC Vol. 1"}) == Decimal(9000)
    assert parse_sort_order(
        {"main_title": "Spawn HC Vol. 1", "locg_issue_id": 3773849}
    ) == Decimal(9000 + (3773849 % 900))
    assert parse_sort_order({"sort_order": 3.5, "main_title": "Spawn #1"}) == Decimal(
        "3.5"
    )
    assert parse_issue_number({"main_title": "Spawn #1"}) == "#1"
    assert parse_issue_number({"main_title": "Spawn HC Vol. 1"}) == "Special / Unnumbered"


def test_upsert_master_issue_and_snapshots(db_session):
    record = {
        "locg_issue_id": 5001,
        "parent_id": 0,
        "main_title": "Spawn #1",
        "publisher": "Image Comics",
        "assigned_tier": "COVER_A",
        "retail_price": 3.99,
        "is_primary_base_issue_one": True,
        "current_pull_count": 1200,
        "days_to_street_date": 5,
        "release_date": "2026-09-02",
        "series_id": 42,
        "sort_order": 1.0,
    }

    # 1. Upsert master + variant
    variant = upsert_master_issue(db_session, record)
    db_variant = (
        db_session.query(IssueVariant).filter_by(locg_issue_id=5001).one()
    )
    db_master = (
        db_session.query(IssueMaster)
        .filter_by(master_issue_id=db_variant.master_issue_id)
        .one()
    )

    assert variant.locg_issue_id == 5001
    assert db_variant.variant_type == "COVER_A"
    assert db_variant.current_pull_count == 1200
    assert db_master.issue_number == "#1"
    assert db_master.publisher == "Image Comics"

    # 2. Append Snapshot
    append_issue_snapshot(db_session, record)
    snapshots = db_session.query(IssueSnapshot).filter_by(locg_issue_id=5001).all()
    assert len(snapshots) == 1
    assert snapshots[0].pull_count == 1200
    assert snapshots[0].days_to_street_date == 5


def test_fetch_recent_snapshots_chronological_order(db_session):
    locg_id = 9999
    base_time = datetime.now(timezone.utc)

    # Seed master + variant first (FK required by schema)
    upsert_master_issue(
        db_session,
        {
            "locg_issue_id": locg_id,
            "parent_id": 0,
            "main_title": "Test Comic #1",
            "publisher": "Image Comics",
            "assigned_tier": "COVER_A",
            "current_pull_count": 100,
            "days_to_street_date": 10,
            "release_date": "2026-09-10",
            "series_id": 99,
            "sort_order": 1.0,
        },
    )

    # Seed 5 days of snapshot history
    for day in range(5):
        db_session.add(
            IssueSnapshot(
                locg_issue_id=locg_id,
                pull_count=100 + (day * 20),
                days_to_street_date=10 - day,
                recorded_at=base_time - timedelta(days=5 - day),
            )
        )
    db_session.flush()

    # Query helper
    recent = fetch_recent_snapshots(db_session, locg_issue_id=locg_id, limit=3)

    # Must return limit=3, sorted oldest -> newest
    assert len(recent) == 3
    assert recent[0]["pull_count"] < recent[-1]["pull_count"]
    assert recent[-1]["pull_count"] == 180  # Most recent snapshot


def test_upsert_velocity_flags(db_session):
    upsert_master_issue(
        db_session,
        {
            "locg_issue_id": 7001,
            "parent_id": 0,
            "main_title": "Breakout #1",
            "publisher": "Marvel Comics",
            "assigned_tier": "COVER_A",
            "current_pull_count": 1500,
            "days_to_street_date": 3,
            "release_date": "2026-09-15",
            "series_id": 7,
            "sort_order": 1.0,
        },
    )

    evaluation = {
        "locg_issue_id": 7001,
        "evaluation_mode": "DEBUT_ISSUE_VELOCITY",
        "current_pull_count": 1500,
        "delta_3d": 40,
        "acceleration_3d": 12,
        "manual_additions": 1500,
        "is_early_breakout": True,
        "demand_tier": "EARLY_MOMENTUM",
        "velocity_state": "WATCH_EARLY_VOLUME",
    }
    flags = upsert_velocity_flags(db_session, evaluation)
    stored = db_session.query(IssueVelocityFlags).filter_by(locg_issue_id=7001).one()

    assert flags.velocity_state == "WATCH_EARLY_VOLUME"
    assert stored.is_early_breakout is True
    assert stored.demand_tier == "EARLY_MOMENTUM"
    assert stored.delta_3d == 40
    assert stored.net_growth_since_discovery == 1500
