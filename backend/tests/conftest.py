import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/sentinelx_test.db"
os.environ["SECRET_KEY"] = "test-secret-that-is-long-enough-for-tests"
os.environ["DEMO_MODE"] = "true"

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
async def database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture
async def auth_headers(client):
    await client.post("/auth/register", json={
        "email": "officer@sentinelx.gov.in", "full_name": "Test Officer",
        "password": "StrongPass!42", "role": "police",
    })
    result = await client.post("/auth/login", json={"email": "officer@sentinelx.gov.in", "password": "StrongPass!42"})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}
