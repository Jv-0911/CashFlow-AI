import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend.tests.payments.sandbox_readiness import (
    IGNORE_PROBES, SEND_APPROVAL, inspect_readiness,
)


class SandboxReadinessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / ".git").mkdir()
        (self.root / ".gitignore").write_text("# Synthetic test only\n")
        self.env = {"PAYPAL_MODE": "sandbox", "PAYPAL_CLIENT_ID": "synthetic-client",
                    "PAYPAL_CLIENT_SECRET": "synthetic-secret", "LEDGER_DB_PATH": "ledger.db",
                    "PAYPAL_SANDBOX_INVOICE_ID": "synthetic-invoice"}
        self.git = patch("backend.tests.payments.sandbox_readiness.subprocess.run",
                         side_effect=self.git_result).start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def git_result(args, **kwargs):
        output = ("\0".join(IGNORE_PROBES) + "\0").encode() if "check-ignore" in args else b""
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr=b"")

    def test_passing_local_checks_do_not_create_ledger_or_expose_values(self):
        before = sorted(p.name for p in self.root.iterdir())
        result = inspect_readiness(self.root, self.env)
        self.assertTrue(result["local_prerequisites_pass"])
        self.assertEqual(before, sorted(p.name for p in self.root.iterdir()))
        rendered = json.dumps(result)
        for sensitive in ("synthetic-client", "synthetic-secret", "synthetic-invoice", str(self.root)):
            self.assertNotIn(sensitive, rendered)
        for call in self.git.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 5)
            self.assertNotIn("shell", call.kwargs)

    def test_missing_repository_does_not_invoke_git(self):
        (self.root / ".git").rmdir()
        result = inspect_readiness(self.root, self.env)
        self.assertFalse(result["local_prerequisites_pass"])
        self.git.assert_not_called()

    def test_missing_ignore_file_blocks(self):
        (self.root / ".gitignore").unlink()
        self.assertFalse(inspect_readiness(self.root, self.env)["local_prerequisites_pass"])
        self.git.assert_not_called()

    def test_partial_ignore_coverage_blocks(self):
        self.git.side_effect = None
        self.git.return_value = subprocess.CompletedProcess([], 0, stdout=b".env\0", stderr=b"")
        self.assertFalse(inspect_readiness(self.root, self.env)["checks"]["ignore_probes_protected"])

    def test_tracked_ignored_file_blocks_without_exposing_name(self):
        def tracked(args, **kwargs):
            if "ls-files" in args:
                return subprocess.CompletedProcess(args, 0, stdout=b"private-name.env\0", stderr=b"")
            return self.git_result(args, **kwargs)
        self.git.side_effect = tracked
        result = inspect_readiness(self.root, self.env)
        self.assertFalse(result["checks"]["no_tracked_ignored_files"])
        self.assertNotIn("private-name", json.dumps(result))

    def test_git_failure_or_timeout_blocks_without_exception_details(self):
        for error in (OSError("sensitive-detail"), subprocess.TimeoutExpired("sensitive-detail", 5)):
            with self.subTest(error=type(error).__name__):
                self.git.side_effect = error
                result = inspect_readiness(self.root, self.env)
                self.assertFalse(result["local_prerequisites_pass"])
                self.assertNotIn("sensitive-detail", json.dumps(result))

    def test_missing_credentials_and_live_mode_or_host_block(self):
        for change in ({"PAYPAL_CLIENT_SECRET": ""}, {"PAYPAL_MODE": "live"},
                       {"PAYPAL_API_HOST": "api-m.paypal.com"}):
            with self.subTest(change=tuple(change)):
                result = inspect_readiness(self.root, self.env | change)
                self.assertFalse(result["checks"]["configuration_valid"])

    def test_missing_parent_or_directory_instead_of_database_blocks(self):
        for path in ("missing/ledger.db", ".git"):
            result = inspect_readiness(self.root, self.env | {"LEDGER_DB_PATH": path})
            self.assertFalse(result["checks"]["ledger_parent_exists"])

    def test_no_selected_integration_test_blocks(self):
        self.env.pop("PAYPAL_SANDBOX_INVOICE_ID")
        self.assertFalse(inspect_readiness(self.root, self.env)["checks"]["at_least_one_test_selected"])

    def test_create_send_requires_exact_ack_and_recipient(self):
        self.env["PAYPAL_SANDBOX_ALLOW_SEND"] = "true"
        result = inspect_readiness(self.root, self.env)
        self.assertFalse(result["selected_tests"]["create_and_send_new_one_cent_invoice"])
        self.env["PAYPAL_SANDBOX_ALLOW_SEND"] = SEND_APPROVAL
        result = inspect_readiness(self.root, self.env)
        self.assertFalse(result["local_prerequisites_pass"])
        self.env["PAYPAL_SANDBOX_PAYER_EMAIL"] = "synthetic-payer@example.test"
        result = inspect_readiness(self.root, self.env)
        self.assertTrue(result["local_prerequisites_pass"])
        self.assertNotIn(self.env["PAYPAL_SANDBOX_PAYER_EMAIL"], json.dumps(result))
