from src.paths import LOGS_DIR
from src.fetch.html_fetcher import fetch_comic_html_driver
from src.parse.comic_parser import parse_comic_harvester_loop
from src.persistence.json_writer import save_json_log


def execute_pipeline(target_date: str = "2026/08/05"):
    url = f"https://leagueofcomicgeeks.com/comics/new-comics/{target_date}"

    print(f"🚀 Launching browser to fetch: {url}")

    try:
        raw_html = fetch_comic_html_driver(url)
        comic_data = parse_comic_harvester_loop(raw_html)

        log_filename = LOGS_DIR / f"harvest_{target_date.replace('/', '-')}.json"
        save_json_log(comic_data, log_filename)

        print(f"✅ Success! Processed and saved {len(comic_data)} records.")
        return comic_data

    except Exception as e:
        print(f"❌ Harvester pipeline crashed: {e}")


if __name__ == "__main__":
    execute_pipeline()
