"""Public write interface: specific commands, never arbitrary state or actor roles."""

from pathlib import Path

from .errors import IntegrityViolation
from .models import IntegrityCheckpoint, LedgerEntry, LedgerEvent, LedgerSnapshot, State
from .store import LedgerStore


def _verified_recovered_cash(snapshots: tuple[LedgerSnapshot, ...]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for snapshot in snapshots:
        entry = snapshot.entry
        totals.setdefault(entry.currency, 0)
        if snapshot.state == State.VERIFIED_PAID:
            latest = snapshot.events[-1]
            if (latest.paid_amount_cents != entry.amount_cents
                    or type(latest.paid_amount_cents) is not int
                    or latest.provider_status != "PAID"):
                raise IntegrityViolation("Verified cash evidence is inconsistent.")
            totals[entry.currency] += entry.amount_cents
    return totals


class LedgerService:
    def __init__(self, db_path: str | Path):
        self._store = LedgerStore(db_path)

    def propose(self, *, idempotency_key: str, amount_cents: int, currency: str) -> LedgerEntry:
        return self._store._propose(idempotency_key=idempotency_key,
                                    amount_cents=amount_cents, currency=currency)

    def approve(self, entry_id: str, *, idempotency_key: str,
                expected_sequence: int, approved_by: str, payer_reference: str | None = None) -> LedgerEvent:
        """Called only by trusted API code after authenticating a human approval.

        `approved_by` must come from the authenticated server-side principal,
        never from an arbitrary request-body field or an AI recommendation.
        """
        return self._store._approve(entry_id, idempotency_key=idempotency_key,
                                     expected_sequence=expected_sequence, approved_by=approved_by,
                                     payer_reference=payer_reference)

    def get(self, entry_id: str) -> LedgerSnapshot:
        return self._store.get(entry_id)

    def list_entries(self) -> tuple[LedgerSnapshot, ...]:
        return self._store.list_entries()

    def verify_integrity(self, checkpoint: IntegrityCheckpoint | None = None) -> IntegrityCheckpoint:
        return self._store.verify_integrity(checkpoint)

    def recovered_cash(self) -> dict[str, int]:
        """Integer cents by currency; no option to include non-verified states."""
        return _verified_recovered_cash(self._store.list_entries())
