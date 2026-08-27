from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


def test_openapi_contains_versioned_project_api() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    assert "/api/v1/projects" in schema["paths"]
