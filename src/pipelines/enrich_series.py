"""Weekly Cover A series-id enrichment via LOCG issue pages."""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from src.db.crud import fetch_cover_a_missing_series, update_master_series_id
from src.fetch.html_fetcher import fetch_issue_page_html, open_uc_driver
from src.parse.series_parser import build_issue_page_url, parse_series_id_from_issue_html

logger = logging.getLogger(__name__)


def enrich_series_id_for_cover_a(
    db_session: Session,
    *,
    locg_issue_id: int,
    master_issue_id: int,
    issue_path: str | None = None,
    driver: Any | None = None,
) -> int | None:
    """
    Open one Cover A issue page, parse /comics/series/{id}/, update master.

    Returns the series_id when found, else None.
    """
    url = build_issue_page_url(locg_issue_id, issue_path)
    html = fetch_issue_page_html(url, driver=driver)
    series_id = parse_series_id_from_issue_html(html)
    if series_id is None:
        logger.warning(
            "No series link on issue page locg_issue_id=%s url=%s",
            locg_issue_id,
            url,
        )
        return None

    update_master_series_id(db_session, master_issue_id, series_id)
    return series_id


def run_series_enrichment(
    db_session: Session,
    *,
    limit: int | None = None,
    pause_seconds: float = 1.0,
    issue_paths: dict[int, str] | None = None,
) -> dict[str, int]:
    """
    Enrich all Cover A masters still missing series_id.

    Uses one shared UC browser session. Variants already share master_issue_id,
    so they inherit series_id automatically — no separate variant loop.
    """
    pending = fetch_cover_a_missing_series(db_session, limit=limit)
    stats = {"attempted": 0, "updated": 0, "missed": 0}
    if not pending:
        logger.info("No Cover A rows missing series_id.")
        return stats

    paths = issue_paths or {}
    driver = open_uc_driver()
    try:
        for row in pending:
            locg_id = int(row["locg_issue_id"])
            master_id = int(row["master_issue_id"])
            stats["attempted"] += 1
            try:
                series_id = enrich_series_id_for_cover_a(
                    db_session,
                    locg_issue_id=locg_id,
                    master_issue_id=master_id,
                    issue_path=paths.get(locg_id),
                    driver=driver,
                )
                if series_id is None:
                    stats["missed"] += 1
                else:
                    stats["updated"] += 1
                    logger.info(
                        "series_id=%s for locg_issue_id=%s master_issue_id=%s",
                        series_id,
                        locg_id,
                        master_id,
                    )
            except Exception:
                stats["missed"] += 1
                logger.exception(
                    "Series enrichment failed for locg_issue_id=%s", locg_id
                )
            if pause_seconds > 0:
                time.sleep(pause_seconds)
        db_session.commit()
    finally:
        driver.quit()

    logger.info(
        "Series enrichment done attempted=%s updated=%s missed=%s",
        stats["attempted"],
        stats["updated"],
        stats["missed"],
    )
    return stats
