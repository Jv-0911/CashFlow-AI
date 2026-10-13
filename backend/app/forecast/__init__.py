"""Historical forecasting and reconciled, conditional financial projections."""

from .baselines import predict_baseline
from .engine import calculate_balances
from .evaluation import calculate_metrics, rolling_origin_backtest
from .ingestion import IngestionError, aggregate_daily, ingest_csv, read_csv
from .financial_schemas import CashForecastRequest, CashForecastResult, CategoryScheduleCoverage, ScheduledCashEvent, UncertaintyConfig, VerifiedOpeningBalance
from .schemas import BaselineConfig, BalanceResult, DailyCash, DailyHistory, ForecastResult, IngestionResult, MLConfig, Transaction
from .selection import forecast_baselines
from .service import forecast_cash_flow
from .interfaces import (
    CovariateDiagnostics, ForecastIssueRequest, KnownAheadCovariate, PreparationRequest,
    PreparedHistory, covariate_diagnostics, issue_forecast, prepare_history,
)
from .monitoring import LocalForecastMonitor
from .monitoring_schemas import ActualObservation, IssuedCashForecast, MonitoringConfig, MonitoringReport
from .persistence_schemas import DirectionModelMetadata, ModelMetadata, RegistryState
from .reconciliation import reconcile_history
from .retraining_schemas import RetrainingDecision, RetrainingPolicy, RetrainingRequest
from .scenario_schemas import (
    AddEventOperation, ChangeExpenseAmountOperation, ChangeProjectionOperation,
    MoveEventOperation, RemoveEventOperation, ScenarioComparison, ScenarioRequest,
)
from .scenarios import simulate_scenario

__all__ = [
    "BaselineConfig", "BalanceResult", "DailyCash", "DailyHistory", "ForecastResult",
    "IngestionError", "IngestionResult", "MLConfig", "Transaction", "aggregate_daily", "calculate_balances",
    "calculate_metrics", "forecast_baselines", "ingest_csv", "predict_baseline", "read_csv",
    "rolling_origin_backtest",
    "CashForecastRequest", "CashForecastResult", "CategoryScheduleCoverage", "ScheduledCashEvent",
    "UncertaintyConfig", "VerifiedOpeningBalance", "forecast_cash_flow",
    "CovariateDiagnostics", "ForecastIssueRequest", "KnownAheadCovariate", "PreparationRequest",
    "PreparedHistory", "covariate_diagnostics", "issue_forecast", "prepare_history",
    "LocalForecastMonitor", "ActualObservation", "IssuedCashForecast", "MonitoringConfig", "MonitoringReport",
    "DirectionModelMetadata", "ModelMetadata", "RegistryState", "reconcile_history",
    "RetrainingDecision", "RetrainingPolicy", "RetrainingRequest", "retrain_model",
    "AddEventOperation", "ChangeExpenseAmountOperation", "ChangeProjectionOperation", "MoveEventOperation",
    "RemoveEventOperation", "ScenarioComparison", "ScenarioRequest", "simulate_scenario",
    "LocalModelRegistry", "TrainedForecastModel", "forecast_trained_model", "train_forecast_model",
]


def __getattr__(name):
    # Keep CSV, baselines and financial calculations usable without importing sklearn.
    from importlib import import_module
    modules = {"LocalModelRegistry": ".persistence", "retrain_model": ".retraining",
        "TrainedForecastModel": ".trained", "forecast_trained_model": ".trained", "train_forecast_model": ".trained"}
    if name not in modules:
        raise AttributeError(name)
    result = getattr(import_module(modules[name], __name__), name)
    globals()[name] = result
    return result
