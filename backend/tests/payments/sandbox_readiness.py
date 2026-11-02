"""Read-only local prerequisites; never fetch PayPal or open the ledger."""

import json
import os
from pathlib import Path
import subprocess

from backend.app.payments.config import PaymentConfig
from backend.app.payments.errors import ConfigurationError


SEND_APPROVAL = "I_APPROVE_A_ONE_CENT_SANDBOX_INVOICE"
# Include nested paths because local configuration and SQLite files may live
# below the project root. These are nonexistent probes, never created files.
IGNORE_PROBES = tuple(
    prefix + name
    for prefix in ("", "backend/")
    for name in (".env", "data/readiness-probe", "readiness-probe.db",
                 "readiness-probe.db-wal", "readiness-probe.db-shm",
                 "readiness-probe.db-journal")
)


def _repository_checks(root):
    checks = {"repository_present": (root / ".git").exists(),
              "root_ignore_present": (root / ".gitignore").is_file(),
              "ignore_probes_protected": False,
              "no_tracked_ignored_files": False}
    if not checks["repository_present"] or not checks["root_ignore_present"]:
        return checks

    def git(*args, data=None):
        return subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=5, check=False,
        )

    try:
        ignored = git("check-ignore", "--no-index", "-z", "--stdin",
                      data=("\0".join(IGNORE_PROBES) + "\0").encode("ascii"))
        checks["ignore_probes_protected"] = (
            ignored.returncode == 0
            and set(ignored.stdout.split(b"\0")) - {b""}
            == {path.encode("ascii") for path in IGNORE_PROBES}
        )
        tracked = git("ls-files", "--cached", "--ignored", "--exclude-standard", "-z")
        checks["no_tracked_ignored_files"] = tracked.returncode == 0 and not tracked.stdout
    except (OSError, subprocess.SubprocessError):
        # Never include stderr, command output or exception text in the report.
        pass
    return checks


def inspect_readiness(root, env=None):
    """Return fixed labels/booleans only; no credentials, paths or payer data."""
    source = os.environ if env is None else env
    root = Path(root)
    checks = _repository_checks(root)
    checks.update(configuration_valid=False, ledger_parent_exists=False)
    try:
        config = PaymentConfig.from_env(source)
        checks["configuration_valid"] = True
        db_path = Path(config.db_path)
        if not db_path.is_absolute():
            db_path = root / db_path
        checks["ledger_parent_exists"] = db_path.parent.is_dir() and not db_path.is_dir()
    except (ConfigurationError, OSError, ValueError):
        pass
    selected = {
        "fetch_existing_invoice": bool(source.get("PAYPAL_SANDBOX_INVOICE_ID")),
        "create_and_send_new_one_cent_invoice": source.get("PAYPAL_SANDBOX_ALLOW_SEND") == SEND_APPROVAL,
        "verify_existing_paid_entry": bool(source.get("PAYPAL_SANDBOX_PAID_ENTRY_ID")),
    }
    checks["at_least_one_test_selected"] = any(selected.values())
    checks["send_recipient_present_if_selected"] = (
        not selected["create_and_send_new_one_cent_invoice"]
        or bool(source.get("PAYPAL_SANDBOX_PAYER_EMAIL"))
    )
    return {"local_prerequisites_pass": all(checks.values()), "checks": checks,
            "selected_tests": selected,
            "limits": "No network, ledger writes, credential authentication, permission/persistence validation, or history secret scan performed."}


def main():
    report = inspect_readiness(Path.cwd())
    print(json.dumps(report, indent=2))
    return 0 if report["local_prerequisites_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
