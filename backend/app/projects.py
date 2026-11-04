"""Single-user local project workspace; authentication is deferred to deployment."""

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Project
from app.db.repositories import list_projects
from app.db.session import get_engine, session_scope

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime


def project_session() -> Iterator[Session]:
    try:
        with session_scope(get_engine()) as session:
            yield session
    except (SQLAlchemyError, ValueError):
        raise HTTPException(503, "Project storage is unavailable. Try again later.") from None


Database = Annotated[Session, Depends(project_session)]


def create_project(session: Session, data: ProjectCreate) -> ProjectView:
    project = Project(name=data.name, description=data.description or None)
    session.add(project)
    session.flush()
    result = ProjectView.model_validate(project)
    # Commit before reporting success, including when used with a yield dependency.
    session.commit()
    return result


@router.post("", response_model=ProjectView, status_code=201)
def create(data: ProjectCreate, session: Database) -> ProjectView:
    return create_project(session, data)


@router.get("", response_model=list[ProjectView])
def index(
    session: Database,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ProjectView]:
    return [ProjectView.model_validate(p) for p in list_projects(session, offset, limit)]


@router.get("/{project_id}", response_model=ProjectView)
def detail(project_id: UUID, session: Database) -> ProjectView:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return ProjectView.model_validate(project)
