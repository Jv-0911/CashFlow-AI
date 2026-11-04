"""Internal financial and baseline contracts; these do not replace JV's API schemas."""

from datetime import date
import re
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, field_validator

# Phase 1 supports these two-decimal currencies. No currency conversion occurs.
Currency = Literal["USD", "EUR", "GBP", "CAD", "AUD", "INR", "SGD", "NZD", "CHF", "HKD", "CNY"]
NonNegativeCents = Annotated[StrictInt, Field(ge=0)]


def _calendar_date(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    raise ValueError("date must be a date object or YYYY-MM-DD string")


CalendarDate = Annotated[date, BeforeValidator(_calendar_date)]


class FinancialModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Transaction(FinancialModel):
    transaction_id: str = Field(min_length=1)
    date: CalendarDate
    amount_cents: NonNegativeCents
    direction: Literal["inflow", "outflow"]
    currency: Currency
    category: str | None = None
    description: str | None = None
    payment_status: Literal["settled", "pending", "cancelled", "failed"] = "settled"
    source_row: Annotated[StrictInt, Field(ge=2)]
    source_fields: dict[str, str] = Field(default_factory=dict)

    @field_validator("transaction_id")
    @classmethod
    def nonblank_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("transaction_id must not be blank")
        return value


class RowIssue(FinancialModel):
    row: int | None
    code: str
    message: str


class IngestionResult(FinancialModel):
    source_sha256: str
    currency: Currency
    transactions: tuple[Transaction, ...]
    warnings: tuple[RowIssue, ...]
    source_row_count: NonNegativeCents
    duplicate_row_count: NonNegativeCents


class DailyCash(FinancialModel):
    date: CalendarDate
    currency: Currency
    inflow_cents: NonNegativeCents = 0
    outflow_cents: NonNegativeCents = 0
    evidence_ids: tuple[str, ...] = ()


class DailyHistory(FinancialModel):
    currency: Currency
    days: tuple[DailyCash, ...]
    coverage_start: CalendarDate | None = None
    coverage_end: CalendarDate | None = None
    complete_coverage: bool = False
    warnings: tuple[str, ...] = ()


class BalanceDay(FinancialModel):
    date: CalendarDate
    opening_balance_cents: StrictInt
    receipts_cents: NonNegativeCents
    expenses_cents: NonNegativeCents
    closing_balance_cents: StrictInt
    below_safety_reserve: bool
    shortfall_cents: NonNegativeCents
    evidence_ids: tuple[str, ...] = ()


class BalanceResult(FinancialModel):
    currency: Currency
    safety_reserve_cents: NonNegativeCents
    first_reserve_breach_date: CalendarDate | None
    days: tuple[BalanceDay, ...]
    calculation_kind: Literal["deterministic_supplied_cash_flows"] = "deterministic_supplied_cash_flows"
    uncertainty: Literal["not_estimated"] = "not_estimated"
    assumptions: tuple[str, ...] = (
        "Only supplied cash flows are included; omitted days have zero supplied activity.",
        "No statistical predictions or payment verification are performed.",
    )


BaselineMethod = Literal["recent_value", "moving_average", "seasonal_naive"]
MLMethod = Literal["ridge", "random_forest", "hist_gradient_boosting"]
ForecastMethod = Literal["recent_value", "moving_average", "seasonal_naive", "ridge", "random_forest", "hist_gradient_boosting"]
Horizon = Annotated[StrictInt, Field(ge=1, le=30)]
PositiveInt = Annotated[StrictInt, Field(ge=1)]


class BaselineConfig(FinancialModel):
    moving_average_window: PositiveInt = 7
    weekday_samples: PositiveInt = 2
    minimum_history_days: PositiveInt = 14
    minimum_evaluation_windows: PositiveInt = 3
    origin_step: PositiveInt = 1
    maximum_origins: PositiveInt = 60
    # Negligible MAE differences: within max(1 cent, 2% of the best MAE).
    mae_tie_absolute_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 1.0
    mae_tie_relative: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = 0.02
    wape_minimum_actual_cents: PositiveInt = 100


class MLConfig(FinancialModel):
    ridge_minimum_days: Annotated[StrictInt, Field(ge=28)] = 56
    tree_minimum_days: Annotated[StrictInt, Field(ge=42)] = 90
    minimum_training_samples: Annotated[StrictInt, Field(ge=20)] = 28
    inner_validation_days: Annotated[StrictInt, Field(ge=3, le=14)] = 7
    maximum_origins: Annotated[StrictInt, Field(ge=3, le=20)] = 6
    origin_step: PositiveInt = 5
    minimum_comparison_windows: Annotated[StrictInt, Field(ge=3)] = 3
    maximum_missing_fraction: Annotated[float, Field(ge=0, le=0.9, allow_inf_nan=False)] = 0.4
    minimum_improvement_relative: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = 0.05
    minimum_improvement_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 1.0
    random_seed: StrictInt = 42


class CandidateEligibility(FinancialModel):
    method: MLMethod
    eligible: bool
    reason: str


class FeatureReport(FinancialModel):
    method: MLMethod
    direction: Literal["inflow", "outflow"]
    training_start: CalendarDate
    training_end: CalendarDate
    usable_observations: PositiveInt
    feature_group: Literal["calendar", "calendar_and_history"]
    selected_features: tuple[str, ...]
    excluded_features: dict[str, str]
    availability: dict[str, str]
    training_importance: dict[str, float]
    inner_validation_mae_cents: dict[str, float]
    warnings: tuple[str, ...] = ()


class MLPrediction(FinancialModel):
    currency: Currency
    as_of: CalendarDate
    forecast_horizon_days: Horizon
    method: MLMethod
    days: tuple["PredictionDay", ...]
    feature_reports: tuple[FeatureReport, ...]
    fit_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    inference_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]


