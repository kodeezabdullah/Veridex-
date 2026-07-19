from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_and_mock_routes_work_without_databricks_credentials():
    assert client.get("/health").json() == {"status": "ok"}

    coverage = client.get("/api/regions/coverage", params={"capability": "ICU"})
    assert coverage.status_code == 200
    assert {item["coverage_status"] for item in coverage.json()} == {
        "verified_coverage",
        "weak_coverage",
        "no_facility",
        "no_data",
    }

    scenarios = client.get("/api/scenarios")
    assert scenarios.status_code == 200
    assert scenarios.json()[0]["scenario_id"] == "s_mock_001"


def test_real_route_fails_gracefully_when_env_is_blank(monkeypatch):
    for name in ("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN"):
        monkeypatch.setenv(name, "")

    response = client.get("/api/facilities", params={"capability": "ICU"})

    assert response.status_code == 503
    assert "Databricks is not configured" in response.json()["detail"]
