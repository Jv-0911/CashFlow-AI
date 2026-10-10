"""Pydantic schemas for CashFlow AI API layer.

Follows the shared API contracts defined in /contracts:
- Monetary amounts must be represented in integer cents.
- Dates follow ISO 8601 formatting.
- Currencies follow ISO 4217.
- Demo data must be clearly labeled.
"""

from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field("ok", description="Application health status")
    version: str = Field("0.1.0", description="API version")


class ForecastDay(BaseModel):
    """Daily forecast line item schema adhering to contracts/forecast-response.example.json."""
    date: str = Field(..., description="ISO 8601 date string, e.g. YYYY-MM-DD")
    opening_balance_cents: int = Field(..., description="Opening cash balance in integer cents")
    receipts_cents: int = Field(..., description="Projected incoming cash receipts in integer cents")
    expenses_cents: int = Field(..., description="Projected outgoing cash expenses in integer cents")
    closing_balance_cents: int = Field(..., description="Projected closing cash balance in integer cents")


class ForecastResponse(BaseModel):
    """Forecast response schema adhering to contracts/forecast-response.example.json."""
    currency: str = Field("USD", description="ISO 4217 currency code")
    safety_reserve_cents: int = Field(100000, description="Configured safety reserve threshold in integer cents")
    first_reserve_breach_date: Optional[str] = Field(
        None,
        description="First ISO 8601 date when closing balance drops below safety reserve, or None if safe"
    )
    days: list[ForecastDay] = Field(..., description="List of daily cash-flow forecast projections")
    is_demo: bool = Field(True, description="Explicit flag indicating this response is demo fixture data")
    disclaimer: str = Field(
        "DEMO FORECAST DATA: The deterministic financial engine will be implemented in backend/app/forecast by Member 1.",
        description="Notice confirming no business calculations have been performed by the API layer"
    )
