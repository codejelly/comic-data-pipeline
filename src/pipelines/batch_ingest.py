import logging
from typing import List, Optional

def run_ingestion_pipeline(
    release_dates: List[str], 
    base_url: str, 
    force_refresh: bool = False
) -> None:
    """
    Universal ingestion runner. Processes any list of release dates, 
    whether it contains 1 date or 100 dates.
    """
    if not release_dates:
        logging.warning("No release dates provided to ingestion pipeline.")
        return

    logging.info(f"Starting ingestion pipeline for {len(release_dates)} week(s)...")
    
    driver = setup_headless_driver()
    
    try:
        for release_date in release_dates:
            try:
                # 1. Fetch DOM (respects force_refresh & local caching)
                raw_html = fetch_and_cache_week(
                    driver=driver, 
                    release_date=release_date, 
                    base_url=base_url, 
                    force_refresh=force_refresh
                )
                
                # 2. Parse raw HTML
                parsed_books = parse_html_data(raw_html, release_date)
                
                # 3. Upsert to DB
                upsert_books_to_db(parsed_books)
                
                logging.info(f" Successfully processed release date: {release_date}")

            except Exception as e:
                logging.error(f" Failed processing week {release_date}: {e}")
                # Continue with remaining dates in batch if one fails
                continue

    finally:
        logging.info("Tearing down Selenium driver session.")
        driver.quit()