"""API routes for CashFlow AI foundation.

Exposes:
- GET /health: Simple JSON status check
- GET /api/v1/health: Versioned status check
- GET /api/v1/forecast/demo: Clearly labeled demo forecast matching contracts/forecast-response.example.json
- GET /api/v1/forecast: Forward-compatible alias returning the demo forecast with explicit disclaimer

Business calculations are kept strictly out of the API layer, awaiting
implementation of backend/app/forecast by Member 1 (Financial Engine Developer).
"""

from fastapi import APIRouter, Response
from backend.app.api.schemas import ForecastDay, ForecastResponse, HealthResponse

router = APIRouter()

# Static demo forecast fixture conforming strictly to contracts/forecast-response.example.json
DEMO_FORECAST_FIXTURE = ForecastResponse(
    currency="USD",
    safety_reserve_cents=100000,  # $1,000.00
    first_reserve_breach_date=None,
    days=[
        ForecastDay(
            date="2026-10-10",
            opening_balance_cents=400000,  # $4,000.00
            receipts_cents=0,
            expenses_cents=0,
            closing_balance_cents=400000,
        ),
        ForecastDay(
            date="2026-10-11",
            opening_balance_cents=400000,  # $4,000.00
            receipts_cents=150000,         # $1,500.00
            expenses_cents=50000,          # $500.00
            closing_balance_cents=500000,  # $5,000.00
        ),
        ForecastDay(
            date="2026-10-12",
            opening_balance_cents=500000,  # $5,000.00
            receipts_cents=0,
            expenses_cents=200000,         # $2,000.00
            closing_balance_cents=300000,  # $3,000.00
        ),
    ],
    is_demo=True,
    disclaimer=(
        "DEMO DATA: Real forecasting engine is pending implementation "
        "by Member 1 (Financial Engine Developer) in backend/app/forecast/."
    ),
)


@router.get("/health", response_model=HealthResponse, tags=["Health"])
@router.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
def get_health() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(status="ok", version="0.1.0")


@router.get(
    "/api/v1/forecast/demo",
    response_model=ForecastResponse,
    tags=["Forecast"],
    summary="Get demo forecast fixture",
)
def get_demo_forecast(response: Response) -> ForecastResponse:
    """Return a clearly labeled demo forecast conforming to the shared response contract.

    Notice: Does not perform business calculations. Serves as a static demo fixture
    for integration testing and frontend verification until Member 1 completes the
    calculation engine in backend/app/forecast.
    """
    response.headers["X-Demo-Data"] = "true"
    return DEMO_FORECAST_FIXTURE


@router.get(
    "/api/v1/forecast",
    response_model=ForecastResponse,
    tags=["Forecast"],
    summary="Get forecast (returns demo fixture until engine is implemented)",
)
def get_forecast(response: Response) -> ForecastResponse:
    """Return the forecast response.

    Returns the clearly labeled demo forecast fixture with header indication.
    """
    response.headers["X-Demo-Data"] = "true"
    return DEMO_FORECAST_FIXTURE
