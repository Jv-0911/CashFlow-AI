"""Local, tenant-separated forecast-versus-verified-actual monitoring.

Server-owned JSON snapshots contain issued forecasts, never uploaded CSV files.
The application must authenticate business IDs before calling these methods.
"""

from contextlib import contextmanager
from datetime import timedelta
import fcntl
from math import isfinite
import os
from pathlib import Path
import stat
import tempfile
from zoneinfo import ZoneInfo

from pydantic import Field, TypeAdapter

from .evaluation import calculate_metrics
from .monitoring_schemas import (
    ActualObservation, DeteriorationWindow, ForecastActualError, IssuedCashForecast,
    MissingActual, MonitoringConfig, MonitoringReport, PerformanceGroup, SafeIdentifier,
)
from .schemas import Currency, FinancialModel


_MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024


class _Ledger(FinancialModel):
    schema_version: int = 1
    business_id: SafeIdentifier
    currency: Currency | None = None
    business_timezone: str | None = None
    forecasts: dict[str, IssuedCashForecast] = Field(default_factory=dict)
    actuals: dict[str, ActualObservation] = Field(default_factory=dict)


def _validate_issued(issued):
    issued = IssuedCashForecast.model_validate(issued.model_dump())
    forecast = issued.forecast
    zone = ZoneInfo(forecast.business_timezone)
    issuance_date = issued.generated_at.astimezone(zone).date()
    if issuance_date > forecast.forecast_start_date:
        raise ValueError("issuance business date must not be after forecast start")
    if forecast.model_forecast.as_of is not None and forecast.model_forecast.as_of > issuance_date:
        raise ValueError("forecast training origin must not be after issuance business date")
    if forecast.model_forecast.as_of is not None and forecast.model_forecast.as_of >= forecast.forecast_start_date:
        raise ValueError("forecast origin must precede target dates")
    if forecast.currency != forecast.model_forecast.currency:
        raise ValueError("forecast and model currencies must match")
    if len(forecast.days) != forecast.forecast_horizon_days:
        raise ValueError("issued forecast must contain every target day")
    opening = forecast.opening_balance_cents
    model_days = {day.date: day for day in forecast.model_forecast.days}
    for lead, day in enumerate(forecast.days, 1):
        if day.horizon != lead or day.date != forecast.forecast_start_date + timedelta(days=lead - 1):
            raise ValueError("issued target dates and horizons must be consecutive and aligned")
        if day.opening_balance_cents != opening:
            raise ValueError("issued forecast opening balance must carry forward")
        if day.projected_receipts_cents != day.predicted_residual_inflow_cents + day.known_expected_inflow_cents:
            raise ValueError("issued receipts do not reconcile")
        if day.projected_payments_cents != day.predicted_residual_outflow_cents + day.known_expected_outflow_cents:
            raise ValueError("issued payments do not reconcile")
        if day.projected_closing_balance_cents != opening + day.projected_receipts_cents - day.projected_payments_cents:
            raise ValueError("issued closing balance does not reconcile")
        if day.known_net_cash_adjustment_cents != day.known_expected_inflow_cents - day.known_expected_outflow_cents:
            raise ValueError("issued known cash adjustment does not reconcile")
        if day.reserve_shortfall_cents != max(0, forecast.safety_reserve_cents - day.projected_closing_balance_cents):
            raise ValueError("issued reserve shortfall does not reconcile")
        if day.below_safety_reserve != (day.projected_closing_balance_cents < forecast.safety_reserve_cents):
            raise ValueError("issued reserve breach does not reconcile")
        for direction in ("inflow", "outflow"):
            applied = getattr(forecast, f"statistical_{direction}_applied")
            prediction = getattr(day, f"predicted_residual_{direction}_cents")
            method = getattr(forecast, f"selected_{direction}_model")
            if applied:
                model_day = model_days.get(day.date)
                if method is None or model_day is None or prediction != getattr(model_day, f"predicted_{direction}_cents"):
                    raise ValueError("issued residual prediction must match the applied model")
            elif prediction != 0:
                raise ValueError("unapplied statistical forecasts must have zero residual cash")
        opening = day.projected_closing_balance_cents
    return issued


