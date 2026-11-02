import os
import socket
import unittest
from unittest.mock import patch

from backend.tests.payments.run_tests import test_environment as guarded_environment


class OfflineRunnerTests(unittest.TestCase):
    def test_default_disables_inherited_sandbox_opt_in_and_network(self):
        with patch.dict(os.environ, {"RUN_PAYPAL_SANDBOX_TESTS": "1"}):
            with guarded_environment(sandbox=False):
                self.assertEqual(os.environ["RUN_PAYPAL_SANDBOX_TESTS"], "0")
                for operation in (lambda: socket.getaddrinfo("example.test", 443),
                                  lambda: socket.create_connection(("example.test", 443))):
                    with self.assertRaisesRegex(AssertionError, "Network is disabled"):
                        operation()
                with socket.socket() as sock:
                    with self.assertRaises(AssertionError):
                        sock.connect(("127.0.0.1", 443))
                    with self.assertRaises(AssertionError):
                        sock.connect_ex(("127.0.0.1", 443))
            self.assertEqual(os.environ["RUN_PAYPAL_SANDBOX_TESTS"], "1")

    def test_explicit_sandbox_flag_sets_opt_in_without_calling_network(self):
        with patch.dict(os.environ, {"RUN_PAYPAL_SANDBOX_TESTS": "0"}):
            with guarded_environment(sandbox=True):
                self.assertEqual(os.environ["RUN_PAYPAL_SANDBOX_TESTS"], "1")
            self.assertEqual(os.environ["RUN_PAYPAL_SANDBOX_TESTS"], "0")