class PredictionDay(FinancialModel):
    date: CalendarDate
    horizon: Horizon
    predicted_inflow_cents: NonNegativeCents
    predicted_outflow_cents: NonNegativeCents
    effective_method: ForecastMethod


class BaselinePrediction(FinancialModel):
    currency: Currency
    as_of: CalendarDate | None
    forecast_horizon_days: Horizon
    method: BaselineMethod
    status: Literal["predicted", "insufficient_data"]
    days: tuple[PredictionDay, ...]
    warnings: tuple[str, ...] = ()


class ErrorMetrics(FinancialModel):
    evaluated_observations: NonNegativeCents
    mae_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    bias_cents: Annotated[float, Field(allow_inf_nan=False)] | None
    absolute_error_std_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    wape: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    wape_unavailable_reason: Literal["no_observations", "zero_or_near_zero_actuals", "numeric_range_exceeded"] | None


class BacktestPoint(FinancialModel):
    origin: CalendarDate
    date: CalendarDate
    horizon: Horizon
    actual_inflow_cents: NonNegativeCents
    actual_outflow_cents: NonNegativeCents
    predicted_inflow_cents: NonNegativeCents
    predicted_outflow_cents: NonNegativeCents
    effective_method: ForecastMethod


class HorizonEvaluation(FinancialModel):
    horizon: Horizon
    inflow: ErrorMetrics
    outflow: ErrorMetrics
    has_minimum_evidence: bool


class MethodEvaluation(FinancialModel):
    method: ForecastMethod
    horizons: tuple[HorizonEvaluation, ...]
    points: tuple[BacktestPoint, ...]
    fallback_observations: NonNegativeCents
    fit_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0.0
    inference_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0.0
    fold_feature_reports: tuple[FeatureReport, ...] = ()


class BacktestResult(FinancialModel):
    currency: Currency
    forecast_horizon_days: Horizon
    status: Literal["evaluated", "insufficient_data"]
    config: BaselineConfig
    origins: tuple[CalendarDate, ...]
    skipped_unknown_targets: NonNegativeCents
    methods: tuple[MethodEvaluation, ...]
    warnings: tuple[str, ...] = ()
    ml_config: MLConfig | None = None


class BaselineScore(FinancialModel):
    method: ForecastMethod
    eligible: bool
    reason: str
    inflow: ErrorMetrics
    outflow: ErrorMetrics
    selection_evidence: dict[str, str] = Field(default_factory=dict)


class SelectedPredictionDay(FinancialModel):
    date: CalendarDate
    horizon: Horizon
    predicted_inflow_cents: NonNegativeCents
    predicted_outflow_cents: NonNegativeCents
    inflow_method: ForecastMethod
    outflow_method: ForecastMethod
    has_minimum_evidence: bool


class ForecastResult(FinancialModel):
    currency: Currency
    as_of: CalendarDate | None
    forecast_horizon_days: Horizon
    status: Literal["forecast", "insufficient_data"]
    reliability: Literal["limited_backtest_evidence", "insufficient_evidence", "insufficient_data"]
    selected_inflow_model: ForecastMethod | None
    selected_outflow_model: ForecastMethod | None
    selection_basis: Literal["chronological_backtest", "recent_value_fallback", "no_history"]
    selection_reasons: tuple[str, ...]
    days: tuple[SelectedPredictionDay, ...]
    evaluated_horizons: tuple[Horizon, ...]
    inflow_evaluation: tuple[HorizonEvaluation, ...]
    outflow_evaluation: tuple[HorizonEvaluation, ...]
    comparison: tuple[BaselineScore, ...]
    backtest: BacktestResult
    uncertainty: Literal["not_estimated"] = "not_estimated"
    warnings: tuple[str, ...] = ()
    model_eligibility: tuple[CandidateEligibility, ...] = ()
    feature_reports: tuple[FeatureReport, ...] = ()
