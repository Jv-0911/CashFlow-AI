"""Stable, sanitised errors: never embed caller data or database messages."""


class LedgerError(Exception):
    pass


class InvalidInput(LedgerError):
    pass


class IllegalTransition(LedgerError):
    pass


class IdempotencyConflict(LedgerError):
    pass


class SequenceConflict(LedgerError):
    pass


class EntryNotFound(LedgerError):
    pass


class IntegrityViolation(LedgerError):
    pass


class StorageUnavailable(LedgerError):
    pass
