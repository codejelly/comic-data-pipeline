from __future__ import annotations

import time
from typing import Any

from seleniumbase import Driver


def fetch_comic_html_driver(target_url: str) -> str:
    """
    Launches an undetected, headless Chrome instance, expands all variant blocks,
    forces lazy-loaded images to assign real sources, and captures the DOM.
    """
    driver = Driver(uc=True, headless=True)
    try:
        driver.get(target_url)

        # 1. Wait for the main list structure to be present
        driver.wait_for_element("#comic-list-block", timeout=10)

        print("🤖 Expanding all comic variant panels...")

        # 2. Click every variant expander
        driver.execute_script("""
            document.querySelectorAll('a.variant-toggle').forEach(button => {
                if (!button.classList.contains('selected')) {
                    button.click();
                }
            });
        """)

        # Give variant DOM nodes 1 second to append
        time.sleep(1)

        print("🖼️ Forcing lazy-loaded image swaps...")

        # 3. Force all lazy images to reveal their true URLs instantly
        driver.execute_script("""
            document.querySelectorAll('img').forEach(img => {
                // Copy data-src or data-original into src if present
                let realSrc = img.getAttribute('data-src') || img.getAttribute('data-original');
                if (realSrc) {
                    img.setAttribute('src', realSrc);
                }
            });
        """)

        # 4. Scroll incrementally down the page to ensure IntersectionObservers fire
        driver.execute_script("""
            let totalHeight = 0;
            let distance = 400;
            let timer = setInterval(() => {
                let scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;

                if(totalHeight >= scrollHeight){
                    clearInterval(timer);
                }
            }, 100);
        """)

        # Give the smooth scroll 2-3 seconds to finish reach the bottom
        time.sleep(3)

        # 5. Extract the full expanded DOM
        html_content = driver.page_source
        return html_content
    finally:
        driver.quit()


def open_uc_driver() -> Any:
    """Shared undetected Chrome session for multi-page enrichment."""
    return Driver(uc=True, headless=True)


def fetch_issue_page_html(target_url: str, driver: Any | None = None) -> str:
    """
    Fetch a single LOCG issue detail page for series-id enrichment.

    Pass an existing driver to reuse one browser across many Cover A visits.
    """
    owns_driver = driver is None
    active = driver or open_uc_driver()
    try:
        active.get(target_url)
        # Issue pages vary; wait for body then a brief settle for SPA/content.
        active.wait_for_element("body", timeout=15)
        time.sleep(1.5)
        return active.page_source
    finally:
        if owns_driver:
            active.quit()
