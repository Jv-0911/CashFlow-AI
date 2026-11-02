"""Exercise the shipped ignore rules using an isolated temporary Git index."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from backend.tests.payments.sandbox_readiness import inspect_readiness


@unittest.skipUnless(shutil.which("git"), "Git is required to validate ignore behavior")
class GitIgnoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("-c", "init.templateDir=", "init", "-q")
        source = Path(__file__).resolve().parents[3] / ".gitignore"
        (self.root / ".gitignore").write_bytes(source.read_bytes())

    def git(self, *args, data=None):
        result = subprocess.run(
            ["git", "-c", "core.excludesFile=" + os.devnull, "-C", str(self.root), *args],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.env, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, "Temporary Git validation failed")
        return result.stdout

    def ignored(self, paths):
        output = self.git("check-ignore", "--no-index", "-z", "--stdin",
                          data=("\0".join(paths) + "\0").encode())
        return {part.decode() for part in output.split(b"\0") if part}

    def test_private_files_are_ignored_at_root_and_nested_levels(self):
        names = (".env", ".env.local", ".env.production", "data/ledger.backup",
                 "ledger.db", "ledger.db-wal", "ledger.db-shm", "ledger.db-journal",
                 "ledger.db.bak", "ledger.sqlite", "ledger.sqlite3-wal",
                 "private.key", "private.pem", "debug.log", ".venv/config",
                 "__pycache__/module.pyc", "private.postman_environment.json",
                 "private.environment.json")
        paths = [prefix + name for prefix in ("", "backend/app/payments/") for name in names]
        self.assertEqual(self.ignored(paths), set(paths))

    def test_source_contract_and_empty_templates_remain_visible(self):
        visible = [".gitignore", "backend/app/payments/.env.example",
                   "backend/app/payments/paypal_client.py", "backend/tests/payments/test_client.py",
                   "contracts/payment-ledger.example.json", "TEAM_WORKPLAN.md",
                   "backend/app/payments/postman/paypal-sandbox.collection.json",
                   "backend/app/payments/postman/sandbox.empty.environment.json"]
        self.assertEqual(self.ignored([".env", *visible]), {".env"})

    def test_existing_team_build_and_environment_rules_are_preserved(self):
        names = ('node_modules/package/index.js', 'dist/app.js', '.vite/cache',
                 '.venv-win/config', 'build/output', '.idea/workspace.xml',
                 '.vscode/settings.json', '.envrc')
        paths = [prefix + name for prefix in ('', 'frontend/') for name in names]
        # This original slash-containing rule is relative to the repository root.
        paths.append('.streamlit/secrets.toml')
        self.assertEqual(self.ignored(paths), set(paths))

    def test_readiness_detects_an_already_tracked_ignored_file(self):
        (self.root / ".env").write_text("SYNTHETIC_TEST_VALUE=example\n")
        self.git("add", "-f", "--", ".env")
        result = inspect_readiness(self.root, {})
        self.assertTrue(result["checks"]["ignore_probes_protected"])
        self.assertFalse(result["checks"]["no_tracked_ignored_files"])
        self.assertFalse(result["local_prerequisites_pass"])
