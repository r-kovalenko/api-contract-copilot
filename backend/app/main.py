from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="API Contract Copilot", version="0.1.0")


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness only; database readiness will be added with persistence."""
    return HealthResponse(status="ok", service="api-contract-copilot")
