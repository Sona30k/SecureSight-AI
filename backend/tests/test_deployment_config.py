import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def production_settings(**overrides):
    values = {
        "environment": "production",
        "enable_api_docs": False,
        "secret_key": "a" * 64,
        "database_url": "postgresql+asyncpg://shieldiq:secure@postgres:5432/shieldiq",
        "redis_url": "redis://:secure-redis-password@redis:6379/0",
        "neo4j_uri": "bolt://neo4j:7687",
        "neo4j_password": "secure-neo4j-password",
        "cors_origins": ["https://shieldiq.example.gov.in"],
        "allowed_hosts": ["shieldiq.example.gov.in"],
        "demo_mode": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_production_configuration_is_accepted():
    settings = production_settings()
    assert settings.environment == "production"
    assert settings.database_url.startswith("postgresql+asyncpg://")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("secret_key", "CHANGE_ME_generate_with_openssl_rand_hex_32"),
        ("database_url", "sqlite+aiosqlite:///./shieldiq.db"),
        ("redis_url", "redis://localhost:6379/0"),
        ("neo4j_password", "shieldiq-password"),
        ("allowed_hosts", ["*"]),
        ("demo_mode", True),
    ],
)
def test_insecure_production_configuration_is_rejected(field, value):
    with pytest.raises(ValidationError):
        production_settings(**{field: value})


@pytest.mark.asyncio
async def test_liveness_readiness_and_security_headers(client):
    live = await client.get("/health/live")
    ready = await client.get("/health/ready")
    auth = await client.post(
        "/auth/login",
        headers={"X-Forwarded-Proto": "https"},
        json={"email": "missing@example.com", "password": "WrongPassword!42"},
    )

    assert live.status_code == 200
    assert ready.status_code == 200
    assert auth.headers["cache-control"] == "no-store"
    assert auth.headers["strict-transport-security"].startswith("max-age=")
