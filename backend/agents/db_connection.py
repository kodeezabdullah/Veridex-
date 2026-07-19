"""Minimal Databricks SQL connection setup for the validator runner."""

import os

from databricks import sql
from dotenv import load_dotenv


class DatabricksConfigurationError(RuntimeError):
    """Raised when required Databricks connection settings are unavailable."""


def get_connection():
    """Create a Databricks SQL connection from environment variables."""
    load_dotenv()

    variable_names = (
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_TOKEN",
    )
    settings = {name: os.getenv(name) for name in variable_names}
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise DatabricksConfigurationError(
            "Missing required Databricks environment variables: "
            + ", ".join(missing)
        )

    return sql.connect(
        server_hostname=settings["DATABRICKS_SERVER_HOSTNAME"],
        http_path=settings["DATABRICKS_HTTP_PATH"],
        access_token=settings["DATABRICKS_TOKEN"],
    )
