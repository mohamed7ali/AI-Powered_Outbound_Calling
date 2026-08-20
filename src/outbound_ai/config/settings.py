"""Central configuration, loaded from the environment / .env file.

Every module reads configuration through `get_settings()` and never touches os.environ
directly. Secrets are wrapped in SecretStr so they cannot leak into logs or tracebacks.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/outbound_ai/config/settings.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------------------------------------------------------- LLM providers
    llm_provider: Literal["openai", "gemini", "offline"] = "openai"
    openai_api_key: SecretStr | None = None
    openai_call_model: str = "gpt-4o-mini"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    openai_reasoning_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_embedding_dim: int = 3072

    # ------------------------------------------------------------------- Database
    supabase_url: str = ""
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None
    supabase_jwt_audience: str = "authenticated"
    database_url: SecretStr | None = None
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5
    db_rls_role: str = "authenticated"
    document_storage_bucket: str = "organization-documents"

    # ------------------------------------------------------------------ Telephony
    telephony_provider: Literal["simulated", "vonage"] = "simulated"
    vonage_application_id: str = ""
    vonage_private_key_path: Path = Path("")
    vonage_public_key_path: Path = Path("")
    vonage_from_number: str = ""
    vonage_verify_webhooks: bool = True
    public_webhook_base_url: str = ""
    auth_redirect_url: str = ""
    ui_public_url: str = ""

    # ------------------------------------------------------------------------ App
    app_env: str = "dev"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    gradio_port: int = 7860

    # ----------------------------------------------------------------- RAG tuning
    rag_embedding_provider: Literal["openai", "deterministic"] = "openai"
    rag_top_k_dense: int = 20
    rag_top_k_sparse: int = 20
    rag_rrf_k: int = 60
    rag_top_n_after_rerank: int = 5
    rag_min_grounding_score: float = Field(default=0.7, ge=0.0, le=1.0)
    agent_internal_token: SecretStr | None = None

    # --------------------------------------------------------------------- Derived
    @property
    def audio_cache_path(self) -> Path:
        path = self.audio_cache_dir
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton. Call `get_settings.cache_clear()` in tests to reload."""
    return Settings()
