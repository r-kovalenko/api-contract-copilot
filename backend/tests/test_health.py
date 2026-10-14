from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_without_external_services():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api-contract-copilot"}


def test_unimplemented_routes_are_not_reported_as_success():
    assert client.post("/analyses", json={}).status_code == 404
