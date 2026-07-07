from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ShieldIQ Digital Public Safety API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    enable_api_docs: bool = True
    secret_key: str = "development-only-change-this-secret-key"
    algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    database_url: str = "sqlite+aiosqlite:///./shieldiq.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_recycle_seconds: int = 1800
    redis_url: str = "redis://localhost:6379/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "shieldiq-password"
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])
    allowed_hosts: list[str] = Field(default=["localhost", "127.0.0.1", "testserver", "test"])
    storage_path: Path = Path("storage")
    max_upload_mb: int = 10
    currency_resnet_path: Path | None = None
    currency_classifier_path: Path | None = None
    currency_classifier_arch: str = "efficientnet_b0"
    currency_yolo_path: Path | None = None
    currency_yolo_confidence: float = 0.55
    currency_ocr_gpu: bool = False
    currency_ocr_download_enabled: bool = False
    assistant_provider: str = "auto"
    assistant_request_timeout_seconds: float = 45.0
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.4-mini"
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-3.5-flash"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    mha_alert_webhook_url: str | None = None
    bank_hold_webhook_url: str | None = None
    ncrb_webhook_url: str | None = None
    channel_webhook_secret: str | None = None
    integration_webhook_secret: str | None = None
    rate_limit: str = "100/minute"
    demo_mode: bool = False
    allowed_upload_types: list[str] = Field(default=["image/jpeg", "image/png", "image/webp", "audio/wav", "audio/mpeg", "application/pdf", "text/csv"])

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.currency_classifier_arch not in {"resnet50", "efficientnet_b0"}:
            raise ValueError("CURRENCY_CLASSIFIER_ARCH must be resnet50 or efficientnet_b0")
        if not 0 < self.currency_yolo_confidence <= 1:
            raise ValueError("CURRENCY_YOLO_CONFIDENCE must be between 0 and 1")
        if self.assistant_provider not in {"auto", "openai", "gemini", "llama", "rules"}:
            raise ValueError("ASSISTANT_PROVIDER must be auto, openai, gemini, llama, or rules")
        if self.environment == "production":
            if (
                self.secret_key == "development-only-change-this-secret-key"
                or "change_me" in self.secret_key.lower()
                or len(self.secret_key) < 32
            ):
                raise ValueError("SECRET_KEY must be a unique value of at least 32 characters in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origins are not allowed in production")
            if "*" in self.allowed_hosts or not self.allowed_hosts:
                raise ValueError("ALLOWED_HOSTS must explicitly list production hostnames")
            if self.demo_mode:
                raise ValueError("DEMO_MODE must be disabled in production")
            if not self.database_url.startswith("postgresql+asyncpg://") or "change_me" in self.database_url.lower():
                raise ValueError("Production DATABASE_URL must use postgresql+asyncpg")
            if (
                self.neo4j_password == "shieldiq-password"
                or "change_me" in self.neo4j_password.lower()
                or len(self.neo4j_password) < 12
            ):
                raise ValueError("NEO4J_PASSWORD must be changed to a strong production secret")
            if self.redis_url == "redis://localhost:6379/0" or "change_me" in self.redis_url.lower():
                raise ValueError("REDIS_URL must use production Redis credentials")
            if (self.mha_alert_webhook_url or self.bank_hold_webhook_url or self.ncrb_webhook_url) and not self.integration_webhook_secret:
                raise ValueError("INTEGRATION_WEBHOOK_SECRET is required when external webhooks are enabled")
            if self.assistant_provider == "openai" and not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when ASSISTANT_PROVIDER=openai")
            if self.assistant_provider == "gemini" and not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required when ASSISTANT_PROVIDER=gemini")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
