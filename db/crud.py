# Compatibility shim — prefer importing from src.db.crud
from src.db.crud import (  # noqa: F401
    append_issue_snapshot,
    fetch_recent_snapshots,
    upsert_master_issue,
    upsert_velocity_flags,
)
