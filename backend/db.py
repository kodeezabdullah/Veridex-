"""Lazy, reusable Databricks SQL connection helpers."""

from __future__ import annotations

import os
from threading import RLock
from pathlib import Path
from typing import Any, Mapping, Sequence

from databricks import sql
from dotenv import load_dotenv

DOTENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

REQUIRED_DATABRICKS_ENV = (
    "DATABRICKS_HTTP_PATH",
)


class DatabricksConfigurationError(RuntimeError):
    """Raised when a real-data endpoint is used without complete credentials."""


_connection = None
_connection_lock = RLock()


def get_connection():
    """Create a Databricks SQL connection after validating configuration lazily."""
    missing = [name for name in REQUIRED_DATABRICKS_ENV if not os.getenv(name, "").strip()]
    has_pat = bool(os.getenv("DATABRICKS_TOKEN", "").strip())
    has_app_oauth = bool(os.getenv("DATABRICKS_CLIENT_ID", "").strip() and os.getenv("DATABRICKS_CLIENT_SECRET", "").strip())
    if not has_pat and not has_app_oauth:
        missing.append("DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID/DATABRICKS_CLIENT_SECRET")
    if missing:
        names = ", ".join(missing)
        raise DatabricksConfigurationError(
            f"Databricks is not configured. Set {names} in backend/.env before calling real-data endpoints."
        )

    global _connection
    with _connection_lock:
        if _connection is None:
            hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME", "") or os.getenv("DATABRICKS_HOST", "").replace("https://", "").rstrip("/")
            options = {"server_hostname": hostname, "http_path": os.environ["DATABRICKS_HTTP_PATH"]}
            if has_pat:
                options["access_token"] = os.environ["DATABRICKS_TOKEN"]
            else:
                options.update({"auth_type": "oauth-m2m", "client_id": os.environ["DATABRICKS_CLIENT_ID"], "client_secret": os.environ["DATABRICKS_CLIENT_SECRET"]})
            _connection = sql.connect(**options)
        return _connection


def _drop_connection() -> None:
    global _connection
    with _connection_lock:
        if _connection is not None:
            try:
                _connection.close()
            finally:
                _connection = None


def warm_up() -> None:
    """Wake the warehouse with a lightweight query during application startup."""
    query("SELECT 1")


def query(sql_text: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute SQL on a reused connection, reconnecting once after transport failure."""
    last_error = None
    for attempt in range(2):
        connection = get_connection()
        try:
            with _connection_lock:
                with connection.cursor() as cursor:
                    cursor.execute(sql_text, params or [])
                    if cursor.description is None:
                        return []
                    columns = [column[0] for column in cursor.description]
                    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except Exception as error:
            last_error = error
            _drop_connection()
            if attempt == 0:
                continue
            raise
    raise last_error  # pragma: no cover
