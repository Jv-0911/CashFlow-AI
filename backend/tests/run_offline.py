"""Full repository suite with network calls and inherited Sandbox opt-in blocked."""
import os
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from backend.tests.payments.run_tests import test_environment


def main():
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    safe_env = {'RUN_PAYPAL_SANDBOX_TESTS': '0', 'CASHFLOW_PAYPAL_ENABLED': 'false',
                'CASHFLOW_AI_ENABLED': 'false', 'CASHFLOW_ADMIN_PASSWORD': '',
                'CASHFLOW_PUBLIC_ORIGIN': 'http://127.0.0.1:8000', 'PAYPAL_MODE': 'sandbox'}
    with test_environment(sandbox=False), patch.dict(os.environ, safe_env):
        return pytest.main(['backend/tests', '--import-mode=importlib', '-p', 'no:cacheprovider', '-q', *sys.argv[1:]])


if __name__ == '__main__':
    raise SystemExit(main())
