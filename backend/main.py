"""Veridex FastAPI application entrypoint."""

from fastapi import FastAPI

from backend.routers import coverage, facilities, scenarios

app = FastAPI(
    title="Veridex API",
    version="0.1.0",
    description="Evidence-aware healthcare facility data from Databricks.",
)

app.include_router(facilities.router)
app.include_router(coverage.router)
app.include_router(scenarios.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
