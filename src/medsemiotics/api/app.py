"""FastAPI application initialization and minimal health check endpoint."""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response payload schema."""

    status: str
    service: str


app = FastAPI(
    title="MedSemiotics Teaching Copilot API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Minimal health check endpoint."""
    return HealthResponse(
        status="ok",
        service="medsemiotics-teaching-copilot",
    )
