"""Integration tests for the FastAPI app."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_search_empty(client):
    """Search with empty index returns zero results gracefully."""
    resp = await client.get("/api/search?q=hello")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "hits" in data


@pytest.mark.asyncio
async def test_suggest(client):
    resp = await client.get("/api/suggest?q=test")
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data


@pytest.mark.asyncio
async def test_index_status(client):
    resp = await client.get("/api/index/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_files" in data
    assert "indexed" in data