def _reference(issued, day, direction, config):
    forecast = issued.forecast
    if getattr(forecast.reconciliation, f"{direction}_policy") != "aggregate_prediction":
        return None, "Residual-category validation cannot be compared to verified gross daily actuals."
    if getattr(day, f"known_expected_{direction}_cents") != 0:
        return None, "Known-event-inclusive gross predictions have a different target basis from model validation."
    evaluations = getattr(forecast.model_forecast, f"{direction}_evaluation")
    evaluation = next((item for item in evaluations if item.horizon == day.horizon), None)
    if evaluation is None or not evaluation.has_minimum_evidence:
        return None, "No eligible chronological validation reference for this horizon."
    metrics = getattr(evaluation, direction)
    if metrics.mae_cents is None or metrics.evaluated_observations < config.minimum_reference_observations:
        return None, "Insufficient validation-reference observations."
    return metrics.mae_cents, None


def _metrics(errors, config):
    return calculate_metrics(
        [item.actual_cents for item in errors], [item.predicted_cents for item in errors],
        wape_minimum_actual_cents=config.wape_minimum_actual_cents,
    )


def _performance_group(key, errors, config):
    # Earliest issued prediction wins duplicate date/lead/version ties. Later reissues
    # remain visible in pair metrics, but never increase deterioration evidence.
    independent = {}
    for item in sorted(errors, key=lambda item: (item.generated_at, item.issuance_id)):
        independent.setdefault(item.target_date, item)
    selected = sorted(independent.values(), key=lambda item: item.target_date)
    count = config.minimum_window_observations
    windows = []
    if len(selected) >= 2 * count:
        for subset in (selected[-2 * count:-count], selected[-count:]):
            metrics = _metrics(subset, config)
            references_available = all(item.validation_reference_mae_cents is not None for item in subset)
            # Dividing before summing also keeps the mean within representable range
            # when each individual reference is finite but their sum would overflow.
            reference = sum(item.validation_reference_mae_cents / count for item in subset) if references_available else None
            available = (metrics.mae_cents is not None and isfinite(metrics.mae_cents)
                         and reference is not None and isfinite(reference))
            if not available:
                reference = None
            threshold = max(config.deterioration_absolute_cents, (reference or 0) * config.deterioration_relative)
            deteriorated = available and metrics.mae_cents > reference + threshold
            windows.append(DeteriorationWindow(
                start_date=subset[0].target_date, end_date=subset[-1].target_date,
                observations=len(subset), metrics=metrics,
                validation_reference_mae_cents=reference, comparison_available=available,
                material_deterioration=deteriorated,
                reason=("MAE materially exceeds the mean comparable issuance-time validation MAE."
                        if deteriorated else "MAE does not materially exceed comparable validation."
                        if available else "Diagnostic metrics exceed the finite numeric range."
                        if metrics.mae_cents is None else "At least one prediction has no comparable gross-target validation reference."),
            ))
    sustained = len(windows) == 2 and all(window.material_deterioration for window in windows)
    reason = ("Two consecutive distinct-date windows deteriorated; candidate evaluation is justified, deployment is not."
              if sustained else "Two consecutive comparable windows have not shown material deterioration."
              if windows else f"Need {2 * count} distinct verified actual dates per direction, horizon and model version.")
    return PerformanceGroup(
        direction=key[0], horizon=key[1], model=key[2], model_version=key[3],
        metrics=_metrics(errors, config), forecast_actual_pairs=len(errors),
        unique_actual_dates=len(selected), duplicate_target_pairs=len(errors) - len(selected),
        independent_date_metrics=_metrics(selected, config), recent_windows=tuple(windows),
        material_deterioration=sustained, deterioration_reason=reason,
    )


