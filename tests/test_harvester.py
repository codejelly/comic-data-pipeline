import pytest

from src.parse.comic_parser import parse_comic_harvester_loop


def make_mock_issue_html(
    title: str,
    cover_info: str = None,
    release_epoch: int = 1785297600,
) -> str:
    """Helper function to dynamically wrap title/variants into valid issue HTML."""
    variant_html = (
        f'<span class="variant-name">{cover_info}</span>' if cover_info else ""
    )

    return f"""
    <div id="comic-list-block">
        <ul id="comic-list-issues">
            <li class="issue" data-comic="100" data-parent="0" data-pulls="500">
                <div class="publisher">DC Comics</div>
                <div class="title">
                    <a href="#">{title} {variant_html}</a>
                </div>
                <div class="details">
                    <span class="date" data-date="{release_epoch}">Jul 29th, 2026</span>
                    <span class="price">&nbsp;·&nbsp; $4.99</span>
                </div>
            </li>
        </ul>
    </div>
    """


@pytest.mark.parametrize(
    "title, cover_info, expected_tier",
    [
        ("X-Men #34", None, "STANDARD_MAIN_ISSUE"),
        ("X-Men #34", "Cover B Alex Ross", "STANDARD_VARIANT_B"),
        ("X-Men #34", "Cover E Jim Lee", "STANDARD_VARIANT_E"),
        ("X-Men #34", "1:50 Ratio Variant", "RATIO_INCENTIVE_1:50"),
        ("Batman 2026 Annual #1", None, "ANNUAL_ONE_SHOT"),
    ],
)
def test_classifier_matrix(title, cover_info, expected_tier):
    html_payload = make_mock_issue_html(title, cover_info)
    records = parse_comic_harvester_loop(html_payload)
    assert records[0]["assigned_tier"] == expected_tier


def test_harvester_classification_logic(sample_html):
    records = parse_comic_harvester_loop(sample_html)

    record_map = {r["locg_issue_id"]: r for r in records}
    main_test_issue = record_map.get(9831492)
    assert main_test_issue is not None, "Record 9831492 does not exist"

    expected_values = {
        "main_title": "Doomquest #3",
        "assigned_tier": "STANDARD_MAIN_ISSUE",
        "publisher": "Marvel Comics",
        "retail_price": 4.99,
        "current_pull_count": 5875,
    }

    failures = []

    for field, expected in expected_values.items():
        actual = main_test_issue.get(field)
        if actual != expected:
            failures.append(
                f"Field '{field}' mismatch: expected '{expected}', got '{actual}'"
            )

    assert not failures, "\n".join(failures)
