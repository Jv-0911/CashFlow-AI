"""Pytest fixtures for CashFlow AI backend tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from backend.app.api.app import app


@pytest.fixture
def anyio_backend():
    """Specify asyncio as the AnyIO backend for async tests."""
    return "asyncio"


@pytest.fixture
async def client():
    """Asynchronous HTTPX test client configured with ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
