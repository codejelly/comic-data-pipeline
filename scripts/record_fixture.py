from pathlib import Path
from typing import Union

from seleniumbase import Driver


def record_sample_html_data(url: str, output_path: Union[str, Path]):
    """
    Fetches rendered HTML using SeleniumBase UC mode and writes it to a UTF-8 fixture.
    """
    driver = Driver(uc=True, headless=True)

    try:
        driver.get(url)
        driver.sleep(3)

        file_path = Path(output_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        print(f"✅ Successfully recorded HTML snapshot to: {file_path}")

    finally:
        driver.quit()


if __name__ == "__main__":
    TARGET_URL = "https://leagueofcomicgeeks.com/comics/new-comics/2026/07/29"
    FIXTURE_DESTINATION = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "sample_issue_list.html"
    )
    print(FIXTURE_DESTINATION)

    record_sample_html_data(TARGET_URL, FIXTURE_DESTINATION)
