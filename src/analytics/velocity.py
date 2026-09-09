from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple, Union

from src.db.models import IssueSnapshot

SnapshotLike = Union[IssueSnapshot, dict[str, Any]]


class VelocityResult(NamedTuple):
    latest_pulls: int
    baseline_pulls: int
    normalized_3d_delta: float
    elapsed_hours: float
    baseline_recorded_at: datetime
    latest_recorded_at: datetime


def _snapshot_recorded_at(snapshot: SnapshotLike) -> datetime:
    raw = (
        snapshot.recorded_at
        if isinstance(snapshot, IssueSnapshot)
        else snapshot["recorded_at"]
    )
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        raise TypeError(f"Unsupported recorded_at type: {type(raw)!r}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _snapshot_pull_count(snapshot: SnapshotLike) -> int:
    if isinstance(snapshot, IssueSnapshot):
        return int(snapshot.pull_count)
    return int(snapshot["pull_count"])


def _snapshot_locg_id(snapshot: SnapshotLike) -> Any:
    if isinstance(snapshot, IssueSnapshot):
        return snapshot.locg_issue_id
    return snapshot.get("locg_issue_id")


def compute_timestamp_3d_delta(
    snapshots: Sequence[SnapshotLike],
    target_hours: float = 72.0,
    tolerance_hours: float = 18.0,
) -> VelocityResult:
    """
    Calculates velocity by finding the historical snapshot closest to target_hours ago.

    Raises ValueError with diagnostic date bounds if the required snapshot is missing.
    Index order alone is not trusted — timing drives the baseline selection.
    """
    if len(snapshots) < 2:
        raise ValueError("Insufficient snapshot history to calculate delta.")

    ordered = sorted(snapshots, key=_snapshot_recorded_at)
    latest = ordered[-1]
    latest_at = _snapshot_recorded_at(latest)
    target_time = latest_at - timedelta(hours=target_hours)

    best_snapshot = None
    min_time_diff = float("inf")
    max_tolerance = tolerance_hours * 3600.0

    for snapshot in ordered[:-1]:
        recorded_at = _snapshot_recorded_at(snapshot)
        diff = abs((recorded_at - target_time).total_seconds())
        if diff < min_time_diff:
            min_time_diff = diff
            best_snapshot = snapshot

    if best_snapshot is None or min_time_diff > max_tolerance:
        missing_start = (target_time - timedelta(hours=tolerance_hours)).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        missing_end = (target_time + timedelta(hours=tolerance_hours)).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        locg_id = _snapshot_locg_id(latest)
        raise ValueError(
            f"[GAP_DETECTED] locg_id={locg_id} missing 3-day baseline snapshot! "
            f"Latest record: {latest_at.strftime('%Y-%m-%d %H:%M UTC')}. "
            f"Missing window: between {missing_start} and {missing_end}."
        )

    baseline_at = _snapshot_recorded_at(best_snapshot)
    elapsed_seconds = (latest_at - baseline_at).total_seconds()
    if elapsed_seconds <= 0:
        raise ValueError(
            f"[GAP_DETECTED] locg_id={_snapshot_locg_id(latest)} "
            "baseline is not strictly older than latest snapshot."
        )

    elapsed_days = elapsed_seconds / 86400.0
    raw_delta = _snapshot_pull_count(latest) - _snapshot_pull_count(best_snapshot)

    # Normalize rate to a strict 72-hour period
    normalized_delta = round((raw_delta / elapsed_days) * (target_hours / 24.0), 2)

    return VelocityResult(
        latest_pulls=_snapshot_pull_count(latest),
        baseline_pulls=_snapshot_pull_count(best_snapshot),
        normalized_3d_delta=normalized_delta,
        elapsed_hours=round(elapsed_seconds / 3600.0, 2),
        baseline_recorded_at=baseline_at,
        latest_recorded_at=latest_at,
    )


def compute_timestamp_acceleration(
    snapshots: Sequence[SnapshotLike],
    target_hours: float = 72.0,
    tolerance_hours: float = 18.0,
    lag_hours: float = 24.0,
) -> float:
    """
    Acceleration = current 3d normalized delta - prior 3d normalized delta.

    Prior window is anchored ~lag_hours before the latest snapshot tip.
    Returns 0.0 when a prior baseline cannot be resolved.
    """
    ordered = sorted(snapshots, key=_snapshot_recorded_at)
    if len(ordered) < 3:
        return 0.0

    current = compute_timestamp_3d_delta(
        ordered, target_hours=target_hours, tolerance_hours=tolerance_hours
    )

    lag_cutoff = current.latest_recorded_at - timedelta(hours=lag_hours)
    prior_pool = [s for s in ordered if _snapshot_recorded_at(s) <= lag_cutoff]
    if len(prior_pool) < 2:
        return 0.0

    try:
        prior = compute_timestamp_3d_delta(
            prior_pool, target_hours=target_hours, tolerance_hours=tolerance_hours
        )
    except ValueError:
        return 0.0

    return round(current.normalized_3d_delta - prior.normalized_3d_delta, 2)
