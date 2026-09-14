from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# Regex patterns
_STRICT_ISSUE_ONE_RE = re.compile(r"#1(?:\s*\(.*|\s*$)")
_ISSUE_NUM_EXTRACT_RE = re.compile(r"#\s*(\d+(?:\.\d+)?)")
_SPECIAL_TOKEN_RE = re.compile(r"\b(Annual\s*#?\d+|One-Shot|Special)\b", re.IGNORECASE)


def is_strict_issue_one(title_str: str) -> bool:
    """Checks string for #1 designation."""
    clean_title = str(title_str).strip()
    return bool(_STRICT_ISSUE_ONE_RE.search(clean_title))


def is_primary_base_issue_one(issue: dict[str, Any]) -> bool:
    """
    Evaluates whether an issue payload is a genuine Primary Base Cover A Issue #1.
    Requires both #1 title parsing AND data_parent == 0.
    """
    title_str = (
        issue.get("title") or issue.get("main_title") or issue.get("data_sorting") or ""
    )

    raw_parent_id = issue.get("data_parent")
    if raw_parent_id is None:
        raw_parent_id = issue.get("parent_id", 0)

    try:
        is_cover_a = int(raw_parent_id) == 0
    except (ValueError, TypeError):
        is_cover_a = False

    return is_cover_a and (
        is_strict_issue_one(title_str)
        or issue.get("is_issue_one") is True
        or issue.get("is_primary_base_issue_one") is True
    )


def parse_issue_number(record: dict[str, Any]) -> str:
    """
    Extracts a display token (e.g., '#1', '#24', 'One-Shot', 'Annual #1')
    for issue_master.issue_number. Pure string output for UI/labels.
    """
    raw_num = record.get("issue_number")
    if raw_num is not None and str(raw_num).strip():
        val = str(raw_num).strip()
        return val if val.startswith("#") else f"#{val}"

    title = str(record.get("main_title") or record.get("title") or "").strip()

    # 1. Match named special releases (e.g., 'Annual #1', 'One-Shot')
    special_match = _SPECIAL_TOKEN_RE.search(title)
    if special_match:
        return special_match.group(1).title()

    # 2. Match standard numeric issue numbers (e.g., 'Spawn #300' -> '#300')
    num_match = _ISSUE_NUM_EXTRACT_RE.search(title)
    if num_match:
        token = num_match.group(1)
        return f"#{token}"

    return "Special / Unnumbered"


def parse_sort_order(record: dict[str, Any]) -> Decimal:
    """
    Resolves sort_order for issue_master (NUMERIC(8, 2)).

    Standard issues parse to exact decimals (e.g., 1.00, 2.50).
    Unnumbered specials/annuals map to 9000.00+ with a unique modulo offset
    based on locg_issue_id so pending (NULL series_id) rows stay distinguishable
    once a real series_id is written and UNIQUE(series_id, sort_order) applies.
    """
    raw_sort = record.get("sort_order")
    if raw_sort is not None and str(raw_sort).strip():
        try:
            return Decimal(str(raw_sort).strip())
        except InvalidOperation:
            pass

    title = str(
        record.get("issue_number")
        or record.get("main_title")
        or record.get("title")
        or ""
    ).strip()

    # Extract digits from title if present
    match = _ISSUE_NUM_EXTRACT_RE.search(title)
    if match:
        try:
            return Decimal(match.group(1))
        except InvalidOperation:
            pass

    # Unnumbered fallback: isolated to 9000.00 - 9899.00
    locg_id = int(record.get("locg_issue_id") or 0)
    slot_offset = locg_id % 900
    return Decimal(f"{9000 + slot_offset}.00")
