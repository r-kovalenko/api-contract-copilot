import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app
from app.request_limits import ProjectBodyLimit


@pytest.mark.parametrize(
    "payload",
    [
        {"name": " "},
        {"name": "x" * 201},
        {"name": "ok", "description": "x" * 2001},
        {"name": "ok", "id": "untrusted"},
        {"name": 42},
    ],
)
def test_invalid_project_input(payload):
    with patch("app.projects.get_engine", return_value=None), TestClient(app) as client:
        assert client.post("/api/projects", json=payload).status_code == 422


def test_oversized_body_is_rejected_before_database_access():
    with TestClient(app) as client:
        response = client.post("/api/projects", content=b"x" * 16385)
        assert response.status_code == 413


def test_chunked_body_limit_cannot_be_bypassed_without_content_length():
    async def exercise():
        sent = []
        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 8192, "more_body": True},
                {"type": "http.request", "body": b"x" * 8193, "more_body": False},
            ]
        )

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        async def forbidden_app(scope, receive, send):
            pytest.fail("Oversized requests must not reach JSON parsing or storage")

        await ProjectBodyLimit(forbidden_app)(
            {"type": "http", "method": "POST", "path": "/api/projects", "headers": []},
            receive,
            send,
        )
        assert sent[0]["status"] == 413

    asyncio.run(exercise())


def test_database_failure_does_not_disclose_connection_details():
    with (
        patch(
            "app.projects.get_engine",
            side_effect=OperationalError("secret-host", {}, Exception("secret-password")),
        ),
        TestClient(app) as client,
    ):
        response = client.get("/api/projects")
        assert response.status_code == 503
        assert "secret" not in response.text
