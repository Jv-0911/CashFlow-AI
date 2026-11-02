"""Pure transition policy, not an authorisation or payment-evidence boundary.

Passing Origin.VERIFICATION to this function does not grant a write capability.
The persistence layer requires a fresh provider observation for payment outcomes.
"""

from enum import StrEnum
from types import MappingProxyType

from .errors import IllegalTransition
from .models import State


class Origin(StrEnum):
    WORKFLOW = "workflow"
    VERIFICATION = "verification"


_UNCERTAIN = frozenset({State.CANCELLED, State.FAILED, State.UNRESOLVED, State.AWAITING_VERIFICATION})
_PROVIDER_STATES = frozenset({
    State.INVOICE_DRAFTED, State.INVOICE_SENT, State.PAYMENT_PENDING,
    State.PARTIALLY_PAID, State.VERIFIED_PAID, State.OFFLINE_MARKED_PAID,
    State.CANCELLED, State.UNRESOLVED, State.REFUNDED,
})
_FORWARD = {
    State.PROPOSED: frozenset({State.APPROVED}) | _UNCERTAIN,
    State.APPROVED: frozenset({State.INVOICE_DRAFTED, State.INVOICE_SENT, State.PAYMENT_PENDING,
                             State.PARTIALLY_PAID, State.VERIFIED_PAID, State.OFFLINE_MARKED_PAID}) | _UNCERTAIN,
    State.INVOICE_DRAFTED: frozenset({State.INVOICE_SENT, State.PAYMENT_PENDING,
                                    State.PARTIALLY_PAID, State.VERIFIED_PAID, State.OFFLINE_MARKED_PAID}) | _UNCERTAIN,
    State.INVOICE_SENT: frozenset({State.PAYMENT_PENDING, State.PARTIALLY_PAID,
                                 State.VERIFIED_PAID, State.OFFLINE_MARKED_PAID}) | _UNCERTAIN,
    State.PAYMENT_PENDING: frozenset({State.PARTIALLY_PAID, State.VERIFIED_PAID,
                                    State.OFFLINE_MARKED_PAID}) | _UNCERTAIN,
    State.PARTIALLY_PAID: frozenset({State.VERIFIED_PAID}) | _UNCERTAIN,
    State.OFFLINE_MARKED_PAID: _UNCERTAIN,
    # An authenticated inconsistent response can flag a previously paid entry.
    # Outages never invoke this policy and never change the last known state.
    State.VERIFIED_PAID: frozenset({State.REFUNDED, State.UNRESOLVED}),
    State.UNRESOLVED: _PROVIDER_STATES,
    State.AWAITING_VERIFICATION: _PROVIDER_STATES,
    State.CANCELLED: frozenset(),
    State.FAILED: frozenset(),
    State.REFUNDED: frozenset(),
}
TRANSITIONS = MappingProxyType(_FORWARD)


def validate_transition(
    previous: State | None,
    target: State,
    *,
    origin: Origin = Origin.WORKFLOW,
    has_approval: bool = False,
    provider_status: str | None = None,
) -> None:
    if not isinstance(target, State) or not isinstance(origin, Origin):
        raise IllegalTransition("Transition requires explicit policy types.")
    if previous is not None and not isinstance(previous, State):
        raise IllegalTransition("Previous state is invalid.")
    if previous is None:
        if target != State.PROPOSED or origin != Origin.WORKFLOW:
            raise IllegalTransition("An entry must begin as proposed.")
        return
    # Repeated provider observations may be recorded only by verification.
    same_observation = previous == target and target in _PROVIDER_STATES and origin == Origin.VERIFICATION
    if target not in TRANSITIONS[previous] and not same_observation:
        raise IllegalTransition("State transition is not allowed.")
    sensitive = (
        target in {State.VERIFIED_PAID, State.PARTIALLY_PAID, State.REFUNDED}
        or previous in {State.UNRESOLVED, State.AWAITING_VERIFICATION, State.VERIFIED_PAID}
        or (previous == State.INVOICE_DRAFTED and target in {State.PAYMENT_PENDING, State.OFFLINE_MARKED_PAID})
        or (previous == State.APPROVED and target in {State.INVOICE_SENT, State.PAYMENT_PENDING, State.OFFLINE_MARKED_PAID})
    )
    if sensitive and (origin != Origin.VERIFICATION or (not provider_status and target != State.UNRESOLVED)):
        raise IllegalTransition("Fresh provider verification is required.")
    if target in {State.INVOICE_DRAFTED, State.INVOICE_SENT, State.PAYMENT_PENDING,
                  State.PARTIALLY_PAID, State.VERIFIED_PAID, State.OFFLINE_MARKED_PAID,
                  State.REFUNDED} and not has_approval:
        raise IllegalTransition("Recorded human approval is required.")
    if target == State.VERIFIED_PAID and provider_status != "PAID":
        raise IllegalTransition("Paid provider evidence is required.")
    if target == State.PARTIALLY_PAID and provider_status != "PARTIALLY_PAID":
        raise IllegalTransition("Partial payment provider evidence is required.")
