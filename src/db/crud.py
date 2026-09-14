from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import IssueMaster, IssueSnapshot, IssueVariant, IssueVelocityFlags
from src.parse.helpers import parse_issue_number, parse_sort_order


def _parse_foc_date(record: dict[str, Any]) -> date:
    """Require Final Order Cutoff date from the harvest record."""
    raw = record.get("foc_date")
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str) and raw:
        return date.fromisoformat(raw[:10])
    raise ValueError("record requires foc_date (YYYY-MM-DD)")


def determine_foc_status(foc_date: date, *, as_of: date | None = None) -> str:
    """FOC lifecycle from Final Order Cutoff date vs today (UTC).

    PRE_FOC       — before FOC (orders still open)
    FOC_DATE      — today is the FOC day
    POST_FOC_DATE — after FOC
    """
    today = as_of or datetime.now(timezone.utc).date()
    if today < foc_date:
        return "PRE_FOC"
    if today == foc_date:
        return "FOC_DATE"
    return "POST_FOC_DATE"


def _coerce_series_id(record: dict[str, Any]) -> int | None:
    """Real LOCG series id when known; None until weekly enrichment."""
    raw = record.get("series_id")
    if raw is None or raw == "":
        return None
    return int(raw)


def _apply_master_fields(
    master: IssueMaster,
    *,
    issue_number: str,
    foc_date: date,
    publisher: str,
    record: dict[str, Any],
    series_id: int | None,
) -> None:
    master.issue_number = issue_number
    master.publisher = publisher
    master.foc_date = foc_date
    master.status = determine_foc_status(foc_date)
    if series_id is not None:
        master.series_id = series_id
    if record.get("type"):
        master.type = str(record["type"])


def _resolve_master(db_session: Session, record: dict[str, Any]) -> IssueMaster:
    """Find or create the master trunk row for a harvested cover record."""
    locg_id = int(record["locg_issue_id"])
    parent_id = int(record.get("parent_id") or record.get("data_parent") or 0)
    foc_date = _parse_foc_date(record)
    publisher = str(record.get("publisher") or "Unknown").strip()
    sort_order = parse_sort_order(record)
    issue_number = parse_issue_number(record)
    series_id = _coerce_series_id(record)

    # Variants attach to Cover A's master when the parent row already exists.
    if parent_id != 0:
        parent_variant = (
            db_session.query(IssueVariant)
            .filter_by(locg_issue_id=parent_id)
            .one_or_none()
        )
        if parent_variant is not None:
            master = parent_variant.master
            _apply_master_fields(
                master,
                issue_number=issue_number,
                foc_date=foc_date,
                publisher=publisher,
                record=record,
                series_id=series_id,
            )
            db_session.flush()
            return master

    # Re-harvest of an existing cover: keep its master (series_id may still be NULL).
    existing_variant = (
        db_session.query(IssueVariant).filter_by(locg_issue_id=locg_id).one_or_none()
    )
    if existing_variant is not None:
        master = existing_variant.master
        _apply_master_fields(
            master,
            issue_number=issue_number,
            foc_date=foc_date,
            publisher=publisher,
            record=record,
            series_id=series_id,
        )
        db_session.flush()
        return master

    # Only match on (series_id, sort_order) once a real series id is known.
    # Do not use locg_issue_id as a fake series_id — that blocks true series grouping.
    master = None
    if series_id is not None:
        master = (
            db_session.query(IssueMaster)
            .filter_by(series_id=series_id, sort_order=sort_order)
            .one_or_none()
        )

    if master is None:
        master = IssueMaster(
            series_id=series_id,
            issue_number=issue_number,
            sort_order=sort_order,
            type=str(record.get("type") or "MAIN_RELEASE"),
            status=determine_foc_status(foc_date),
            foc_date=foc_date,
            publisher=publisher,
        )
        db_session.add(master)
        db_session.flush()
        return master

    _apply_master_fields(
        master,
        issue_number=issue_number,
        foc_date=foc_date,
        publisher=publisher,
        record=record,
        series_id=series_id,
    )
    db_session.flush()
    return master


def upsert_master_issue(db_session: Session, record: dict[str, Any]) -> IssueVariant:
    """
    Upserts issue_master + issue_variants for a harvested cover record.
    Variants are keyed by locg_issue_id; masters by (series_id, sort_order)
    once series_id is enriched (NULL until then).
    """
    locg_id = int(record["locg_issue_id"])
    master = _resolve_master(db_session, record)

    days_to_foc = int(record.get("days_to_foc") or 0)
    pull_count = int(record.get("current_pull_count") or 0)
    variant_type = str(
        record.get("assigned_tier") or record.get("variant_type") or "UNKNOWN"
    )
    retail_price = record.get("retail_price")
    retail_price_dec = Decimal(str(retail_price)) if retail_price is not None else None

    variant = (
        db_session.query(IssueVariant).filter_by(locg_issue_id=locg_id).one_or_none()
    )
    if variant is None:
        variant = IssueVariant(
            master_issue_id=master.master_issue_id,
            locg_issue_id=locg_id,
            variant_type=variant_type,
            cover_info=record.get("cover_info"),
            retail_price=retail_price_dec,
            image_url=record.get("image_url"),
            current_pull_count=pull_count,
            days_to_foc=days_to_foc,
        )
        db_session.add(variant)
    else:
        variant.master_issue_id = master.master_issue_id
        variant.variant_type = variant_type
        variant.cover_info = record.get("cover_info")
        variant.retail_price = retail_price_dec
        variant.image_url = record.get("image_url")
        variant.current_pull_count = pull_count
        variant.days_to_foc = days_to_foc

    db_session.flush()
    return variant


