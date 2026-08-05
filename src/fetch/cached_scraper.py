import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from src.paths import CACHE_DIR

CACHE_DIR.mkdir(parents=True, exist_ok=True)

def fetch_and_cache_week(
    driver: webdriver.Chrome, 
    release_date: str, 
    base_url: str, 
    force_refresh: bool = True,
    timeout: int = 15
) -> str:
    """
    Fetches raw HTML for a specific comic release date using Selenium.
    
    - If force_refresh is False and a cached file exists, reads from disk.
    - If force_refresh is True (e.g. nightly cron) or no cache exists, fetches live DOM 
      via Selenium and overwrites the local HTML cache file.
    """
    cache_file = CACHE_DIR / f"week_{release_date}.html"
    
    # 1. Respect local cache if force_refresh is False
    if cache_file.exists() and not force_refresh:
        logging.info(f"[{release_date}] Reading raw HTML from local cache ({cache_file.name}).")
        return cache_file.read_text(encoding="utf-8")

    # 2. Construct the date-specific URL
    target_url = f"{base_url}?release_date={release_date}"
    logging.info(f"[{release_date}] Fetching live DOM via Selenium (force_refresh={force_refresh})...")
    
    try:
        driver.get(target_url)
        
        # Wait until target comic listing element is present in the rendered DOM
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".comic-list-item")))
        
        raw_html = driver.page_source
        
        # Save or overwrite raw HTML snapshot on disk
        cache_file.write_text(raw_html, encoding="utf-8")
        logging.info(f"[{release_date}] Successfully cached HTML snapshot to disk.")
        
        return raw_html

    except TimeoutException:
        logging.error(f"[{release_date}] Timed out waiting for .comic-list-item at {target_url}")
        raise
    except WebDriverException as e:
        logging.error(f"[{release_date}] Selenium error while loading {target_url}: {e}")
        raise
    except Exception as e:
        logging.error(f"[{release_date}] Unexpected error during fetch: {e}")
        raise