class LocalForecastMonitor:
    """Caller selects a trusted server directory; customer-supplied paths are unsupported."""

    def __init__(self, root: Path):
        root = Path(root).absolute()
        if root.is_symlink():
            raise ValueError("monitor root must not be a symlink")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not root.is_dir():
            raise ValueError("monitor root must be a directory")
        self.root = root.resolve(strict=True)

    def _tenant(self, business_id):
        business_id = TypeAdapter(SafeIdentifier).validate_python(business_id)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("monitor root changed or became unsafe")
        tenant = self.root / business_id
        if tenant.is_symlink():
            raise ValueError("tenant directory must not be a symlink")
        tenant.mkdir(exist_ok=True, mode=0o700)
        if not tenant.is_dir():
            raise ValueError("tenant path must be a directory")
        return tenant

    @contextmanager
    def _locked(self, business_id):
        tenant = self._tenant(business_id)
        lock = tenant / ".monitor.lock"
        if lock.is_symlink():
            raise ValueError("monitor lock must not be a symlink")
        if lock.exists() and not stat.S_ISREG(lock.stat().st_mode):
            raise ValueError("monitor lock must be a regular file")
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        locked = False
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("monitor lock must be a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield tenant
        finally:
            if locked:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read(self, tenant, business_id):
        path = tenant / "monitor.json"
        if path.is_symlink():
            raise ValueError("monitor snapshot must not be a symlink")
        if not path.exists():
            return _Ledger(business_id=business_id)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("monitor snapshot must be a regular file")
            if info.st_size > _MAX_SNAPSHOT_BYTES:
                raise ValueError("monitor snapshot exceeds the 16 MiB local ledger limit")
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = None
                payload = stream.read(_MAX_SNAPSHOT_BYTES + 1)
            if len(payload) > _MAX_SNAPSHOT_BYTES:
                raise ValueError("monitor snapshot exceeds the 16 MiB local ledger limit")
        finally:
            if descriptor is not None:
                os.close(descriptor)
        ledger = _Ledger.model_validate_json(payload)
        if ledger.schema_version != 1 or ledger.business_id != business_id:
            raise ValueError("monitor snapshot schema or business is incompatible")
        for key, forecast in ledger.forecasts.items():
            if key != forecast.issuance_id or forecast.business_id != business_id:
                raise ValueError("monitor snapshot mixes issuance identities or businesses")
            _validate_issued(forecast)
            if ledger.currency != forecast.forecast.currency or ledger.business_timezone != forecast.forecast.business_timezone:
                raise ValueError("monitor snapshot mixes currencies or business timezones")
        dates = set()
        for key, actual in ledger.actuals.items():
            if key != actual.observation_id or actual.business_id != business_id or actual.currency != ledger.currency:
                raise ValueError("monitor snapshot mixes actual identities, businesses or currencies")
            if actual.date in dates:
                raise ValueError("monitor snapshot contains duplicate actual dates")
            dates.add(actual.date)
        return ledger

    @staticmethod
    def _write(tenant, ledger):
        path = tenant / "monitor.json"
        if path.is_symlink():
            raise ValueError("monitor snapshot must not be a symlink")
        if path.exists() and not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("monitor snapshot must be a regular file")
        payload = ledger.model_dump_json()
        if len(payload.encode("utf-8")) > _MAX_SNAPSHOT_BYTES:
            raise ValueError("monitor snapshot exceeds the 16 MiB local ledger limit; archive records outside this monitor")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=tenant, prefix=".monitor-", suffix=".json", delete=False,
                                             encoding="utf-8") as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def record_forecast(self, issued: IssuedCashForecast) -> str:
        issued = _validate_issued(issued)
        with self._locked(issued.business_id) as tenant:
            ledger = self._read(tenant, issued.business_id)
            previous = ledger.forecasts.get(issued.issuance_id)
            if previous is not None:
                if previous != issued:
                    raise ValueError("issuance_id already exists with a different forecast")
                return issued.issuance_id
            if ledger.currency is not None and ledger.currency != issued.forecast.currency:
                raise ValueError("business monitor cannot mix currencies")
            if ledger.business_timezone is not None and ledger.business_timezone != issued.forecast.business_timezone:
                raise ValueError("business monitor cannot mix business timezones")
            ledger = ledger.model_copy(update={
                "currency": issued.forecast.currency, "business_timezone": issued.forecast.business_timezone,
                "forecasts": {**ledger.forecasts, issued.issuance_id: issued},
            })
            self._write(tenant, ledger)
        return issued.issuance_id

    def record_actual(self, observation: ActualObservation) -> str:
        observation = ActualObservation.model_validate(observation.model_dump())
        with self._locked(observation.business_id) as tenant:
            ledger = self._read(tenant, observation.business_id)
            previous = ledger.actuals.get(observation.observation_id)
            if previous is not None:
                if previous != observation:
                    raise ValueError("observation_id already exists with conflicting actuals")
                return observation.observation_id
            if any(item.date == observation.date for item in ledger.actuals.values()):
                raise ValueError("a verified actual already exists for this business date; corrections need a separate contract")
            if ledger.currency is not None and ledger.currency != observation.currency:
                raise ValueError("business monitor cannot mix currencies")
            # Without a forecast timezone, UTC is conservative: subsequently matched
            # forecasts still check the complete business day in their own timezone.
            zone = ZoneInfo(ledger.business_timezone or "UTC")
            if observation.observed_at.astimezone(zone).date() <= observation.date:
                raise ValueError("verified complete actuals require observation after the business day has ended")
            ledger = ledger.model_copy(update={
                "currency": observation.currency, "actuals": {**ledger.actuals, observation.observation_id: observation},
            })
            self._write(tenant, ledger)
        return observation.observation_id

    def evaluate(self, business_id: str, *, config: MonitoringConfig | None = None) -> MonitoringReport:
        business_id = TypeAdapter(SafeIdentifier).validate_python(business_id)
        config = MonitoringConfig.model_validate((config or MonitoringConfig()).model_dump())
        with self._locked(business_id) as tenant:
            ledger = self._read(tenant, business_id)
        actuals = {item.date: item for item in ledger.actuals.values()}
        errors, missing, grouped = [], [], {}
        matched = 0
        for issued in sorted(ledger.forecasts.values(), key=lambda item: (item.generated_at, item.issuance_id)):
            forecast = issued.forecast
            zone = ZoneInfo(forecast.business_timezone)
            for day in forecast.days:
                actual = actuals.get(day.date)
                reason = None
                if actual is None:
                    reason = "No verified complete actual for this target date."
                elif actual.observed_at <= issued.generated_at:
                    reason = "Actual was already observed at issuance; this is not future forecast accuracy."
                elif actual.observed_at.astimezone(zone).date() <= day.date:
                    reason = "The actual's business day was not complete when observed."
                if reason:
                    missing.append(MissingActual(issuance_id=issued.issuance_id, target_date=day.date,
                                                 horizon=day.horizon, reason=reason))
                    continue
                matched += 1
                for direction in ("inflow", "outflow"):
                    method = getattr(forecast, f"selected_{direction}_model")
                    eligible = forecast.reconciliation.fully_reconciled and getattr(forecast, f"statistical_{direction}_applied")
                    prediction = getattr(day, "projected_receipts_cents" if direction == "inflow" else "projected_payments_cents")
                    verified = getattr(actual, f"{direction}_cents")
                    reference, reference_reason = _reference(issued, day, direction, config) if eligible else (
                        None, "An unreconciled or unapplied statistical forecast has no eligible accuracy reference.",
                    )
                    item = ForecastActualError(
                        issuance_id=issued.issuance_id, forecast_id=forecast.forecast_id,
                        observation_id=actual.observation_id, verification_evidence_id=actual.verification_evidence_id,
                        generated_at=issued.generated_at, actual_observed_at=actual.observed_at,
                        issuance_date=issued.generated_at.astimezone(zone).date(),
                        model_as_of=forecast.model_forecast.as_of, target_date=day.date, horizon=day.horizon,
                        direction=direction, model=method, model_version=getattr(issued, f"{direction}_model_version"),
                        predicted_cents=prediction, actual_cents=verified, error_cents=prediction - verified if eligible else None,
                        accuracy_eligible=eligible,
                        ineligible_reason=None if eligible else "Forecast direction is not fully reconciled with an applied statistical prediction.",
                        validation_reference_mae_cents=reference, reference_unavailable_reason=reference_reason,
                    )
                    errors.append(item)
                    if eligible:
                        key = (direction, day.horizon, method, item.model_version)
                        grouped.setdefault(key, []).append(item)
        groups = tuple(_performance_group(key, values, config) for key, values in sorted(
            grouped.items(), key=lambda pair: (pair[0][0], pair[0][1], pair[0][2], pair[0][3] or ""),
        ))
        warnings = [
            "Accuracy compares issued gross daily predictions with later verified complete gross actuals; it never compares two forecasts.",
            "Rolling forecasts can share actual dates. Pair counts are not independent sample counts; deterioration uses one issuance per date, horizon and model version.",
            "Deterioration is a retraining-evaluation trigger, not permission to promote a model.",
            "Validation references are issuance-time descriptive selection metrics, not an independent final evaluation guarantee.",
        ]
        if any(item.reference_unavailable_reason for item in errors if item.accuracy_eligible):
            warnings.append("Some errors have no comparable validation reference; residual validation is never compared to known-event-inclusive gross actuals.")
        if any(group.metrics.mae_cents is None and group.metrics.evaluated_observations for group in groups):
            warnings.append("Some monetary errors exceed finite diagnostic range; integer errors remain exact but numeric accuracy metrics and deterioration comparisons are unavailable.")
        return MonitoringReport(
            business_id=business_id, currency=ledger.currency, recorded_forecasts=len(ledger.forecasts),
            recorded_actual_days=len(ledger.actuals), forecast_actual_pairs=matched,
            eligible_direction_errors=sum(item.accuracy_eligible for item in errors),
            unique_actual_dates=len({item.target_date for item in errors}), errors=tuple(errors),
            missing_actuals=tuple(missing), groups=groups,
            material_deterioration=any(group.material_deterioration for group in groups), warnings=tuple(warnings),
        )
