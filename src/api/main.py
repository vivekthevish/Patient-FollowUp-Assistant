"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import escalations, patients, workflow
from src.db.session import init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Patient Follow-Up Assistant API",
        version="1.0.0",
        description="FastAPI implementation of the Patient Follow-Up Assistant design doc.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(patients.router, prefix="/api/v1")
    app.include_router(workflow.router, prefix="/api/v1")
    app.include_router(escalations.router, prefix="/api/v1")
    return app


app = create_app()

