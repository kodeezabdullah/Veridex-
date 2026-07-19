"""Veridex FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from threading import Thread

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
    print("STARTUP: warm_databricks_warehouse entered", flush=True)
    result: list[BaseException] = []
    worker = Thread(target=lambda: _run_warmup(result), daemon=True)
    worker.start()
    print("STARTUP: warm-up worker started", flush=True)
    worker.join(timeout=35)
    print("STARTUP: warm-up worker join returned", flush=True)
    if worker.is_alive():
        raise TimeoutError("Databricks warm-up SELECT 1 exceeded 35 seconds; check app service-principal permissions on the SQL warehouse.")
    if result:
        raise RuntimeError(f"Databricks warm-up SELECT 1 failed: {result[0]}") from result[0]


def _run_warmup(result: list[BaseException]) -> None:
    try:
        warm_up()
    except BaseException as error:
        result.append(error)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
