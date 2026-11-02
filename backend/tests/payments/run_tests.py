"""Run all Member 3 tests using only the Python standard library."""
import argparse
from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


@contextmanager
def test_environment(*, sandbox):
    """The default runner cannot inherit a live-network opt-in from the shell."""
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"RUN_PAYPAL_SANDBOX_TESTS": "1" if sandbox else "0"}))
        if not sandbox:
            for target in ("socket.create_connection", "socket.getaddrinfo",
                           "socket.socket.connect", "socket.socket.connect_ex"):
                stack.enter_context(patch(target, side_effect=AssertionError("Network is disabled in the offline test suite")))
        yield


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", action="store_true", help="Opt into credentialed Sandbox tests; sending requires a separate approval flag.")
    args = parser.parse_args()
    with test_environment(sandbox=args.sandbox):
        base = Path(__file__).resolve().parents[1]
        suites = []
        for directory in ("ledger", "payments"):
            # Separate loaders support namespace directories without editing
            # shared package files owned by other members.
            suites.append(unittest.TestLoader().discover(str(base / directory), pattern="test_*.py"))
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
