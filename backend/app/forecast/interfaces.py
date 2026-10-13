"""Ready-to-wire Python operations; application authentication stays with JV."""

from typing import Annotated

from pydantic import Field, StrictBool, StrictInt, model_validator

from .financial_schemas import CashForecastRequest, Identifier
from .ingestion import DEFAULT_MAX_BYTES, aggregate_daily, ingest_csv
from .monitoring_schemas import IssuedCashForecast, UTCTimestamp
from .persistence_schemas import SafeIdentifier
from .schemas import CalendarDate, Currency, DailyHistory, FinancialModel, IngestionResult
from .service import forecast_cash_flow


class PreparationRequest(FinancialModel):
    csv_data: bytes | str
    currency: Currency | None = None
    coverage_start: CalendarDate | None = None
    coverage_end: CalendarDate | None = None
    complete_coverage: StrictBool = False
    max_bytes: Annotated[StrictInt, Field(ge=1)] = DEFAULT_MAX_BYTES


class PreparedHistory(FinancialModel):
    source: IngestionResult
    history: DailyHistory


class KnownAheadCovariate(FinancialModel):
    """An extension record retained for adapters, not yet consumed by sklearn models."""

    business_id: SafeIdentifier
    name: Identifier
    date: CalendarDate
    value: Annotated[float, Field(allow_inf_nan=False)] | None
    known_at: UTCTimestamp
    evidence_id: Identifier


class ForecastIssueRequest(FinancialModel):
    issuance_id: SafeIdentifier
    business_id: SafeIdentifier
    generated_at: UTCTimestamp
    financial: CashForecastRequest
    covariates: tuple[KnownAheadCovariate, ...] = ()

    @model_validator(mode="after")
    def known_time_contract(self):
        if any(item.business_id != self.business_id or item.known_at > self.generated_at for item in self.covariates):
            raise ValueError("covariates must belong to this business and be known by forecast issuance")
        identities = [(item.name, item.date) for item in self.covariates]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate covariate name/date records")
        return self


class CovariateDiagnostics(FinancialModel):
    model_support_available: StrictBool = False
    records: tuple[KnownAheadCovariate, ...]
    warnings: tuple[str, ...] = (
        "Optional business covariates are validated and retained but are not consumed by current models.",
        "A future feature adapter must filter known_at at every historical forecast origin, handle missingness, and rerun chronological validation.",
    )


def prepare_history(request: PreparationRequest) -> PreparedHistory:
    request = PreparationRequest.model_validate(request.model_dump())
    source = ingest_csv(request.csv_data, currency=request.currency, max_bytes=request.max_bytes)
    history = aggregate_daily(source, coverage_start=request.coverage_start, coverage_end=request.coverage_end,
        complete_coverage=request.complete_coverage)
    return PreparedHistory(source=source, history=history)


def covariate_diagnostics(request: ForecastIssueRequest) -> CovariateDiagnostics:
    request = ForecastIssueRequest.model_validate(request.model_dump())
    return CovariateDiagnostics(records=request.covariates)


def issue_forecast(request: ForecastIssueRequest, *, trained_model=None) -> IssuedCashForecast:
    """Issue a business-scoped snapshot; no persistence, verification or real payment action."""
    request = ForecastIssueRequest.model_validate(request.model_dump())
    if trained_model is not None:
        if trained_model.metadata.business_id != request.business_id:
            raise ValueError("trained model belongs to another business")
        if trained_model.metadata.trained_at > request.generated_at:
            raise ValueError("forecast cannot precede model training")
    forecast = forecast_cash_flow(request.financial, trained_model=trained_model)
    if request.covariates:
        forecast = forecast.model_copy(update={"warnings": forecast.warnings + covariate_diagnostics(request).warnings})
    version = trained_model.metadata.model_version if trained_model is not None else None
    return IssuedCashForecast(issuance_id=request.issuance_id, business_id=request.business_id,
        generated_at=request.generated_at, inflow_model_version=version if forecast.statistical_inflow_applied else None,
        outflow_model_version=version if forecast.statistical_outflow_applied else None, forecast=forecast)
