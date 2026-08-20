"""FastAPI application factory for the Vonage and application APIs."""

from __future__ import annotations

from fastapi import FastAPI

from outbound_ai.api.routers.admin import router as admin_router
from outbound_ai.api.routers.agent import router as agent_router
from outbound_ai.api.routers.auth_ui import router as auth_ui_router
from outbound_ai.api.routers.campaign import router as campaign_router
from outbound_ai.api.routers.documents import router as documents_router
from outbound_ai.api.routers.reports import router as reports_router
from outbound_ai.api.routers.vonage import router as vonage_router


def create_app() -> FastAPI:
    app = FastAPI(title="Arabic Outbound Calls API", version="0.1.0")
    app.include_router(vonage_router, prefix="/vonage", tags=["vonage"])
    app.include_router(agent_router, prefix="/agent", tags=["agent"])
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    app.include_router(auth_ui_router, prefix="/auth", tags=["auth-ui"])
    app.include_router(campaign_router, prefix="/campaign", tags=["campaign"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(reports_router, prefix="/reports", tags=["reports"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
