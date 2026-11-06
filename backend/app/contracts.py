"""Project-scoped immutable contract versions for the local single-user MVP."""

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ApiContract
from app.db.repositories import get_contract, get_project, list_contracts
from app.projects import Database

router = APIRouter(prefix="/api/projects/{project_id}/contracts", tags=["contracts"])
MEDIA_TYPES = {"application/json", "application/yaml", "application/x-yaml", "text/yaml"}
validation_slots = threading.BoundedSemaphore(2)


class UploadMetadata(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    version: str = Field(min_length=1, max_length=100)
    source_name: str | None = Field(default=None, max_length=255)

    @field_validator("version")
    @classmethod
    def plain_version(cls, value: str) -> str:
        if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError("Version labels cannot contain control characters")
        return value

    @field_validator("source_name")
    @classmethod
    def safe_name(cls, value: str | None) -> str | None:
        if value is not None and (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]*\.(json|ya?ml)", value) or ".." in value
        ):
            raise ValueError("Use a plain .json, .yaml or .yml filename without a path")
        return value


class ContractSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    version: str
    openapi_version: str
    source_name: str | None
    created_at: datetime


class ContractDetail(ContractSummary):
    specification: dict[str, Any]


async def uploaded_body(request: Request) -> tuple[bytes, str]:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type not in MEDIA_TYPES:
        raise HTTPException(415, "Send application/json or application/yaml, not multipart data.")
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(415, "Compressed uploads are not supported.")
    return await request.body(), media_type


def validate_upload(raw: bytes, media_type: str) -> dict:
    if not validation_slots.acquire(blocking=False):
        raise HTTPException(503, "Contract validation is busy. Try again shortly.")
    try:
        # No credentials, inherited proxy configuration or user-controlled executable/arguments.
        env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
        try:
            result = subprocess.run(
                [sys.executable, "-m", "app.contract_validation", media_type],
                input=raw,
                capture_output=True,
                timeout=10,
                check=False,
                cwd=Path(__file__).resolve().parents[1],
                env=env,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(422, "Contract validation exceeded the 10-second limit.") from None
        except OSError:
            raise HTTPException(503, "Contract validation is unavailable.") from None
        if result.returncode != 0:
            raise HTTPException(422, "Contract could not be validated within supported limits.")
        try:
            output = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise HTTPException(503, "Contract validator returned an invalid result.") from None
        if not isinstance(output, dict):
            raise HTTPException(503, "Contract validator returned an invalid result.")
        if "error" in output:
            raise HTTPException(422, output["error"])
        specification = output.get("specification")
        if not isinstance(specification, dict) or "openapi" not in specification:
            raise HTTPException(503, "Contract validator returned an invalid result.")
        return specification
    finally:
        validation_slots.release()


def require_project(session: Session, project_id: UUID) -> None:
    if get_project(session, project_id) is None:
        raise HTTPException(404, "Project not found")


def store_contract(
    session: Session, project_id: UUID, metadata: UploadMetadata, raw: bytes, media_type: str
) -> ContractSummary:
    require_project(session, project_id)
    specification = validate_upload(raw, media_type)
    contract = ApiContract(
        project_id=project_id,
        version=metadata.version,
        source_name=metadata.source_name,
        openapi_version=specification["openapi"],
        specification=specification,
    )
    try:
        session.add(contract)
        session.flush()
        summary = ContractSummary.model_validate(contract)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "uq_contracts_project_version"
        ):
            raise HTTPException(
                409, "This project already has that version. Choose a new version label."
            ) from None
        raise
    return summary


@router.post(
    "",
    response_model=ContractSummary,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": {"type": "object"}},
                "application/yaml": {"schema": {"type": "string"}},
            },
        }
    },
)
def upload(
    project_id: UUID,
    metadata: Annotated[UploadMetadata, Query()],
    body: Annotated[tuple[bytes, str], Depends(uploaded_body)],
    session: Database,
) -> ContractSummary:
    return store_contract(session, project_id, metadata, *body)


@router.get("", response_model=list[ContractSummary])
def versions(
    project_id: UUID,
    session: Database,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ContractSummary]:
    require_project(session, project_id)
    return [
        ContractSummary.model_validate(c)
        for c in list_contracts(session, project_id, offset, limit)
    ]


@router.get("/{contract_id}", response_model=ContractDetail)
def detail(project_id: UUID, contract_id: UUID, session: Database) -> ContractDetail:
    require_project(session, project_id)
    contract = get_contract(session, project_id=project_id, contract_id=contract_id)
    if contract is None:
        raise HTTPException(404, "Contract not found in this project")
    return ContractDetail.model_validate(contract)
