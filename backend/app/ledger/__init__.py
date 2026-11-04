"""Recovery ledger. Application callers use LedgerService, never the store."""

from .service import LedgerService

__all__ = ["LedgerService"]
