"""Veridex FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import coverage, facilities, scenarios

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
