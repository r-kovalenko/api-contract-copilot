from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.db.readiness import database_ready
from app.db.session import get_engine

app = FastAPI(title="API Contract Copilot", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness remains available even when PostgreSQL is unavailable."""
    return HealthResponse(status="ok", service="api-contract-copilot")


@app.get("/api/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    """Require a reachable database at the expected migration revision with pgvector."""
    try:
        if database_ready(get_engine()):
            return HealthResponse(status="ready", service="api-contract-copilot")
    except (SQLAlchemyError, ValueError):
        # Driver exceptions can contain credentials or host details. Return no raw exception text.
        pass
    raise HTTPException(status_code=503, detail="Database is not ready")
