from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine
from app.knowledge import KnowledgeError, KnowledgeSearch
from app.knowledge_schemas import KnowledgeRequest, KnowledgeResult

router = APIRouter(prefix="/api/projects/{project_id}/knowledge", tags=["knowledge"])


@router.get("/search", response_model=KnowledgeResult)
def search(project_id: UUID, request: Annotated[KnowledgeRequest, Query()]) -> KnowledgeResult:
    try:
        return KnowledgeSearch(get_engine(), project_id).search(request)
    except KnowledgeError as error:
        if error.code == "unknown_project":
            raise HTTPException(404, "Project not found") from None
        raise HTTPException(503, "Knowledge search is unavailable") from None
    except (SQLAlchemyError, ValueError):
        raise HTTPException(503, "Knowledge search is unavailable") from None
