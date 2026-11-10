"""
Application settings loaded from environment variables / backend/.env.
No secrets are hardcoded here — every value is read from the environment,
falling back only to non-sensitive development defaults.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Development defaults. Kept in one place so the deployment check can assert
# that nothing else is silently allowed.
DEV_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql://pesticide_app:CHANGE_ME_PASSWORD@localhost:5432/pesticide_advisory"
    # Managed providers (Neon, Render, Supabase) require TLS. Empty means "use
    # libpq's default", which is what a loopback-only development cluster needs;
    # a public deployment must set DB_SSLMODE=require. It is never defaulted to
    # "require" here, because that would break the local cluster instead.
    db_sslmode: str = ""

    # --- LLM Provider (Module F) ---
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    cloud_llm_api_key: str = ""

    # --- Application ---
    app_env: str = "development"
    log_level: str = "INFO"

    # --- CORS (Phase 9) ---
    # Comma-separated exact origins. A deployed frontend must be named here; the
    # Vite default is only a development convenience. "*" is refused (see
    # main.py) because this API takes free-text input and has no authentication.
    cors_origins: str = DEV_CORS_ORIGINS

    # --- Languages (DEC-003) ---
    supported_languages: str = "en,hi"

    @property
    def supported_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in ("production", "prod")

    def db_connect_args(self) -> dict[str, str]:
        """
        psycopg2 connect arguments derived from settings.

        `application_name` identifies this app's sessions in `pg_stat_activity`.
        `sslmode` is added only when configured: an empty value must not turn
        into sslmode='' , which libpq rejects.
        """
        args = {"application_name": "pesticide_advisory_backend"}
        if self.db_sslmode.strip():
            args["sslmode"] = self.db_sslmode.strip()
        return args


@lru_cache
def get_settings() -> Settings:
    return Settings()
