"""Contracts for rescue analysis; no provider calls or financial side effects.

Amounts are integer cents. Dates are calendar dates. The caller supplies verified
records; these models validate structure, not provider payment authenticity.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Cents = Annotated[int, Field(strict=True)]
NonNegativeCents = Annotated[int, Field(strict=True, ge=0)]
RecordId = Annotated[str, Field(strict=True, min_length=1, pattern=r"^\S+$")]
Currency = Annotated[str, Field(strict=True, pattern=r"^[A-Z]{3}$")]
Text = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]


class RescueModel(BaseModel):
    """Reject unknown fields instead of silently discarding integration errors."""

    model_config = ConfigDict(extra="forbid")


class ForecastDay(RescueModel):
    """One projected day, matching the existing forecast example fields."""

    date: date
    opening_balance_cents: Cents
    receipts_cents: NonNegativeCents
    expenses_cents: NonNegativeCents
    closing_balance_cents: Cents

    @model_validator(mode="after")
    def validate_balance(self):
        expected = self.opening_balance_cents + self.receipts_cents - self.expenses_cents
        if self.closing_balance_cents != expected:
            raise ValueError("Daily closing balance does not match receipts and expenses")
        return self


class ForecastEvidence(RescueModel):
    """Forecast snapshot. Empty days mean insufficient evidence, not safety."""

    currency: Currency
    safety_reserve_cents: NonNegativeCents
    first_reserve_breach_date: date | None
    days: list[ForecastDay] = Field(max_length=30)
    is_demo: bool = False
    disclaimer: str | None = None

    @model_validator(mode="after")
    def validate_days(self):
        for previous, current in zip(self.days, self.days[1:]):
            if (current.date - previous.date).days != 1:
                raise ValueError("Forecast days must be consecutive and ordered")
            if current.opening_balance_cents != previous.closing_balance_cents:
                raise ValueError("Forecast balances must carry forward between days")
        breach = next(
            (day.date for day in self.days
             if day.closing_balance_cents < self.safety_reserve_cents),
            None,
        )
        if self.first_reserve_breach_date != breach:
            raise ValueError("Reserve breach date must match the supplied daily balances")
        return self


class InvoiceEvidence(RescueModel):
    """Outstanding amount is supplied by the ledger, never inferred by AI.

    Status is an application state proposed for Member 3's adapter. A pending
    invoice is not a verified receipt. No customer names or emails are needed.
    """

    invoice_id: RecordId
    currency: Currency
    outstanding_amount_cents: NonNegativeCents
    due_date: date
    status: Literal["unpaid", "pending", "paid", "cancelled"]

    @model_validator(mode="after")
    def validate_paid_amount(self):
        if self.status == "paid" and self.outstanding_amount_cents != 0:
            raise ValueError("A paid invoice cannot have an outstanding amount")
        return self


class TransactionEvidence(RescueModel):
    """Evidence for diagnosis; never added again to an existing forecast."""

    transaction_id: RecordId
    currency: Currency
    amount_cents: NonNegativeCents
    date: date
    direction: Literal["receipt", "expense"]
    status: Literal["projected", "verified", "cancelled"]
    discretionary: bool = False


class RescueAnalysisRequest(RescueModel):
    """Proposed module input for the integration lead to map to API records.

    forecast_id names the supplied snapshot for response citations. as_of_date
    makes overdue classification reproducible rather than using the system clock.
    """

    as_of_date: date
    forecast_id: RecordId
    forecast: ForecastEvidence
    invoices: list[InvoiceEvidence] = Field(default_factory=list)
    transactions: list[TransactionEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence(self):
        identifiers = [self.forecast_id]
        for record in [*self.invoices, *self.transactions]:
            if record.currency != self.forecast.currency:
                raise ValueError("All evidence must use the forecast currency")
            identifiers.append(
                record.invoice_id if isinstance(record, InvoiceEvidence)
                else record.transaction_id
            )
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Evidence identifiers must be unique across the request")
        return self


class RecoveryAction(RescueModel):
    """Proposed action, never an executed payment or guaranteed cash receipt.

    Optional additions preserve parsing of the team's existing response example.
    null estimated impact means it cannot be calculated from supplied evidence.
    """

    action_id: RecordId
    title: Text
    estimated_impact_cents: NonNegativeCents | None
    assumptions: list[Text] = Field(min_length=1)
    explanation: Text | None = None
    evidence_ids: list[RecordId] = Field(default_factory=list)
    currency: Currency | None = None
    priority: Annotated[int, Field(strict=True, ge=1)] | None = None
    requires_approval: bool = True


class RescueResponse(RescueModel):
    """Existing response fields plus optional metadata for integration review.

    These structural checks cannot establish that citations support a statement;
    the analysis service must check references and financial claims separately.
    """

    summary: Text
    risk_level: Literal["low", "medium", "high", "unknown"]
    evidence_ids: list[RecordId]
    recommended_actions: list[RecoveryAction]
    currency: Currency | None = None
    assumptions: list[Text] = Field(default_factory=list)
    source: Literal["deterministic", "ai"] = "deterministic"
    is_demo: bool = False

    @model_validator(mode="after")
    def validate_actions(self):
        action_ids = [action.action_id for action in self.recommended_actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("Action identifiers must be unique")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Response evidence identifiers must be unique")
        for action in self.recommended_actions:
            if not set(action.evidence_ids).issubset(self.evidence_ids):
                raise ValueError("Action evidence must appear in response evidence")
            if action.currency is not None and action.currency != self.currency:
                raise ValueError("Action currency must match response currency")
        return self
