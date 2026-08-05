import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from src.parse.classifier import dynamic_issue_classifier

def parse_comic_harvester_loop(html_content: str):
    """
    Scrapes a list of comic issue cards with strict structural validation,
    extracting core master details and itemized variant parameters mapped out 
    for relational database distribution.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    parsed_records = []

    # 🛑 GUARD CLAUSE: Verify the parent blocks exist before running iterations
    list_block = soup.find('div', id='comic-list-block')
    list_ul = soup.find('ul', id='comic-list-issues')

    if not list_block or not list_ul:
        raise ValueError(
            "CRITICAL: Structural container 'comic-list-block' or 'comic-list-issues' "
            "was not found in the HTML payload. Page may not have loaded completely."
        )

    # 🟢 PROCEED: Safe to loop now that we know the DOM structure is present
    for issue_li in list_ul.find_all('li', class_='issue'):
        
        # -------------------------------------------------------------------------
        # 1. PRIMARY PLATFORM RELATIONSHIP KEYS & VELOCITY METRICS
        # -------------------------------------------------------------------------
        locg_issue_id = int(issue_li.get('data-comic', 0))
        parent_id = int(issue_li.get('data-parent', 0))
        current_pull_count = int(issue_li.get('data-pulls', 0))

        # -------------------------------------------------------------------------
        # 2. VISUALS & METRICS: COVERS, PRICES & CALENDAR METRICS
        # -------------------------------------------------------------------------
        cover_div = issue_li.find('div', class_='cover')
        image_url = None
        if cover_div:
            img_tag = cover_div.find('img')
            if img_tag:
                # 1. Check lazy-load data attributes first
                # 2. Fallback to standard 'src' if data attributes aren't present
                raw_src = (
                    img_tag.get('data-src') or 
                    img_tag.get('data-original') or 
                    img_tag.get('data-lazy-src') or 
                    img_tag.get('src')
                )

                # Verify it's not the base64 transparent pixel placeholder
                if raw_src and not raw_src.startswith('data:image'):
                    image_url = raw_src.strip()
                else:
                    # If it's still base64, check if there's a parent anchor or noscript fallback
                    image_url = None

        details_div = issue_li.find('div', class_='details')
        retail_price = None

        if details_div:
            retail_price = None
            price_span = issue_li.find("span", class_="price")
            
            if price_span:
                # Extract raw text ("$4.99" or " ·  $4.99")
                raw_price = price_span.get_text()
                
                # Match digits and optional decimals
                match = re.search(r"\d+(?:\.\d+)?", raw_price)
                if match:
                    retail_price = float(match.group())
        else:
            retail_price = None

    # -------------------------------------------------------------
    # 2. DATE & VELOCITY EXTRACTION
    # -------------------------------------------------------------

        # Pre-initialize defaults outside the if block
        release_date = None
        days_to_street_date = None

        if details_div:
            # 1. Price extraction ...
            
            # 2. Date & Velocity extraction
            date_span = details_div.find('span', class_='date')
            
            if date_span:
                # Path A: Extract from data-date epoch attribute (Primary)
                raw_epoch_attr = date_span.get('data-date')
                
                if raw_epoch_attr:
                    try:
                        raw_epoch = int(raw_epoch_attr)
                        street_datetime = datetime.fromtimestamp(raw_epoch, tz=timezone.utc)
                        street_date_obj = street_datetime.date()

                        # Set ISO Date String ("2026-07-29")
                        release_date = street_date_obj.isoformat()

                        today_utc_date = datetime.now(timezone.utc).date()
                        days_to_street_date = (street_date_obj - today_utc_date).days
                    except (ValueError, TypeError):
                        release_date = None
                        days_to_street_date = None

                # Path B: Fallback to inner text if data-date attribute is missing (e.g. "Jul 29th, 2026")
                if not release_date:
                    raw_text_date = date_span.text.strip()
                    if raw_text_date:
                        release_date = raw_text_date
        # -------------------------------------------------------------------------
        # 3. THE TITLE BRANCH: MAIN SERIES NAME & VERBOSE COVER DECOUPLE
        # -------------------------------------------------------------------------
        title_div = issue_li.find('div', class_=lambda x: x and 'title' in x.split())
        main_title = ""
        cover_info = None

        if title_div:
            title_anchor = title_div.find('a')
            if title_anchor:
                variant_span = title_anchor.find('span', class_='variant-name')
                
                if variant_span:
                    # VARIANT COVER: Extract variant label and remove it from title
                    cover_info = variant_span.get_text(strip=True)
                    
                    # Extract only direct text nodes inside anchor
                    title_parts = [
                        str(node).strip() 
                        for node in title_anchor.contents 
                        if isinstance(node, str) and node.strip()
                    ]
                    main_title = " ".join(title_parts)
                else:
                    # MAIN COVER
                    cover_info = None
                    main_title = title_anchor.get_text(strip=True)
            else:
                # Fallback only if <a> tag was absent
                main_title = title_div.get('data-sorting') or title_div.get_text(strip=True)

        # Final safety net to guarantee main_title is never empty
        main_title = main_title.strip() if main_title else "Unknown Title"

        # -------------------------------------------------------------------------
        # 4. THE PUBLISHER BRANCH: DYNAMIC CORE IP EXTRACTION
        # -------------------------------------------------------------------------
        publisher_div = issue_li.find('div', class_='publisher')
        publisher = "Unknown"
        if publisher_div:
            publisher = publisher_div.text.strip()

        # -------------------------------------------------------------------------
        # 5. RUN CLASSIFICATION RULE ENGINE
        # -------------------------------------------------------------------------
        is_annual = "annual" in main_title.lower()

        ratio_match = None
        hidden_letter = None

        if not cover_info:
            # Main Issue
            variant_label = "Cover A"
            hidden_letter = "A"
        else:
            variant_label = cover_info
            
            # 1. Check for Incentive Ratio (e.g., "1:25", "1:50", "1:100", 1 in 25 or 1-in-50.)
            ratio_search = re.search(r'\b1(?::|-in-|\s+in\s+)(\d+)\b', cover_info, re.IGNORECASE)
            if ratio_search:
                ratio_match = f"1:{ratio_search.group(1)}"
                
            # 2. Extract Cover Letter across full alphabet A-Z (e.g., "Cover E" -> "E")
            letter_search = re.search(r'\bCover\s+([A-Z])\b', cover_info, re.IGNORECASE)
            if letter_search:
                hidden_letter = letter_search.group(1).upper()

        issue_metadata = {
            "format": "annual" if is_annual else "comic",
            "is_annual": is_annual,
            "variant_type": variant_label,
            "cover_info": cover_info,
            "ratio": ratio_match,             # e.g., "1:25"
            "cover_letter": hidden_letter,    # e.g., "E" or "A"
            "hidden_letter": hidden_letter,
            "is_main_cover": cover_info is None
        }

        assigned_tier = dynamic_issue_classifier(issue_metadata, main_title)

        # -------------------------------------------------------------------------
        # 6. CONSOLIDATE PAYLOAD FOR DB PIPELINE ROUTER
        # -------------------------------------------------------------------------
        parsed_records.append({
            "locg_issue_id": locg_issue_id,
            "parent_id": parent_id,
            "main_title": main_title,
            "publisher": publisher,           
            "assigned_tier": assigned_tier,
            "cover_info": cover_info,         
            "retail_price": retail_price,
            "image_url": image_url,           
            "current_pull_count": current_pull_count,
            "days_to_street_date": days_to_street_date,
            "release_date": release_date
        })

    return parsed_records