import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.request_limits import ProjectBodyLimit


def test_large_upload_is_rejected_before_database():
    with TestClient(app) as client:
        response = client.post(
            f"/api/projects/{uuid4()}/contracts?version=v1",
            content=b"x" * (1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "?version=",
        "?version=%20",
        "?version=v1&source_name=../api.json",
        "?version=v1&unknown=1",
    ],
)
def test_metadata_validation(suffix):
    with patch("app.projects.get_engine", return_value=None), TestClient(app) as client:
        assert client.post(f"/api/projects/{uuid4()}/contracts{suffix}", json={}).status_code == 422


def test_compressed_body_is_not_accepted():
    with TestClient(app) as client:
        response = client.post(
            f"/api/projects/{uuid4()}/contracts?version=v1",
            content=b"gzip",
            headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
        )
        assert response.status_code == 415


def test_chunked_contract_limit():
    async def exercise():
        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 1024 * 1024, "more_body": True},
                {"type": "http.request", "body": b"x", "more_body": False},
            ]
        )
        sent = []

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        async def forbidden(*args):
            pytest.fail("Oversized upload reached parsing or storage")

        await ProjectBodyLimit(forbidden)(
            {"type": "http", "method": "POST", "path": f"/api/projects/{uuid4()}/contracts"},
            receive,
            send,
        )
        assert sent[0]["status"] == 413

    asyncio.run(exercise())


def test_api_docs_describe_raw_upload():
    schema = app.openapi()
    upload = schema["paths"]["/api/projects/{project_id}/contracts"]["post"]
    assert set(upload["requestBody"]["content"]) == {"application/json", "application/yaml"}
    assert any(p["name"] == "version" and p["required"] for p in upload["parameters"])


def test_slow_upload_times_out_before_parsing():
    async def exercise():
        sent = []

        async def receive():
            await asyncio.sleep(1)

        async def send(message):
            sent.append(message)

        async def forbidden(*args):
            pytest.fail("Timed-out body reached parsing")

        timeout = asyncio.timeout
        with patch("app.request_limits.asyncio.timeout", side_effect=lambda _: timeout(0)):
            await ProjectBodyLimit(forbidden)(
                {"type": "http", "method": "POST", "path": f"/api/projects/{uuid4()}/contracts"},
                receive,
                send,
            )
        assert sent[0]["status"] == 408

    asyncio.run(exercise())
