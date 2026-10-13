"""Issued forecast and verified-actual contracts for local performance monitoring."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BeforeValidator, Field, StrictInt, model_validator

from .financial_schemas import CashForecastResult, Direction, Identifier
from .persistence_schemas import SafeIdentifier
from .schemas import CalendarDate, Currency, ErrorMetrics, FinancialModel, ForecastMethod, Horizon, NonNegativeCents


def _utc_timestamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be an aware UTC datetime") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be an aware UTC datetime")
    return value.astimezone(timezone.utc)


def _explicit_true(value):
    if value is not True:
        raise ValueError("verified and complete daily actuals require explicit boolean true")
    return value


UTCTimestamp = Annotated[datetime, BeforeValidator(_utc_timestamp)]
Confirmed = Annotated[Literal[True], BeforeValidator(_explicit_true)]


class IssuedCashForecast(FinancialModel):
    issuance_id: SafeIdentifier
    business_id: SafeIdentifier
    generated_at: UTCTimestamp
    inflow_model_version: SafeIdentifier | None = None
    outflow_model_version: SafeIdentifier | None = None
    forecast: CashForecastResult

    @model_validator(mode="after")
    def coherent_issuance(self):
        forecast = self.forecast
        issuance_date = self.generated_at.astimezone(ZoneInfo(forecast.business_timezone)).date()
        if issuance_date > forecast.forecast_start_date:
            raise ValueError("issuance business date must not be after forecast start")
        as_of = forecast.model_forecast.as_of
        if as_of is not None and (as_of > issuance_date or as_of >= forecast.forecast_start_date):
            raise ValueError("training origin must be available by issuance and precede forecast targets")
        if forecast.currency != forecast.model_forecast.currency:
            raise ValueError("issued financial and model currencies must match")
        for direction in ("inflow", "outflow"):
            version = getattr(self, f"{direction}_model_version")
            applied = getattr(forecast, f"statistical_{direction}_applied")
            if not applied and version is not None:
                raise ValueError("unapplied statistical directions cannot carry a model version")
            if applied and forecast.model_version is not None and version != forecast.model_version:
                raise ValueError("issued direction model version must match the financial forecast's stored version")
        if len(forecast.days) != forecast.forecast_horizon_days:
            raise ValueError("issued forecast must contain every target day")
        for lead, day in enumerate(forecast.days, 1):
            if day.horizon != lead or day.date != forecast.forecast_start_date + timedelta(days=lead - 1):
                raise ValueError("issued target dates and horizons must be consecutive and aligned")
        return self


class ActualObservation(FinancialModel):
    """A complete verified business day; verification is supplied by the ledger adapter."""

    business_id: SafeIdentifier
    observation_id: SafeIdentifier
    currency: Currency
    date: CalendarDate
    inflow_cents: NonNegativeCents
    outflow_cents: NonNegativeCents
    verified: Confirmed
    complete: Confirmed
    verification_evidence_id: Identifier
    observed_at: UTCTimestamp


class MonitoringConfig(FinancialModel):
    minimum_window_observations: Annotated[StrictInt, Field(ge=3, le=60)] = 5
    minimum_reference_observations: Annotated[StrictInt, Field(ge=3)] = 3
    deterioration_relative: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0.25
    deterioration_absolute_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 1.0
    wape_minimum_actual_cents: Annotated[StrictInt, Field(ge=1)] = 100


class ForecastActualError(FinancialModel):
    issuance_id: SafeIdentifier
    forecast_id: Identifier
    observation_id: SafeIdentifier
    verification_evidence_id: Identifier
    generated_at: UTCTimestamp
    actual_observed_at: UTCTimestamp
    issuance_date: CalendarDate
    model_as_of: CalendarDate | None
    target_date: CalendarDate
    horizon: Horizon
    direction: Direction
    model: ForecastMethod | None
    model_version: SafeIdentifier | None
    predicted_cents: NonNegativeCents
    actual_cents: NonNegativeCents
    error_cents: StrictInt | None
    accuracy_eligible: bool
    ineligible_reason: str | None
    validation_reference_mae_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    reference_unavailable_reason: str | None

    @model_validator(mode="after")
    def no_invented_accuracy(self):
        if self.actual_observed_at <= self.generated_at:
            raise ValueError("verified actual must be observed after forecast issuance")
        if self.accuracy_eligible:
            if self.error_cents != self.predicted_cents - self.actual_cents or self.ineligible_reason is not None:
                raise ValueError("eligible errors must equal predicted minus verified actual")
        elif self.error_cents is not None or self.ineligible_reason is None:
            raise ValueError("ineligible forecasts cannot provide an accuracy error")
        return self


class MissingActual(FinancialModel):
    issuance_id: SafeIdentifier
    target_date: CalendarDate
    horizon: Horizon
    reason: str


class DeteriorationWindow(FinancialModel):
    start_date: CalendarDate
    end_date: CalendarDate
    observations: Annotated[StrictInt, Field(ge=1)]
    metrics: ErrorMetrics
    validation_reference_mae_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    material_deterioration: bool
    comparison_available: bool
    reason: str


class PerformanceGroup(FinancialModel):
    direction: Direction
    horizon: Horizon
    model: ForecastMethod
    model_version: SafeIdentifier | None
    metrics: ErrorMetrics
    forecast_actual_pairs: NonNegativeCents
    unique_actual_dates: NonNegativeCents
    duplicate_target_pairs: NonNegativeCents
    independent_date_metrics: ErrorMetrics
    recent_windows: tuple[DeteriorationWindow, ...]
    material_deterioration: bool
    deterioration_reason: str


class MonitoringReport(FinancialModel):
    business_id: SafeIdentifier
    currency: Currency | None
    recorded_forecasts: NonNegativeCents
    recorded_actual_days: NonNegativeCents
    forecast_actual_pairs: NonNegativeCents
    eligible_direction_errors: NonNegativeCents
    unique_actual_dates: NonNegativeCents
    errors: tuple[ForecastActualError, ...]
    missing_actuals: tuple[MissingActual, ...]
    groups: tuple[PerformanceGroup, ...]
    material_deterioration: bool
    warnings: tuple[str, ...]
