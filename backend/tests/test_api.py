"""Automated API foundation tests for CashFlow AI.

Verifies:
1. Health check endpoints (/health and /api/v1/health)
2. Demo forecast endpoints (/api/v1/forecast/demo and /api/v1/forecast)
3. Schema conformity with contracts/forecast-response.example.json:
   - Integer cents for all monetary values
   - Explicit demo labeling and headers
   - ISO 8601 date strings
"""

import json
from pathlib import Path
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


@pytest.mark.anyio
async def test_health_endpoint(client: AsyncClient):
    """GET /health must return status ok with 200 code."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.anyio
async def test_versioned_health_endpoint(client: AsyncClient):
    """GET /api/v1/health must return status ok with 200 code."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.anyio
async def test_demo_forecast_endpoint(client: AsyncClient):
    """GET /api/v1/forecast/demo must return clearly labeled demo forecast."""
    response = await client.get("/api/v1/forecast/demo")
    assert response.status_code == 200
    assert response.headers.get("X-Demo-Data") == "true"

    data = response.json()
    # Contract fields
    assert data["currency"] == "USD"
    assert isinstance(data["safety_reserve_cents"], int)
    assert data["safety_reserve_cents"] == 100000
    assert data["first_reserve_breach_date"] is None

    # Clear demo labeling
    assert data["is_demo"] is True
    assert "DEMO" in data["disclaimer"]

    # Days array validation
    assert isinstance(data["days"], list)
    assert len(data["days"]) > 0

    for day in data["days"]:
        assert isinstance(day["date"], str)
        assert len(day["date"]) == 10  # YYYY-MM-DD
        # Enforce integer cents rule
        assert isinstance(day["opening_balance_cents"], int)
        assert isinstance(day["receipts_cents"], int)
        assert isinstance(day["expenses_cents"], int)
        assert isinstance(day["closing_balance_cents"], int)


@pytest.mark.anyio
async def test_forecast_alias_endpoint(client: AsyncClient):
    """GET /api/v1/forecast returns the demo fixture with demo indicators."""
    response = await client.get("/api/v1/forecast")
    assert response.status_code == 200
    assert response.headers.get("X-Demo-Data") == "true"

    data = response.json()
    assert data["is_demo"] is True
    assert len(data["days"]) > 0


@pytest.mark.anyio
async def test_forecast_contract_json_compliance(client: AsyncClient):
    """Verify demo forecast contains all keys defined in contracts/forecast-response.example.json."""
    contract_file = (
        Path(__file__).resolve().parents[2] / "contracts" / "forecast-response.example.json"
    )
    if contract_file.exists():
        contract_spec = json.loads(contract_file.read_text(encoding="utf-8-sig"))
        response = await client.get("/api/v1/forecast/demo")
        data = response.json()

        # All top-level keys from example contract must be present
        for key in contract_spec.keys():
            assert key in data, f"Missing required contract key: {key}"

        # All keys in days line item must be present
        if contract_spec.get("days"):
            expected_day_keys = set(contract_spec["days"][0].keys())
            for day in data["days"]:
                assert expected_day_keys.issubset(set(day.keys()))


@pytest.mark.anyio
async def test_not_found_endpoint(client: AsyncClient):
    """Unregistered routes must return 404."""
    response = await client.get("/api/v1/non_existent_route")
    assert response.status_code == 404
