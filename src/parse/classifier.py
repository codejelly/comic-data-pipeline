# src/parse/classifier.py
import re


def categorize_variant_string(title_string: str) -> str:
    """
    Fallback regex pattern-matching engine. Parses crowdsourced text strings
    when hidden metadata dropdown flags are missing or unpopulated.
    """
    if not title_string:
        return "MAIN_RELEASE"

    text = title_string.lower().strip()

    # 1. RULE 1: Ratio Incentive Detection
    if (
        re.search(r"\b1\s*(:|in|-in)\s*\d+", text)
        or "ratio" in text
        or "incentive" in text
    ):
        return "RATIO_INCENTIVE"

    # 2. RULE 2: Dynamic Format Overrides (Annuals/Specials)
    if "annual" in text or "giant-size" in text or "one-shot" in text:
        return "ANNUAL_ONE_SHOT"

    # 3. RULE 3: Retailer / Store Exclusives
    if "exclusive" in text or "unknown comics" in text or "616" in text:
        return "STORE_EXCLUSIVE"

    # 4. RULE 4: Special Format Open-Orders
    if "printing" in text or "reprint" in text:
        return "LATER_PRINTING"
    if "foil" in text:
        return "FOIL_VARIANT"
    if "blank" in text or "sketch" in text:
        return "BLANK_SKETCH"

    # 5. RULE 5: Standard Alphabetical Variants (B, C, D)
    if re.search(r"\b(cover|variant)?\s*b\b|\bb\s*(cover|variant)?\b", text):
        return "STANDARD_VARIANT_B"
    if re.search(r"\b(cover|variant)?\s*c\b|\bc\s*(cover|variant)?\b", text):
        return "STANDARD_VARIANT_C"
    if re.search(r"\b(cover|variant)?\s*d\b|\bd\s*(cover|variant)?\b", text):
        return "STANDARD_VARIANT_D"

    # 6. Default Fallback if it matches main book terminology
    if text in ["cover a", "main", "regular", "regular cover", ""]:
        return "MAIN_RELEASE"

    return "UNKNOWN_OPEN_ORDER_VARIANT"


def dynamic_issue_classifier(metadata: dict, title: str) -> str:
    """
    Unified multi-factor classifier. First leverages structured metadata,
    then falls back to a two-factor text net whenever metadata is unreliable/missing.
    """
    is_annual = metadata.get("is_annual") or "annual" in title.lower()
    cover_letter = metadata.get("cover_letter") or metadata.get("hidden_letter")
    cover_info = metadata.get("cover_info") or ""
    ratio = metadata.get("ratio")
    page_format = metadata.get("format", "").lower()
    hidden_type = metadata.get("hidden_type", "").lower()

    # ─────────────────────────────────────────────────────────────────
    # FACTOR 1: CORE CHRONOLOGICAL FORMAT SEPARATION
    # ─────────────────────────────────────────────────────────────────
    if is_annual or page_format in ["annual", "one-shot", "giant-size"]:
        if not ratio and not cover_letter and not cover_info:
            return "ANNUAL_ONE_SHOT"

    # ─────────────────────────────────────────────────────────────────
    # FACTOR 2: EXPLICIT STRUCTURED METADATA (When available)
    # ─────────────────────────────────────────────────────────────────
    # 1. Ratio Incentive (e.g., 1:25, 1:50)
    if ratio:
        prefix = "ANNUAL_RATIO" if is_annual else "RATIO_INCENTIVE"
        return f"{prefix}_{ratio}"

    # 2. Main Cover / Cover A
    if metadata.get("is_main_cover") or cover_letter == "A":
        return "ANNUAL_ONE_SHOT" if is_annual else "STANDARD_MAIN_ISSUE"

    # 3. Standard Alphabetical Letters (Cover B through Z)
    if cover_letter and len(cover_letter) == 1 and "B" <= cover_letter <= "Z":
        prefix = "ANNUAL_VARIANT" if is_annual else "STANDARD_VARIANT"
        return f"{prefix}_{cover_letter}"

    # ─────────────────────────────────────────────────────────────────
    # FACTOR 3: HIDDEN BACKEND INVENTORY TYPES (LOCG internal flags)
    # ─────────────────────────────────────────────────────────────────
    if "incentive" in hidden_type or hidden_type == "incentive variant":
        return "RATIO_INCENTIVE"
    if "reprint" in hidden_type or hidden_type == "reprint":
        return "LATER_PRINTING"
    if (
        "retailer exclusive" in hidden_type
        or "store" in hidden_type
        or "exclusive" in hidden_type
    ):
        return "STORE_EXCLUSIVE"

    # ─────────────────────────────────────────────────────────────────
    # FACTOR 4: TWO-FACTOR VERIFICATION NET (Verbose Text Parsing)
    # ── Handles missing/unreliable metadata via Regex on cover_info & title
    # ─────────────────────────────────────────────────────────────────
    text_tier_from_info = categorize_variant_string(cover_info)
    if (
        text_tier_from_info != "MAIN_RELEASE"
        and text_tier_from_info != "UNKNOWN_OPEN_ORDER_VARIANT"
    ):
        return text_tier_from_info

    if hidden_type:
        text_tier_from_type = categorize_variant_string(hidden_type)
        if (
            text_tier_from_type != "MAIN_RELEASE"
            and text_tier_from_type != "UNKNOWN_OPEN_ORDER_VARIANT"
        ):
            return text_tier_from_type

    # ─────────────────────────────────────────────────────────────────
    # FACTOR 5: FINAL FALLBACK / OPEN ORDER
    # ─────────────────────────────────────────────────────────────────
    if cover_info:
        return "ANNUAL_OPEN_ORDER_VARIANT" if is_annual else "OPEN_ORDER_VARIANT"

    title_tier = categorize_variant_string(title)
    if title_tier != "MAIN_RELEASE":
        return title_tier

    return "STANDARD_MAIN_ISSUE"
