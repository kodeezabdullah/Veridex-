"""Lakebase-backed scenario persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from backend.lakebase import lakebase_connection
from backend.models import Scenario


def _ensure_schema(cursor: RealDictCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS veridex_scenarios (
            scenario_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );
        CREATE TABLE IF NOT EXISTS veridex_scenario_notes (
            note_id BIGSERIAL PRIMARY KEY,
            scenario_id TEXT NOT NULL REFERENCES veridex_scenarios(scenario_id)
                ON DELETE CASCADE,
            facility_unique_id TEXT NOT NULL,
            note_text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS veridex_scenario_shortlist (
            scenario_id TEXT NOT NULL REFERENCES veridex_scenarios(scenario_id)
                ON DELETE CASCADE,
            facility_unique_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (scenario_id, facility_unique_id)
        )
        """
    )


def _scenario(cursor: RealDictCursor, row: dict[str, Any]) -> Scenario:
    scenario_id = str(row["scenario_id"])
    cursor.execute(
        """
        SELECT facility_unique_id
        FROM veridex_scenario_shortlist
        WHERE scenario_id = %s
        ORDER BY created_at
        """,
        [scenario_id],
    )
    shortlist = [str(item["facility_unique_id"]) for item in cursor.fetchall()]
    cursor.execute(
        """
        SELECT facility_unique_id, note_text, created_at
        FROM veridex_scenario_notes
        WHERE scenario_id = %s
        ORDER BY created_at
        """,
        [scenario_id],
    )
    notes = [
        {
            "facility_id": str(item["facility_unique_id"]),
            "note": str(item["note_text"]),
            "timestamp": item["created_at"].isoformat(),
        }
        for item in cursor.fetchall()
    ]
    return Scenario(
        scenario_id=scenario_id,
        name=str(row["name"]),
        shortlist=shortlist,
        notes=notes,
        overrides=[],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


def list_scenarios() -> list[Scenario]:
    with lakebase_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            _ensure_schema(cursor)
            cursor.execute(
                """
                SELECT scenario_id, name, created_at, updated_at
                FROM veridex_scenarios
                ORDER BY updated_at DESC
                """
            )
            rows = cursor.fetchall()
            return [_scenario(cursor, row) for row in rows]


def create_scenario(name: str) -> Scenario:
    now = datetime.now(UTC)
    scenario_id = f"s_{uuid4().hex[:12]}"
    with lakebase_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            _ensure_schema(cursor)
            cursor.execute(
                """
                INSERT INTO veridex_scenarios
                    (scenario_id, name, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                RETURNING scenario_id, name, created_at, updated_at
                """,
                [scenario_id, name, now, now],
            )
            return _scenario(cursor, cursor.fetchone())


def add_note(scenario_id: str, facility_id: str, note: str) -> Scenario | None:
    with lakebase_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            _ensure_schema(cursor)
            cursor.execute(
                """
                INSERT INTO veridex_scenario_notes
                    (scenario_id, facility_unique_id, note_text)
                SELECT scenario_id, %s, %s
                FROM veridex_scenarios
                WHERE scenario_id = %s
                """,
                [facility_id, note, scenario_id],
            )
            if cursor.rowcount == 0:
                return None
            cursor.execute(
                "UPDATE veridex_scenarios SET updated_at = NOW() WHERE scenario_id = %s",
                [scenario_id],
            )
            cursor.execute(
                "SELECT * FROM veridex_scenarios WHERE scenario_id = %s",
                [scenario_id],
            )
            return _scenario(cursor, cursor.fetchone())


def add_shortlist_item(scenario_id: str, facility_id: str) -> Scenario | None:
    with lakebase_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            _ensure_schema(cursor)
            cursor.execute(
                "SELECT 1 FROM veridex_scenarios WHERE scenario_id = %s",
                [scenario_id],
            )
            if cursor.fetchone() is None:
                return None
            cursor.execute(
                """
                INSERT INTO veridex_scenario_shortlist
                    (scenario_id, facility_unique_id)
                VALUES (%s, %s)
                ON CONFLICT (scenario_id, facility_unique_id) DO NOTHING
                """,
                [scenario_id, facility_id],
            )
            cursor.execute(
                "UPDATE veridex_scenarios SET updated_at = NOW() WHERE scenario_id = %s",
                [scenario_id],
            )
            cursor.execute(
                "SELECT * FROM veridex_scenarios WHERE scenario_id = %s",
                [scenario_id],
            )
            return _scenario(cursor, cursor.fetchone())
