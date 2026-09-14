import logging
from typing import List


def run_ingestion_pipeline(
    foc_weeks: List[str], base_url: str, force_refresh: bool = False
) -> None:
    """
    Universal ingestion runner. Processes any list of FOC week keys,
    whether it contains 1 week or 100 weeks.
    """
    if not foc_weeks:
        logging.warning("No FOC weeks provided to ingestion pipeline.")
        return

    logging.info(f"Starting ingestion pipeline for {len(foc_weeks)} FOC week(s)...")

    driver = setup_headless_driver()

    try:
        for foc_week in foc_weeks:
            try:
                # 1. Fetch DOM (respects force_refresh & local caching)
                raw_html = fetch_and_cache_week(
                    driver=driver,
                    foc_week=foc_week,
                    base_url=base_url,
                    force_refresh=force_refresh,
                )

                # 2. Parse raw HTML (per-book foc_date comes from list-item DOM)
                parsed_books = parse_html_data(raw_html, foc_week)

                # 3. Upsert to DB
                upsert_books_to_db(parsed_books)

                logging.info(f" Successfully processed FOC week: {foc_week}")

            except Exception as e:
                logging.error(f" Failed processing FOC week {foc_week}: {e}")
                # Continue with remaining weeks in batch if one fails
                continue

    finally:
        logging.info("Tearing down Selenium driver session.")
        driver.quit()
