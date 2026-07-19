"""Veridex FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from backend.db import warm_up
from backend.routers import coverage, facilities, scenarios, validation

app = FastAPI(
    title="Veridex API",
    version="0.1.0",
    description="Evidence-aware healthcare facility data from Databricks.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facilities.router)
app.include_router(coverage.router)
app.include_router(scenarios.router)
app.include_router(validation.router)


@app.on_event("startup")
def warm_databricks_warehouse() -> None:
    try:
        warm_up()
    except Exception:
        logging.getLogger(__name__).warning("Databricks warm-up query failed; live endpoints will retry on demand", exc_info=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