def append_issue_snapshot(db_session: Session, record: dict[str, Any]) -> IssueSnapshot:
    """Append a time-series pull-count row for an existing variant."""
    locg_id = int(record["locg_issue_id"])
    variant = (
        db_session.query(IssueVariant).filter_by(locg_issue_id=locg_id).one_or_none()
    )
    if variant is None:
        raise ValueError(
            f"Cannot append snapshot: no issue_variants row for locg_issue_id={locg_id}"
        )

    recorded_at = record.get("recorded_at") or datetime.now(timezone.utc)
    if isinstance(recorded_at, str):
        recorded_at = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))

    days_to_foc = int(
        record.get("days_to_foc")
        if record.get("days_to_foc") is not None
        else variant.days_to_foc
    )
    pull_count = int(
        record.get("current_pull_count")
        if record.get("current_pull_count") is not None
        else record.get("pull_count", 0)
    )

    snapshot = IssueSnapshot(
        locg_issue_id=locg_id,
        pull_count=pull_count,
        days_to_foc=days_to_foc,
        recorded_at=recorded_at,
    )
    db_session.add(snapshot)

    variant.current_pull_count = pull_count
    variant.days_to_foc = days_to_foc
    db_session.flush()
    return snapshot


def fetch_recent_snapshots(
    db_session: Session,
    locg_issue_id: int,
    limit: int = 7,
) -> list[dict[str, Any]]:
    """
    Fetches the most recent daily snapshots for a given issue,
    sorted chronologically (oldest to newest) for velocity math.
    """
    records = (
        db_session.query(IssueSnapshot)
        .filter(IssueSnapshot.locg_issue_id == locg_issue_id)
        .order_by(IssueSnapshot.recorded_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "recorded_at": row.recorded_at.isoformat(),
            "pull_count": row.pull_count,
            "days_to_foc": row.days_to_foc,
        }
        for row in reversed(records)
    ]


def fetch_snapshots_by_date(
    db_session: Session,
    locg_issue_id: int,
    lookback_days: int = 5,
) -> list[dict[str, Any]]:
    """
    Fetches snapshots within an explicit time window in ascending chronological order.
    Prefer this over index/limit slicing when computing time-based velocity.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    records = (
        db_session.query(IssueSnapshot)
        .filter(
            IssueSnapshot.locg_issue_id == locg_issue_id,
            IssueSnapshot.recorded_at >= cutoff,
        )
        .order_by(IssueSnapshot.recorded_at.asc())
        .all()
    )

    return [
        {
            "locg_issue_id": row.locg_issue_id,
            "recorded_at": row.recorded_at.isoformat(),
            "pull_count": row.pull_count,
            "days_to_foc": row.days_to_foc,
        }
        for row in records
    ]


def upsert_velocity_flags(
    db_session: Session, evaluation: dict[str, Any]
) -> IssueVelocityFlags:
    """Upsert derived analytics flags keyed by locg_issue_id."""
    locg_id = int(evaluation["locg_issue_id"])
    variant = (
        db_session.query(IssueVariant).filter_by(locg_issue_id=locg_id).one_or_none()
    )
    if variant is None:
        raise ValueError(
            f"Cannot upsert velocity flags: no issue_variants row for locg_issue_id={locg_id}"
        )

    flags = (
        db_session.query(IssueVelocityFlags)
        .filter_by(locg_issue_id=locg_id)
        .one_or_none()
    )
    net_growth = int(
        evaluation.get("net_growth_since_discovery")
        if evaluation.get("net_growth_since_discovery") is not None
        else evaluation.get("manual_additions", 0) or 0
    )

    values = {
        "evaluation_mode": str(evaluation.get("evaluation_mode") or "UNKNOWN"),
        "current_pull_count": int(evaluation.get("current_pull_count") or 0),
        "net_growth_since_discovery": net_growth,
        "delta_3d": int(evaluation.get("delta_3d") or 0),
        "acceleration_3d": int(evaluation.get("acceleration_3d") or 0),
        "is_early_breakout": bool(evaluation.get("is_early_breakout", False)),
        "demand_tier": str(evaluation.get("demand_tier") or "UNFLAGGED"),
        "velocity_state": str(evaluation.get("velocity_state") or "STABLE"),
        "last_evaluated_at": datetime.now(timezone.utc),
    }

    if flags is None:
        flags = IssueVelocityFlags(locg_issue_id=locg_id, **values)
        db_session.add(flags)
    else:
        for key, value in values.items():
            setattr(flags, key, value)

    db_session.flush()
    return flags
