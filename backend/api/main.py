"""FastAPI application factory for VC Connections API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import contacts, leads, matches, work_history, enrichment, research, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources on startup."""
    from backend.api.dependencies import get_store
    get_store()  # pre-warm the NotionStore singleton
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="VC Connections API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://*.vercel.app",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(contacts.router)
    app.include_router(leads.router)
    app.include_router(matches.router)
    app.include_router(work_history.router)
    app.include_router(enrichment.router)
    app.include_router(research.router)
    app.include_router(settings.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
