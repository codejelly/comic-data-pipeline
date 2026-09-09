# src/pipelines/router.py

from typing import Any

from src.analytics.cover_a_engine import evaluate_cover_a_issue
from src.db.crud import (
    append_issue_snapshot,
    fetch_snapshots_by_date,
    upsert_master_issue,
    upsert_velocity_flags,
)

# Future engine imports:
# from src.analytics.variant_engine import evaluate_variant_issue
# from src.analytics.ratio_engine import evaluate_ratio_issue


def process_harvested_record(db_session, record: dict[str, Any]) -> None:
    """
    1. Upserts master/variant rows into `issue_master` + `issue_variants`.
    2. Appends current snapshot into `issue_snapshots`.
    3. Routes to specialized analytics engine based on categorized tier.
    4. Upserts evaluation metrics into `issue_velocity_flags`.
    """
    locg_id = record["locg_issue_id"]

    # -------------------------------------------------------------------------
    # STEP 1 & 2: PERSIST MASTER METADATA & APPEND TIME-SERIES SNAPSHOT
    # -------------------------------------------------------------------------
    upsert_master_issue(db_session, record)
    append_issue_snapshot(db_session, record)

    # Fetch timed snapshot window for 72h velocity (not fragile index offsets)
    snapshots = fetch_snapshots_by_date(db_session, locg_id, lookback_days=5)

    evaluation = None

    # -------------------------------------------------------------------------
    # STEP 3: CATEGORY-BASED ENGINE ROUTING
    # -------------------------------------------------------------------------

    # BRANCH A: Primary Cover A Issue #1 Debut Engine
    if record.get("is_primary_base_issue_one"):
        evaluation = evaluate_cover_a_issue(
            issue=record, same_book_snapshots=snapshots
        )

    # BRANCH B: Incentive Ratio Variants (e.g., "1:25", "1:50")
    elif record.get("ratio"):
        # evaluation = evaluate_ratio_issue(issue=record, snapshots=snapshots)
        pass

    # BRANCH C: Open-Order Variants (Cover B, C, D, etc. where parent_id != 0)
    elif record.get("parent_id", 0) != 0:
        # evaluation = evaluate_variant_issue(issue=record, snapshots=snapshots)
        pass

    # BRANCH D: Mid-Series Standard Cover A (Issue #4+)
    else:
        # evaluation = evaluate_mid_series_issue(issue=record, snapshots=snapshots)
        pass

    # -------------------------------------------------------------------------
    # STEP 4: UPSERT ANALYTICS FLAGS (If evaluated)
    # -------------------------------------------------------------------------
    if evaluation:
        upsert_velocity_flags(db_session, evaluation)
