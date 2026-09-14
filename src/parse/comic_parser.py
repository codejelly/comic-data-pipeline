import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from src.parse.classifier import dynamic_issue_classifier
from src.parse.helpers import is_primary_base_issue_one


def parse_comic_harvester_loop(html_content: str) -> list[dict[str, Any]]:
    """
    Scrapes a list of comic issue cards with strict structural validation,
    extracting core master details and itemized variant parameters mapped out
    for relational database distribution.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_records: list[dict[str, Any]] = []

    # 🛑 GUARD CLAUSE: Verify the parent blocks exist before running iterations
    list_block = soup.find("div", id="comic-list-block")
    list_ul = soup.find("ul", id="comic-list-issues")

    if not list_block or not list_ul:
        raise ValueError(
            "CRITICAL: Structural container 'comic-list-block' or 'comic-list-issues' "
            "was not found in the HTML payload. Page may not have loaded completely."
        )

    # 🟢 PROCEED: Safe to loop now that we know the DOM structure is present
    for issue_li in list_ul.find_all("li", class_="issue"):
        # -------------------------------------------------------------------------
        # 1. PRIMARY PLATFORM RELATIONSHIP KEYS & VELOCITY METRICS
        # -------------------------------------------------------------------------
        locg_issue_id = int(issue_li.get("data-comic", 0))
        parent_id = int(issue_li.get("data-parent", 0))
        current_pull_count = int(issue_li.get("data-pulls", 0))

        # -------------------------------------------------------------------------
        # 2. VISUALS & METRICS: COVERS, PRICES & CALENDAR METRICS
        # -------------------------------------------------------------------------
        cover_div = issue_li.find("div", class_="cover")
        image_url = None
        if cover_div:
            img_tag = cover_div.find("img")
            if img_tag:
                raw_src = (
                    img_tag.get("data-src")
                    or img_tag.get("data-original")
                    or img_tag.get("data-lazy-src")
                    or img_tag.get("src")
                )

                if raw_src and not raw_src.startswith("data:image"):
                    image_url = raw_src.strip()
                else:
                    image_url = None

        details_div = issue_li.find("div", class_="details")
        retail_price = None

        if details_div:
            price_span = issue_li.find("span", class_="price")
            if price_span:
                raw_price = price_span.get_text()
                match = re.search(r"\d+(?:\.\d+)?", raw_price)
                if match:
                    retail_price = float(match.group())

        # -------------------------------------------------------------
        # 2. FOC DATE & DAYS-TO-FOC EXTRACTION
        # -------------------------------------------------------------
        foc_date = None
        days_to_foc = None

        if details_div:
            date_span = details_div.find("span", class_="date")

            if date_span:
                raw_epoch_attr = date_span.get("data-date")

                if raw_epoch_attr:
                    try:
                        raw_epoch = int(raw_epoch_attr)
                        foc_datetime = datetime.fromtimestamp(
                            raw_epoch, tz=timezone.utc
                        )
                        foc_date_obj = foc_datetime.date()

                        foc_date = foc_date_obj.isoformat()

                        today_utc_date = datetime.now(timezone.utc).date()
                        days_to_foc = (foc_date_obj - today_utc_date).days
                    except (ValueError, TypeError):
                        foc_date = None
                        days_to_foc = None

                if not foc_date:
                    raw_text_date = date_span.text.strip()
                    if raw_text_date:
                        foc_date = raw_text_date

        # -------------------------------------------------------------------------
        # 3. THE TITLE BRANCH: MAIN SERIES NAME & VERBOSE COVER DECOUPLE
        # -------------------------------------------------------------------------
        title_div = issue_li.find("div", class_=lambda x: x and "title" in x.split())
        main_title = ""
        cover_info = None

        if title_div:
            title_anchor = title_div.find("a")
            if title_anchor:
                variant_span = title_anchor.find("span", class_="variant-name")

                if variant_span:
                    cover_info = variant_span.get_text(strip=True)
                    title_parts = [
                        str(node).strip()
                        for node in title_anchor.contents
                        if isinstance(node, str) and node.strip()
                    ]
                    main_title = " ".join(title_parts)
                else:
                    cover_info = None
                    main_title = title_anchor.get_text(strip=True)
            else:
                main_title = title_div.get("data-sorting") or title_div.get_text(
                    strip=True
                )

        main_title = main_title.strip() if main_title else "Unknown Title"

        # -------------------------------------------------------------------------
        # 4. THE PUBLISHER BRANCH: DYNAMIC CORE IP EXTRACTION
        # -------------------------------------------------------------------------
        publisher_div = issue_li.find("div", class_="publisher")
        publisher = "Unknown"
        if publisher_div:
            publisher = publisher_div.text.strip()

        # -------------------------------------------------------------------------
        # 5. RUN CLASSIFICATION RULE ENGINE & STAMP ISSUE #1 FLAG
        # -------------------------------------------------------------------------
        is_annual = "annual" in main_title.lower()

        ratio_match = None
        hidden_letter = None

        if not cover_info:
            variant_label = "Cover A"
            hidden_letter = "A"
        else:
            variant_label = cover_info

            ratio_search = re.search(
                r"\b1(?::|-in-|\s+in\s+)(\d+)\b", cover_info, re.IGNORECASE
            )
            if ratio_search:
                ratio_match = f"1:{ratio_search.group(1)}"

            letter_search = re.search(r"\bCover\s+([A-Z])\b", cover_info, re.IGNORECASE)
            if letter_search:
                hidden_letter = letter_search.group(1).upper()

        issue_metadata = {
            "format": "annual" if is_annual else "comic",
            "is_annual": is_annual,
            "variant_type": variant_label,
            "cover_info": cover_info,
            "ratio": ratio_match,
            "cover_letter": hidden_letter,
            "hidden_letter": hidden_letter,
            "is_main_cover": cover_info is None,
        }

        assigned_tier = dynamic_issue_classifier(issue_metadata, main_title)

        # Build raw dict payload to test against Cover A Issue #1 validation helper
        record_payload = {
            "title": main_title,
            "data_parent": parent_id,
            "parent_id": parent_id,
        }

        # Stamp explicit boolean flag for downstream analytics routing
        is_primary_base_one = is_primary_base_issue_one(record_payload)

        # -------------------------------------------------------------------------
        # 6. CONSOLIDATE PAYLOAD FOR DB PIPELINE ROUTER
        # -------------------------------------------------------------------------
        parsed_records.append(
            {
                "locg_issue_id": locg_issue_id,
                "parent_id": parent_id,
                "data_parent": parent_id,
                "main_title": main_title,
                "publisher": publisher,
                "assigned_tier": assigned_tier,
                "cover_info": cover_info,
                "retail_price": retail_price,
                "image_url": image_url,
                "current_pull_count": current_pull_count,
                "days_to_foc": days_to_foc,
                "foc_date": foc_date,
                "is_primary_base_issue_one": is_primary_base_one,
            }
        )

    return parsed_records
