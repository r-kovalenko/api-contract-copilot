from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_comparison_body_is_bounded_before_database_access():
    with TestClient(app) as client:
        for suffix in ("", "/"):
            response = client.post(
                f"/api/projects/{uuid4()}/comparisons{suffix}",
                content=b"x" * 16385,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 413
