from src.paths import LOGS_DIR
from src.fetch.html_fetcher import fetch_comic_html_driver
from src.parse.comic_parser import parse_comic_harvester_loop
from src.persistence.json_writer import save_json_log


def execute_pipeline(foc_week: str = "2026/08/05"):
    """Harvest the LOCG new-comics list for a FOC week (YYYY/MM/DD)."""
    url = f"https://leagueofcomicgeeks.com/comics/new-comics/{foc_week}"

    print(f"🚀 Launching browser to fetch: {url}")

    try:
        raw_html = fetch_comic_html_driver(url)
        comic_data = parse_comic_harvester_loop(raw_html)

        log_filename = LOGS_DIR / f"harvest_{foc_week.replace('/', '-')}.json"
        save_json_log(comic_data, log_filename)

        print(f"✅ Success! Processed and saved {len(comic_data)} records.")
        return comic_data

    except Exception as e:
        print(f"❌ Harvester pipeline crashed: {e}")


if __name__ == "__main__":
    execute_pipeline()
