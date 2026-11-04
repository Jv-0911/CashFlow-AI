"""Business-scoped metadata for trusted, locally trained model artifacts."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StrictInt, model_validator

from .schemas import (
    BaselineConfig, CalendarDate, CandidateEligibility, Currency, ErrorMetrics,
    FinancialModel, ForecastMethod, Horizon, MLConfig,
)


SafeIdentifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must include the UTC timezone")
    return value.astimezone(timezone.utc)


UTCTimestamp = Annotated[datetime, AfterValidator(_utc)]


class DirectionModelMetadata(FinancialModel):
    direction: Literal["inflow", "outflow"]
    method: ForecastMethod | None
    selected_features: tuple[str, ...] = ()
    hyperparameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    validation_metrics: ErrorMetrics | None = None
    eligible: bool
    eligibility_reason: str


class ModelMetadata(FinancialModel):
    artifact_format_version: Literal[1] = 1
    business_id: SafeIdentifier
    model_id: SafeIdentifier
    model_version: SafeIdentifier
    currency: Currency
    trained_at: UTCTimestamp
    horizon_days: Horizon
    training_start: CalendarDate | None
    training_end: CalendarDate | None
    training_observations: Annotated[StrictInt, Field(ge=0)]
    history_fingerprint: Sha256
    complete_coverage: bool
    feature_schema_version: str
    inflow: DirectionModelMetadata
    outflow: DirectionModelMetadata
    baseline_config: BaselineConfig
    ml_config: MLConfig | None
    dependency_versions: dict[str, str]
    reliability: Literal["limited_backtest_evidence", "insufficient_evidence", "insufficient_data"]
    evaluated_horizons: tuple[Horizon, ...]
    candidate_eligibility: tuple[CandidateEligibility, ...] = ()
    promotion_evidence: dict[str, object] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def coherent_metadata(self):
        if self.inflow.direction != "inflow" or self.outflow.direction != "outflow":
            raise ValueError("direction metadata must match its declared cash direction")
        if self.training_observations == 0:
            if self.training_start is not None or self.training_end is not None:
                raise ValueError("empty model history has no training dates")
        elif self.training_start is None or self.training_end is None or self.training_end < self.training_start:
            raise ValueError("training metadata requires an ordered date range")
        if any(value > self.horizon_days for value in self.evaluated_horizons):
            raise ValueError("validated horizons exceed the model's configured horizon")
        return self


class ArtifactManifest(FinancialModel):
    manifest_version: Literal[1] = 1
    artifact_filename: Literal["model.joblib"] = "model.joblib"
    artifact_sha256: Sha256
    metadata: ModelMetadata


class RegistryState(FinancialModel):
    registry_format_version: Literal[1] = 1
    business_id: SafeIdentifier
    active_version: SafeIdentifier | None = None
    previous_versions: tuple[SafeIdentifier, ...] = ()
    candidate_versions: tuple[SafeIdentifier, ...] = ()
    failed_versions: dict[SafeIdentifier, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def no_duplicate_versions(self):
        if len(self.previous_versions) != len(set(self.previous_versions)) or len(self.candidate_versions) != len(set(self.candidate_versions)):
            raise ValueError("model registry contains duplicate versions")
        if self.active_version in self.candidate_versions or self.active_version in self.previous_versions:
            raise ValueError("active version cannot also be a candidate or previous version")
        if any(version in self.failed_versions for version in self.candidate_versions):
            raise ValueError("failed version cannot remain an eligible candidate")
        return self
