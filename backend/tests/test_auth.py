import pytest


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    response = await client.post("/auth/register", json={
        "email": "citizen@example.com", "full_name": "A Citizen",
        "password": "VeryStrong!42", "role": "citizen",
    })
    assert response.status_code == 201
    login = await client.post("/auth/login", json={"email": "citizen@example.com", "password": "VeryStrong!42"})
    assert login.status_code == 200
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "citizen"


@pytest.mark.asyncio
async def test_duplicate_registration_rejected(client):
    payload = {"email": "same@example.com", "full_name": "Same User", "password": "VeryStrong!42"}
    assert (await client.post("/auth/register", json=payload)).status_code == 201
    assert (await client.post("/auth/register", json=payload)).status_code == 409


@pytest.mark.asyncio
async def test_refresh_token_issues_a_new_pair(client):
    await client.post("/auth/register", json={
        "email": "refresh@example.com", "full_name": "Refresh User",
        "password": "VeryStrong!42", "role": "citizen",
    })
    login = await client.post("/auth/login", json={"email": "refresh@example.com", "password": "VeryStrong!42"})
    refreshed = await client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
