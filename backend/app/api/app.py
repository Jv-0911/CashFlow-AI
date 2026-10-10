"""FastAPI application factory for CashFlow AI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="CashFlow AI 2.0 API",
        description=(
            "CashFlow AI API foundation providing initial health checks and contract-compliant "
            "demo endpoints. Business calculation and AI modules are separated by team ownership."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable CORS for local development with frontend (Vite/React default ports)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(router)

    return app


app = create_app()
