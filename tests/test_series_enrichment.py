from __future__ import annotations

from src.db.crud import (
    fetch_cover_a_missing_series,
    update_master_series_id,
    upsert_master_issue,
)
from src.db.models import IssueMaster
from src.parse.series_parser import (
    build_issue_page_url,
    parse_series_id_from_issue_html,
)


SAMPLE_ISSUE_HTML = """
<html><body>
  <a class="series-title" href="/comics/series/210130/clayface-celebrity-dirt">
    Clayface: Celebrity Dirt
  </a>
  <h1>Clayface: Celebrity Dirt #3</h1>
</body></html>
"""


def test_parse_series_id_from_issue_html():
    assert parse_series_id_from_issue_html(SAMPLE_ISSUE_HTML) == 210130
    assert parse_series_id_from_issue_html("<html><body>No series</body></html>") is None


def test_build_issue_page_url():
    assert build_issue_page_url(7056380) == (
        "https://leagueofcomicgeeks.com/comic/7056380"
    )
    assert build_issue_page_url(
        7056380, "/comic/7056380/clayface-celebrity-dirt-3"
    ) == "https://leagueofcomicgeeks.com/comic/7056380/clayface-celebrity-dirt-3"


def test_fetch_cover_a_missing_series_and_update(db_session):
    cover_a = upsert_master_issue(
        db_session,
        {
            "locg_issue_id": 7056380,
            "parent_id": 0,
            "main_title": "Clayface: Celebrity Dirt #3",
            "publisher": "DC Comics",
            "assigned_tier": "COVER_A",
            "current_pull_count": 6174,
            "days_to_foc": 0,
            "foc_date": "2026-09-09",
        },
    )
    # Variant attached to same master via parent_id
    upsert_master_issue(
        db_session,
        {
            "locg_issue_id": 7056381,
            "parent_id": 7056380,
            "main_title": "Clayface: Celebrity Dirt #3",
            "publisher": "DC Comics",
            "assigned_tier": "STANDARD_VARIANT_B",
            "current_pull_count": 200,
            "days_to_foc": 0,
            "foc_date": "2026-09-09",
        },
    )

    pending = fetch_cover_a_missing_series(db_session)
    assert any(row["locg_issue_id"] == 7056380 for row in pending)
    assert all(row["locg_issue_id"] != 7056381 for row in pending)

    update_master_series_id(db_session, cover_a.master_issue_id, 210130)
    master = (
        db_session.query(IssueMaster)
        .filter_by(master_issue_id=cover_a.master_issue_id)
        .one()
    )
    assert master.series_id == 210130
    assert fetch_cover_a_missing_series(db_session) == []
