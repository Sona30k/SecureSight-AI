from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentinelX Digital Public Safety API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "development-only-change-this-secret-key"
    algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    database_url: str = "sqlite+aiosqlite:///./sentinelx.db"
    redis_url: str = "redis://localhost:6379/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "sentinelx-password"
    cors_origins: list[str] = Field(default=["http://localhost:5173"])
    storage_path: Path = Path("storage")
    max_upload_mb: int = 10
    rate_limit: str = "100/minute"
    demo_mode: bool = False
    allowed_upload_types: list[str] = Field(default=["image/jpeg", "image/png", "image/webp", "audio/wav", "audio/mpeg", "application/pdf", "text/csv"])

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment == "production":
            if self.secret_key == "development-only-change-this-secret-key" or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a unique value of at least 32 characters in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origins are not allowed in production")
            if self.demo_mode:
                raise ValueError("DEMO_MODE must be disabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
