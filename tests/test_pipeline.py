import sqlite3
from datetime import datetime, timezone

import pytest

from src.parse.classifier import dynamic_issue_classifier
from src.parse.comic_parser import parse_comic_harvester_loop


@pytest.fixture
def mock_db():
    """
    Spins up an isolated, structural in-memory database setup for verification.
    Matches our comprehensive multi-tier architecture.
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("DROP TABLE IF EXISTS issue_variants;")
    cursor.execute("DROP TABLE IF EXISTS issue_master;")

    cursor.execute("""
        CREATE TABLE issue_master (
            master_issue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id          INTEGER NOT NULL,
            issue_number       VARCHAR(20) NOT NULL,
            sort_order         REAL NOT NULL,
            type               VARCHAR(30) NOT NULL,
            status             VARCHAR(20) NOT NULL,
            street_date        TEXT NOT NULL,
            publisher          VARCHAR(100) NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE issue_variants (
            variant_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            master_issue_id     INTEGER NOT NULL,
            locg_issue_id       INTEGER UNIQUE NOT NULL,
            variant_type        VARCHAR(40) NOT NULL,
            cover_info          TEXT,
            retail_price        REAL,
            image_url           TEXT,
            current_pull_count  INTEGER DEFAULT 0,
            days_to_street_date INTEGER NOT NULL,
            FOREIGN KEY (master_issue_id) REFERENCES issue_master(master_issue_id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    yield conn
    conn.close()


def test_pipeline_classification_and_cascade_logic(mock_db):
    cursor = mock_db.cursor()

    today_utc = datetime.now(timezone.utc)
    future_epoch_seconds = int(today_utc.timestamp() + (7 * 86400))
    street_datetime = datetime.fromtimestamp(future_epoch_seconds, tz=timezone.utc)

    iso_release_date = street_datetime.date().isoformat()

    cursor.execute("""
        INSERT INTO issue_master (series_id, issue_number, sort_order, type, status, street_date, publisher)
        VALUES (11, 'Avengers: Armageddon #2', 2.0, 'MAIN_RELEASE', 'RELEASED', ?, 'Marvel Comics')
    """, (iso_release_date,))
    parent_id = cursor.lastrowid

    raw_title = "Avengers: Armageddon #2"
    raw_cover_text = "Sukesha Ray Foil Virgin Variant"
    mock_meta = {"format": "comic", "variant_type": raw_cover_text}
    assigned_tier = dynamic_issue_classifier(mock_meta, raw_title)

    calculated_days_delta = (street_datetime.date() - today_utc.date()).days

    cursor.execute("""
        INSERT INTO issue_variants (
            master_issue_id, locg_issue_id, variant_type, cover_info,
            retail_price, image_url, current_pull_count, days_to_street_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (parent_id, 3773849, assigned_tier, raw_cover_text, 4.99,
          "https://s3.amazonaws.com/comicgeeks/covers/medium-3773849.jpg", 10408, calculated_days_delta))
    mock_db.commit()

    cursor.execute("SELECT publisher, street_date FROM issue_master WHERE master_issue_id = ?", (parent_id,))
    row = cursor.fetchone()
    assert row[0] == "Marvel Comics"
    assert row[1] == iso_release_date

    cursor.execute("DELETE FROM issue_master WHERE master_issue_id = ?", (parent_id,))
    mock_db.commit()

    cursor.execute("SELECT COUNT(*) FROM issue_variants WHERE master_issue_id = ?", (parent_id,))
    assert cursor.fetchone()[0] == 0


def test_harvester_full_extraction_behavior():
    """Verifies that the parser extracts titles, publishers, images, and date fields cleanly."""
    html_sample = """
    <div id="comic-list-block">
        <ul id="comic-list-issues">
            <li class="issue" data-comic="3773849" data-parent="0" data-pulls="10408">
                <div class="cover">
                    <a href="/comic/3773849/avengers-armageddon-2">
                        <img class="lazy loaded" src="https://s3.amazonaws.com/comicgeeks/covers/medium-3773849.jpg" alt="avengers">
                    </a>
                </div>
                <div class="publisher color-offset">Marvel Comics</div>
                <div class="title color-primary" data-sorting="Avengers: Armageddon #2">
                    <a href="#">Avengers: Armageddon #2 <span class="variant-name">Sukesha Ray Foil Virgin Variant</span></a>
                </div>
                <div class="details">
                    <span class="price">$4.99</span>
                    <span class="date" data-date="1784088000">Jul 2026</span>
                </div>
            </li>
        </ul>
    </div>
    """
    records = parse_comic_harvester_loop(html_sample)

    assert len(records) == 1
    rec = records[0]

    assert rec["main_title"] == "Avengers: Armageddon #2"
    assert rec["publisher"] == "Marvel Comics"
    assert rec["cover_info"] == "Sukesha Ray Foil Virgin Variant"
    assert rec["retail_price"] == 4.99
    assert rec["image_url"] == "https://s3.amazonaws.com/comicgeeks/covers/medium-3773849.jpg"
    assert rec["current_pull_count"] == 10408

    assert rec["release_date"] == "2026-07-15"
    assert isinstance(rec["days_to_street_date"], int)
