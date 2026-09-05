"""API-level tests: session CRUD, validation, health endpoint shape."""
import pytest


@pytest.mark.asyncio
async def test_create_session(client):
    resp = await client.post("/api/sessions", json={"title": "My chat"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "My chat"
    assert body["llm_provider"] == "ollama"
    assert "id" in body


@pytest.mark.asyncio
async def test_create_session_defaults_title(client):
    resp = await client.post("/api/sessions", json={})
    assert resp.status_code == 201
    assert resp.json()["title"] == "New chat"


@pytest.mark.asyncio
async def test_get_missing_session_404(client):
    import uuid

    resp = await client.get(f"/api/sessions/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_get_session_returns_messages(client, seeded_session):
    resp = await client.get(f"/api/sessions/{seeded_session.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(seeded_session.id)
    assert body["messages"] == []


@pytest.mark.asyncio
async def test_list_sessions(client, seeded_session):
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    assert any(s["id"] == str(seeded_session.id) for s in resp.json())


@pytest.mark.asyncio
async def test_delete_session(client, seeded_session):
    resp = await client.delete(f"/api/sessions/{seeded_session.id}")
    assert resp.status_code == 204
    resp2 = await client.get(f"/api/sessions/{seeded_session.id}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_chat_request_validation_rejects_empty_message(client, seeded_session):
    resp = await client.post(
        "/api/chat", json={"session_id": str(seeded_session.id), "message": "", "mode": "default"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_rejects_unknown_session(client):
    import uuid

    resp = await client.post(
        "/api/chat", json={"session_id": str(uuid.uuid4()), "message": "hello", "mode": "default"}
    )
    assert resp.status_code == 404
