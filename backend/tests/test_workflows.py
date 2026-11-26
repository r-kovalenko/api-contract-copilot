from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.workflow_schemas import MessageCreate, SessionCreate, Transition


@pytest.mark.parametrize(
    "data", [{"title": " "}, {"title": "x" * 201}, {"title": "x", "status": "completed"}]
)
def test_session_inputs_are_bounded(data):
    with pytest.raises(ValidationError):
        SessionCreate.model_validate(data)


def test_message_cannot_impersonate_assistant_or_supply_tool_result():
    with pytest.raises(ValidationError):
        MessageCreate.model_validate(
            {"request_id": str(uuid4()), "content": "x", "role": "assistant"}
        )
    with pytest.raises(ValidationError):
        Transition(expected_revision=True, status="running", reason="test")
    with pytest.raises(ValidationError):
        Transition(expected_revision=0, status="approved", reason="test")


@pytest.mark.parametrize("suffix", ["", "/id/messages", "/id/workflow/transitions"])
def test_session_body_limit_precedes_database(suffix):
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{uuid4()}/sessions{suffix}", content=b"x" * 16385)
    assert response.status_code == 413


def test_invalid_text_is_rejected_before_storage():
    for content in ("bad\x00text", "bad\ud800text"):
        with pytest.raises(ValidationError):
            MessageCreate(request_id=uuid4(), content=content)
