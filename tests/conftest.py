from pathlib import Path

import pytest


@pytest.fixture
def sample_html():
    """Loads the recorded HTML snapshot file into memory for testing."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_issue_list.html"
    return fixture_path.read_text(encoding="utf-8")
