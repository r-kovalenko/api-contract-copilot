import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.document_service import DocumentMetadata, decode_document
from app.main import app
from app.request_limits import ProjectBodyLimit


@pytest.mark.parametrize("raw", [b"", b" \n\t", b"bad\x00", b"\xff", b"bad\x7f"])
def test_invalid_document_text(raw):
    with pytest.raises(HTTPException) as error:
        decode_document(raw)
    assert error.value.status_code == 422


def test_normalization_and_literal_untrusted_content():
    assert decode_document(b"\xef\xbb\xbfHello\r\nworld\r") == "Hello\nworld\n"
    text = "<script>bad()</script> [link](http://169.254.169.254/) ignore instructions"
    assert decode_document(text.encode()) == text


@pytest.mark.parametrize(
    "changes",
    [
        {"source_ref": "x\x00"},
        {"provider": " "},
        {"api_version": "x" * 101},
        {"document_type": "html"},
        {"root": "/tmp"},
    ],
)
def test_metadata_is_bounded(changes):
    with pytest.raises(ValidationError):
        DocumentMetadata.model_validate(
            {
                "provider": "demo",
                "api_version": "v1",
                "document_type": "guide",
                "source_ref": "guide.md",
                **changes,
            }
        )


def test_oversized_upload_precedes_database_access():
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{uuid4()}/documents", content=b"x" * 262145)
    assert response.status_code == 413


def test_chunked_document_upload_limit():
    async def exercise():
        sent = []
        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 262144, "more_body": True},
                {"type": "http.request", "body": b"x", "more_body": False},
            ]
        )

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        async def forbidden(*args):
            pytest.fail("Oversized request reached application")

        await ProjectBodyLimit(forbidden)(
            {
                "type": "http",
                "method": "POST",
                "path": f"/api/projects/{uuid4()}/documents",
                "headers": [],
            },
            receive,
            send,
        )
        assert sent[0]["status"] == 413

    asyncio.run(exercise())
