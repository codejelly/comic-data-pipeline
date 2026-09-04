from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.db.models import Base

# Use in-memory SQLite for fast testing, or test Postgres URI in CI
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def sample_html():
    """Loads the recorded HTML snapshot file into memory for testing."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_issue_list.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def engine():
    """Creates the engine once for the entire test session."""
    engine = create_engine(TEST_DATABASE_URL)

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Provides a fresh, transactional session per test.
    Rolls back changes after each test so tests never leak data to each other.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
