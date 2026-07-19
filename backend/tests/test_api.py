from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_route_works_without_external_services():
    assert client.get("/health").json() == {"status": "ok"}


def test_local_frontend_origin_is_allowed_by_cors():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_real_route_fails_gracefully_when_env_is_blank(monkeypatch):
    for name in (
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_TOKEN",
        "LAKEBASE_INSTANCE_NAME",
        "LAKEBASE_HOST",
        "LAKEBASE_DBNAME",
        "LAKEBASE_USER",
        "LAKEBASE_SSLMODE",
    ):
        monkeypatch.setenv(name, "")

    response = client.get("/api/facilities", params={"capability": "ICU"})

    assert response.status_code == 503
    assert "Databricks is not configured" in response.json()["detail"]

    coverage_response = client.get(
        "/api/regions/coverage", params={"capability": "ICU"}
    )
    assert coverage_response.status_code == 503
    assert "Databricks is not configured" in coverage_response.json()["detail"]

    scenario_response = client.get("/api/scenarios")
    assert scenario_response.status_code == 503
    assert "Lakebase is not configured" in scenario_response.json()["detail"]
