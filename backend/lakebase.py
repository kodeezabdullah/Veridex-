"""Short-lived Lakebase OAuth credentials and PostgreSQL connections."""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator
import psycopg2
from databricks.sdk import WorkspaceClient
from databricks.sdk.config import Config
from dotenv import load_dotenv

DOTENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

REQUIRED_LAKEBASE_ENV = (
    "LAKEBASE_INSTANCE_NAME",
    "LAKEBASE_HOST",
    "LAKEBASE_DBNAME",
    "LAKEBASE_USER",
    "LAKEBASE_SSLMODE",
    "DATABRICKS_SERVER_HOSTNAME",
    "DATABRICKS_TOKEN",
)


class LakebaseConfigurationError(RuntimeError):
    """Raised when Lakebase cannot be configured from backend/.env."""


def _settings() -> dict[str, str]:
    values = {name: os.getenv(name, "").strip() for name in REQUIRED_LAKEBASE_ENV}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise LakebaseConfigurationError(
            "Lakebase is not configured. Set " + ", ".join(missing) + "."
        )
    return values


@lru_cache(maxsize=1)
def _workspace_client(workspace_host: str, token: str) -> WorkspaceClient:
    config = Config(
        host=workspace_host,
        token=token,
        auth_type="pat",
        http_timeout_seconds=5,
        retry_timeout_seconds=5,
    )
    return WorkspaceClient(config=config)


@lru_cache(maxsize=1)
def _lakebase_endpoint(
    workspace_host: str,
    token: str,
    lakebase_host: str,
) -> str:
    client = _workspace_client(workspace_host, token)
    for project in client.postgres.list_projects():
        for branch in client.postgres.list_branches(parent=project.name):
            for endpoint in client.postgres.list_endpoints(parent=branch.name):
                endpoint_host = getattr(
                    getattr(getattr(endpoint, "status", None), "hosts", None),
                    "host",
                    None,
                )
                if endpoint_host == lakebase_host:
                    return str(endpoint.name)
    raise LakebaseConfigurationError(
        "No Lakebase Autoscaling endpoint matches LAKEBASE_HOST."
    )


def _database_token(settings: dict[str, str]) -> str:
    workspace_host = settings["DATABRICKS_SERVER_HOSTNAME"]
    if not workspace_host.startswith(("http://", "https://")):
        workspace_host = f"https://{workspace_host}"
    client = _workspace_client(workspace_host, settings["DATABRICKS_TOKEN"])
    endpoint_name = _lakebase_endpoint(
        workspace_host,
        settings["DATABRICKS_TOKEN"],
        settings["LAKEBASE_HOST"],
    )
    credential = client.postgres.generate_database_credential(
        endpoint=endpoint_name
    )
    token = getattr(credential, "token", None)
    if not token:
        raise LakebaseConfigurationError(
            "Databricks did not return a Lakebase database credential."
        )
    return str(token)


@contextmanager
def lakebase_connection() -> Iterator[object]:
    """Open one connection with a newly generated short-lived credential."""
    settings = _settings()
    connection = psycopg2.connect(
        host=settings["LAKEBASE_HOST"],
        dbname=settings["LAKEBASE_DBNAME"],
        user=settings["LAKEBASE_USER"],
        password=_database_token(settings),
        sslmode=settings["LAKEBASE_SSLMODE"],
        connect_timeout=15,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
