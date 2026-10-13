"""Phase 4 internal contracts. Provider status mapping belongs to the payment owner."""

from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BeforeValidator, Field, StrictInt, field_validator, model_validator

from .schemas import (
    BaselineConfig, CalendarDate, Currency, DailyHistory, FinancialModel, ForecastMethod,
    ForecastResult, Horizon, IngestionResult, MLConfig, NonNegativeCents,
)


def _nonblank(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("identifier or assumption must be a nonblank string")
    return value.strip()


def _confirmed(value):
    if value is not True:
        raise ValueError("complete coverage requires explicit boolean true")
    return value


Identifier = Annotated[str, BeforeValidator(_nonblank)]
Category = Annotated[str, BeforeValidator(lambda value: _nonblank(value).casefold())]
Direction = Literal["inflow", "outflow"]
EventStatus = Literal[
    "verified_completed", "invoice_unpaid", "pending_verification", "scheduled_expense",
    "cancelled", "overdue_receivable", "failed",
]


class VerifiedOpeningBalance(FinancialModel):
    balance_cents: StrictInt
    currency: Currency
    balance_date: CalendarDate
    evidence_id: Identifier
    verification_status: Literal["verified"] = "verified"


class ScheduledCashEvent(FinancialModel):
    event_id: Identifier
    source_id: Identifier
    direction: Direction
    amount_cents: NonNegativeCents
    currency: Currency
    status: EventStatus
    category: Category | None = None
    expected_date: CalendarDate | None = None
    due_date: CalendarDate | None = None
    projection_assumption: Identifier | None = None
    historical_transaction_id: Identifier | None = None
    verification_evidence_id: Identifier | None = None

    @model_validator(mode="after")
    def coherent_status(self):
        if self.status in ("invoice_unpaid", "overdue_receivable") and self.direction != "inflow":
            raise ValueError("receivable statuses require inflow direction")
        if self.status == "scheduled_expense" and self.direction != "outflow":
            raise ValueError("scheduled_expense requires outflow direction")
        if self.status == "verified_completed" and self.verification_evidence_id is None:
            raise ValueError("completed status requires a supplied verification evidence identifier")
        return self


class CategoryScheduleCoverage(FinancialModel):
    """Caller attests the entire category's cash schedule for this window, including zeros."""

    category: Category
    direction: Direction
    evidence_id: Identifier
    complete_for_forecast_window: Annotated[Literal[True], BeforeValidator(_confirmed)]


class UncertaintyConfig(FinancialModel):
    minimum_samples: Annotated[StrictInt, Field(ge=3)] = 8


class CashForecastRequest(FinancialModel):
    history: DailyHistory
    opening_balance: VerifiedOpeningBalance
    safety_reserve_cents: NonNegativeCents
    forecast_start_date: CalendarDate
    forecast_horizon_days: Horizon = 2
    known_events: tuple[ScheduledCashEvent, ...] = ()
    historical_transactions: IngestionResult | None = None
    category_coverage: tuple[CategoryScheduleCoverage, ...] = ()
    baseline_config: BaselineConfig = Field(default_factory=BaselineConfig)
    ml_config: MLConfig | None = None
    uncertainty_config: UncertaintyConfig = Field(default_factory=UncertaintyConfig)
    business_timezone: str = "UTC"

    @field_validator("business_timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("business_timezone must be a valid IANA timezone") from exc
        return value


class EventDisposition(FinancialModel):
    event: ScheduledCashEvent
    included: bool
    reason: str


class ReconciliationReport(FinancialModel):
    status: Literal["aggregate_only", "residual_categories", "known_only_fallback", "no_history"]
    fully_reconciled: bool
    inflow_policy: Literal["aggregate_prediction", "category_residual", "known_events_only", "no_prediction"]
    outflow_policy: Literal["aggregate_prediction", "category_residual", "known_events_only", "no_prediction"]
    excluded_historical_transaction_ids: tuple[str, ...] = ()
    coverage_evidence_ids: tuple[str, ...] = ()
    event_dispositions: tuple[EventDisposition, ...] = ()
    warnings: tuple[str, ...] = ()


class ProjectedCashDay(FinancialModel):
    evidence_id: Identifier
    date: CalendarDate
    horizon: Horizon
    opening_balance_cents: StrictInt
    predicted_residual_inflow_cents: NonNegativeCents
    predicted_residual_outflow_cents: NonNegativeCents
    known_expected_inflow_cents: NonNegativeCents
    known_expected_outflow_cents: NonNegativeCents
    known_net_cash_adjustment_cents: StrictInt
    projected_receipts_cents: NonNegativeCents
    projected_payments_cents: NonNegativeCents
    projected_closing_balance_cents: StrictInt
    below_safety_reserve: bool
    reserve_shortfall_cents: NonNegativeCents
    known_event_ids: tuple[str, ...]


class EmpiricalRange(FinancialModel):
    status: Literal["approximate_empirical_range", "unavailable"]
    lower_cents: StrictInt | None = None
    upper_cents: StrictInt | None = None
    validation_samples: Annotated[StrictInt, Field(ge=0)] = 0
    reason: str | None = None

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.status == "unavailable":
            if self.lower_cents is not None or self.upper_cents is not None:
                raise ValueError("unavailable uncertainty must not contain invented bounds")
        elif self.lower_cents is None or self.upper_cents is None or self.lower_cents > self.upper_cents:
            raise ValueError("available empirical range requires ordered bounds")
        return self


class HorizonUncertainty(FinancialModel):
    horizon: Horizon
    date: CalendarDate
    residual_inflow: EmpiricalRange
    residual_outflow: EmpiricalRange
    projected_closing_balance: EmpiricalRange


class CashUncertainty(FinancialModel):
    status: Literal["approximate_empirical_ranges", "partially_available", "unavailable"]
    intervals_available: bool
    method: Literal["held_out_residual_min_max_and_complete_path_errors"] = "held_out_residual_min_max_and_complete_path_errors"
    calibrated_coverage: None = None
    known_event_uncertainty_included: Literal[False] = False
    conditional_on_event_assumptions: Literal[True] = True
    horizons: tuple[HorizonUncertainty, ...]
    warnings: tuple[str, ...]


class KnownEventEffect(FinancialModel):
    event_id: Identifier
    source_id: Identifier
    status: EventStatus
    expected_date: CalendarDate
    signed_balance_effect_cents: StrictInt
    closing_balance_without_event_cents: StrictInt
    reserve_shortfall_difference_cents: StrictInt
    assumption: str


class ShortageEvidence(FinancialModel):
    forecast_day_evidence_id: Identifier
    date: CalendarDate
    closing_balance_cents: StrictInt
    reserve_shortfall_cents: NonNegativeCents
    known_event_effects: tuple[KnownEventEffect, ...]
    opening_balance_evidence_id: Identifier


class CashForecastResult(FinancialModel):
    forecast_id: Identifier
    request_fingerprint: Identifier | None = None
    model_artifact_id: Identifier | None = None
    model_version: Identifier | None = None
    currency: Currency
    business_timezone: str
    forecast_start_date: CalendarDate
    forecast_horizon_days: Horizon
    opening_balance_cents: StrictInt
    opening_balance_evidence_id: Identifier
    safety_reserve_cents: NonNegativeCents
    selected_inflow_model: ForecastMethod | None
    selected_outflow_model: ForecastMethod | None
    statistical_inflow_applied: bool
    statistical_outflow_applied: bool
    model_forecast: ForecastResult
    reconciliation: ReconciliationReport
    days: tuple[ProjectedCashDay, ...]
    first_reserve_breach_date: CalendarDate | None
    minimum_projected_cash_balance_cents: StrictInt
    maximum_reserve_shortfall_cents: NonNegativeCents
    days_below_reserve: Annotated[StrictInt, Field(ge=0)]
    risk_assessment_complete: bool
    shortage_evidence: tuple[ShortageEvidence, ...]
    uncertainty: CashUncertainty
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
