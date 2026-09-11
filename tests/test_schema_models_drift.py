"""Guardrail: SQLAlchemy models must match db/schema.sql structure.

Applies schema.sql to a throwaway SQLite DB (with light Postgres→SQLite
rewrites), reflects it, and compares tables/columns/nullability/PKs/FKs
against Base.metadata. Catches renames and silent dual-source drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, text

from src.db.models import Base

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def _sqlite_compatible_ddl(sql: str) -> str:
    """Rewrite Postgres-oriented DDL enough for SQLite to execute schema.sql."""
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"\bBIGSERIAL\b", "INTEGER", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bSERIAL\b", "INTEGER", sql, flags=re.IGNORECASE)
    sql = re.sub(
        r"TIMESTAMP\s+WITH\s+TIME\s+ZONE",
        "TIMESTAMP",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


def _statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]


def _fk_signature(fk: dict) -> tuple:
    return (
        tuple(fk["constrained_columns"]),
        fk["referred_table"],
        tuple(fk["referred_columns"]),
    )


@pytest.fixture(scope="module")
def schema_engine():
    raw = SCHEMA_PATH.read_text(encoding="utf-8")
    ddl = _sqlite_compatible_ddl(raw)
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with engine.begin() as conn:
        for statement in _statements(ddl):
            conn.execute(text(statement))

    yield engine
    engine.dispose()


def test_schema_sql_exists():
    assert SCHEMA_PATH.is_file(), f"Missing schema file: {SCHEMA_PATH}"


def test_models_match_schema_tables_and_columns(schema_engine):
    insp = inspect(schema_engine)
    schema_tables = set(insp.get_table_names())
    model_tables = set(Base.metadata.tables)

    assert schema_tables == model_tables, (
        f"Table set drift.\n"
        f"  only in schema.sql: {sorted(schema_tables - model_tables)}\n"
        f"  only in models.py:  {sorted(model_tables - schema_tables)}"
    )

    mismatches: list[str] = []

    for table_name in sorted(model_tables):
        model_table = Base.metadata.tables[table_name]
        db_cols = {col["name"]: col for col in insp.get_columns(table_name)}
        model_cols = {col.name: col for col in model_table.columns}

        if set(db_cols) != set(model_cols):
            mismatches.append(
                f"{table_name} columns:\n"
                f"  only in schema.sql: {sorted(set(db_cols) - set(model_cols))}\n"
                f"  only in models.py:  {sorted(set(model_cols) - set(db_cols))}"
            )
            continue

        db_pk = list(insp.get_pk_constraint(table_name).get("constrained_columns") or [])
        model_pk = [col.name for col in model_table.primary_key.columns]
        if db_pk != model_pk:
            mismatches.append(
                f"{table_name} primary key: schema={db_pk} model={model_pk}"
            )

        # SQLite reflection often reports INTEGER PRIMARY KEY as nullable=True
        # even though those columns are implicitly NOT NULL.
        pk_names = set(db_pk)
        for col_name, model_col in model_cols.items():
            if col_name in pk_names:
                continue
            db_nullable = bool(db_cols[col_name]["nullable"])
            model_nullable = bool(model_col.nullable)
            if db_nullable != model_nullable:
                mismatches.append(
                    f"{table_name}.{col_name} nullable: "
                    f"schema={db_nullable} model={model_nullable}"
                )

        db_fks = {_fk_signature(fk) for fk in insp.get_foreign_keys(table_name)}
        model_fks = set()
        for constraint in model_table.foreign_key_constraints:
            constrained = tuple(col.name for col in constraint.columns)
            referred_table = constraint.elements[0].column.table.name
            referred_cols = tuple(elem.column.name for elem in constraint.elements)
            model_fks.add((constrained, referred_table, referred_cols))

        if db_fks != model_fks:
            mismatches.append(
                f"{table_name} foreign keys:\n"
                f"  schema: {sorted(db_fks)}\n"
                f"  model:  {sorted(model_fks)}"
            )

    assert not mismatches, "Schema/model drift detected:\n" + "\n".join(mismatches)
