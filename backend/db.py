"""Lazy, reusable Databricks SQL connection helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from databricks import sql
from dotenv import load_dotenv

DOTENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

REQUIRED_DATABRICKS_ENV = (
    "DATABRICKS_SERVER_HOSTNAME",
    "DATABRICKS_HTTP_PATH",
    "DATABRICKS_TOKEN",
)


class DatabricksConfigurationError(RuntimeError):
    """Raised when a real-data endpoint is used without complete credentials."""


def get_connection():
    """Create a Databricks SQL connection after validating configuration lazily."""
    missing = [name for name in REQUIRED_DATABRICKS_ENV if not os.getenv(name, "").strip()]
    if missing:
        names = ", ".join(missing)
        raise DatabricksConfigurationError(
            f"Databricks is not configured. Set {names} in backend/.env before calling real-data endpoints."
        )

    return sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def query(sql_text: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute parameterized SQL and return rows as dictionaries."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_text, params or [])
            if cursor.description is None:
                return []
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        connection.close()
