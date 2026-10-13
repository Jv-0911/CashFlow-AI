"""Explicit verified-data inputs and evidence for bounded retraining decisions."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, StrictInt, model_validator

from .baselines import validate_history
from .financial_schemas import Identifier, _confirmed
from .persistence_schemas import SafeIdentifier, UTCTimestamp
from .schemas import BaselineConfig, CalendarDate, DailyHistory, ErrorMetrics, FinancialModel, Horizon, MLConfig


class RetrainingPolicy(FinancialModel):
    minimum_new_observations: Annotated[StrictInt, Field(ge=1)] = 14
    maximum_training_age_days: Annotated[StrictInt, Field(ge=1)] = 30
    minimum_final_windows: Annotated[StrictInt, Field(ge=3, le=10)] = 3
    maximum_final_windows: Annotated[StrictInt, Field(ge=3, le=10)] = 6
    minimum_improvement_cents: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 1.0
    minimum_improvement_relative: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = 0.05

    @model_validator(mode="after")
    def ordered_windows(self):
        if self.minimum_final_windows > self.maximum_final_windows:
            raise ValueError("minimum final windows cannot exceed maximum final windows")
        return self


class RetrainingRequest(FinancialModel):
    business_id: SafeIdentifier
    decision_id: SafeIdentifier
    candidate_version: SafeIdentifier
    now: UTCTimestamp
    history: DailyHistory
    verification_evidence_id: Identifier
    verified: Annotated[Literal[True], BeforeValidator(_confirmed)]
    policy: RetrainingPolicy = Field(default_factory=RetrainingPolicy)
    horizon_days: Horizon = 2
    baseline_config: BaselineConfig | None = None
    ml_config: MLConfig | None = None

    @model_validator(mode="after")
    def verified_coverage(self):
        history = validate_history(self.history)
        if not history.days or not history.complete_coverage:
            raise ValueError("retraining requires nonempty, confirmed complete verified history")
        if history.days[-1].date > self.now.date():
            raise ValueError("retraining cannot use future actual observations")
        return self


class DirectionPromotionEvidence(FinancialModel):
    direction: Literal["inflow", "outflow"]
    candidate: ErrorMetrics
    incumbent: ErrorMetrics | None
    best_baseline_method: str
    best_baseline: ErrorMetrics
    final_windows: Annotated[StrictInt, Field(ge=0)]
    paired_mae_gain_cents: float | None = None
    required_gain_cents: float | None = None
    improves_incumbent: bool
    no_material_regression: bool
    reason: str


class RetrainingDecision(FinancialModel):
    decision_id: SafeIdentifier
    business_id: SafeIdentifier
    candidate_version: SafeIdentifier
    status: Literal["not_triggered", "insufficient_evidence", "retained", "promoted", "failed"]
    decided_at: UTCTimestamp
    previous_active_version: SafeIdentifier | None
    active_version: SafeIdentifier | None
    triggers: tuple[str, ...]
    new_verified_observations: Annotated[StrictInt, Field(ge=0)]
    selection_training_end: CalendarDate | None = None
    final_origins: tuple[CalendarDate, ...] = ()
    evaluated_through: CalendarDate | None = None
    evaluation: tuple[DirectionPromotionEvidence, ...] = ()
    reason: str
    warnings: tuple[str, ...] = (
        "Final windows are new chronological outcomes not used in candidate selection; reserved windows are not reused by later decisions, including after failure.",
        "Promotion guards are engineering diagnostics, not calibrated significance tests or real-business accuracy guarantees.",
        "The promoted artifact is the exact pre-holdout candidate; no selection or refitting occurs after observing final outcomes.",
    )
