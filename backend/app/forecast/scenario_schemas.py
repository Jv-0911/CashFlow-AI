"""Validated hypothetical cash changes; these contracts authorize no payment actions."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, StrictInt, model_validator

from .financial_schemas import CashForecastResult, Direction, Identifier, ScheduledCashEvent
from .schemas import CalendarDate, FinancialModel, NonNegativeCents


def _explicit_hypothetical(value):
    if value is not True:
        raise ValueError("hypothetical events require explicit boolean true")
    return value


class MoveEventOperation(FinancialModel):
    operation: Literal["move_event"] = "move_event"
    operation_id: Identifier
    event_id: Identifier
    expected_date: CalendarDate
    assumption: Identifier


class ChangeExpenseAmountOperation(FinancialModel):
    operation: Literal["change_expense_amount"] = "change_expense_amount"
    operation_id: Identifier
    event_id: Identifier
    amount_cents: NonNegativeCents
    assumption: Identifier


class ChangeProjectionOperation(FinancialModel):
    operation: Literal["change_projection"] = "change_projection"
    operation_id: Identifier
    direction: Direction
    date: CalendarDate
    amount_cents: NonNegativeCents
    assumption: Identifier


class AddEventOperation(FinancialModel):
    operation: Literal["add_event"] = "add_event"
    operation_id: Identifier
    event: ScheduledCashEvent
    hypothetical: Annotated[Literal[True], BeforeValidator(_explicit_hypothetical)]
    assumption: Identifier


class RemoveEventOperation(FinancialModel):
    operation: Literal["remove_event"] = "remove_event"
    operation_id: Identifier
    event_id: Identifier
    assumption: Identifier


ScenarioOperation = Annotated[
    MoveEventOperation | ChangeExpenseAmountOperation | ChangeProjectionOperation |
    AddEventOperation | RemoveEventOperation,
    Field(discriminator="operation"),
]


class ScenarioRequest(FinancialModel):
    scenario_id: Identifier
    operations: Annotated[tuple[ScenarioOperation, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_changes(self):
        operation_ids = [operation.operation_id for operation in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("duplicate scenario operation IDs")
        event_ids = []
        projections = []
        for operation in self.operations:
            if isinstance(operation, ChangeProjectionOperation):
                projections.append((operation.direction, operation.date))
            else:
                event_ids.append(operation.event.event_id if isinstance(operation, AddEventOperation) else operation.event_id)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("an event may be changed only once per scenario; submit a separate scenario for another change")
        if len(projections) != len(set(projections)):
            raise ValueError("a dated directional projection may be changed only once per scenario")
        return self


class ScenarioEventChange(FinancialModel):
    operation_id: Identifier
    operation: Literal["move_event", "change_expense_amount", "add_event", "remove_event"]
    event_id: Identifier
    before: ScheduledCashEvent | None
    after: ScheduledCashEvent | None
    included_before: bool
    included_after: bool
    hypothetical: Literal[True] = True
    assumption: Identifier


class ScenarioProjectionChange(FinancialModel):
    operation_id: Identifier
    direction: Direction
    date: CalendarDate
    before_cents: NonNegativeCents
    after_cents: NonNegativeCents
    assumption: Identifier


class ScenarioDailyDifference(FinancialModel):
    date: CalendarDate
    baseline_closing_balance_cents: StrictInt
    scenario_closing_balance_cents: StrictInt
    closing_balance_difference_cents: StrictInt
    receipts_difference_cents: StrictInt
    payments_difference_cents: StrictInt


class ScenarioComparison(FinancialModel):
    scenario_id: Identifier
    hypothetical: Literal[True] = True
    baseline: CashForecastResult
    scenario: CashForecastResult
    baseline_shortage_date: CalendarDate | None
    scenario_shortage_date: CalendarDate | None
    baseline_minimum_cash_balance_cents: StrictInt
    scenario_minimum_cash_balance_cents: StrictInt
    maximum_reserve_shortfall_change_cents: StrictInt
    daily_differences: tuple[ScenarioDailyDifference, ...]
    changed_events: tuple[ScenarioEventChange, ...]
    changed_projections: tuple[ScenarioProjectionChange, ...]
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
