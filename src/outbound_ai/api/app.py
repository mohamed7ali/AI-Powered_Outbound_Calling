"""FastAPI application factory for the Vonage and application APIs."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from outbound_ai.api.routers.admin import router as admin_router
from outbound_ai.api.routers.agent import router as agent_router
from outbound_ai.api.routers.auth_ui import router as auth_ui_router
from outbound_ai.api.routers.campaign import router as campaign_router
from outbound_ai.api.routers.documents import router as documents_router
from outbound_ai.api.routers.reports import router as reports_router
from outbound_ai.api.routers.vonage import router as vonage_router
from outbound_ai.config.settings import get_settings
from outbound_ai.telephony.local_voice import prewarm_local_voice
from outbound_ai.telephony.prompts import (
    GREETING_TEXT,
    HANDOFF_TEXT,
    PROCESSING_TEXT,
    RESOLVED_TEXT,
    UNRESOLVED_TEXT,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Arabic Outbound Calls API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(vonage_router, prefix="/vonage", tags=["vonage"])
    app.include_router(agent_router, prefix="/agent", tags=["agent"])
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    app.include_router(auth_ui_router, prefix="/auth", tags=["auth-ui"])
    app.include_router(campaign_router, prefix="/campaign", tags=["campaign"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(reports_router, prefix="/reports", tags=["reports"])

    @app.on_event("startup")
    def prewarm_voice_models() -> None:
        settings = get_settings()
        if settings.local_stt_enabled or settings.local_tts_enabled:
            prewarm_local_voice([
                GREETING_TEXT,
                PROCESSING_TEXT,
                HANDOFF_TEXT,
                RESOLVED_TEXT,
                UNRESOLVED_TEXT,
            ])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
