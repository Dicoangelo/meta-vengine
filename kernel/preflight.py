#!/usr/bin/env python3
"""
US-201: Activation Gate & Preflight Check

Validates all prerequisites before enabling banditEnabled: true.
Runs from project root: python3 kernel/preflight.py

- JSON report on stdout (machine-parseable)
- Human summary on stderr
- Exit 0 = all pass, 1 = failures
- Idempotent — safe to run multiple times
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

REQUIRED_DATA_DIRS = [
    "data",
    "data/weight-snapshots",
    "data/lrf-reports",
    "data/bo-reports",
    "data/rollback-reports",
    "data/ab-reports",
    "data/daemon-logs",
]

REQUIRED_CONFIGS = [
    "config/graph-signal-weights.json",
    "config/supermax-v2.json",
]

LEARNABLE_PARAMS_PATH = "config/learnable-params.json"
TEST_PATH = "kernel/tests/test_learning_loop.py"
PREFLIGHT_LOG_PATH = "data/preflight-log.jsonl"


def check_test_suite() -> dict:
    """Run test_learning_loop.py via pytest and capture result."""
    t0 = time.monotonic()
    test_file = PROJECT_ROOT / TEST_PATH
    if not test_file.exists():
        return {
            "name": "test_suite",
            "passed": False,
            "detail": f"Test file not found: {TEST_PATH}",
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short", "-q"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        passed = result.returncode == 0
        detail = "all tests passed" if passed else result.stdout[-500:] + result.stderr[-500:]
        return {
            "name": "test_suite",
            "passed": passed,
            "detail": detail.strip(),
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except subprocess.TimeoutExpired:
        return {
            "name": "test_suite",
            "passed": False,
            "detail": "pytest timed out after 60s",
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except Exception as e:
        return {
            "name": "test_suite",
            "passed": False,
            "detail": str(e),
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }


def check_data_dirs() -> list[dict]:
    """Check all required data dirs exist and are writable. Create missing ones."""
    results = []
    for rel in REQUIRED_DATA_DIRS:
        t0 = time.monotonic()
        full = PROJECT_ROOT / rel
        created = False
        if not full.exists():
            try:
                full.mkdir(parents=True, exist_ok=True)
                created = True
            except OSError as e:
                results.append({
                    "name": f"dir:{rel}",
                    "passed": False,
                    "detail": f"mkdir failed: {e}",
                    "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
                })
                continue

        # Check writable
        writable = os.access(str(full), os.W_OK)
        detail = "exists, writable"
        if created:
            detail = "created, writable" if writable else "created, NOT writable"
        elif not writable:
            detail = "exists, NOT writable"

        results.append({
            "name": f"dir:{rel}",
            "passed": writable,
            "detail": detail,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        })
    return results


def check_learnable_params() -> dict:
    """Load and validate learnable-params.json."""
    t0 = time.monotonic()
    path = PROJECT_ROOT / LEARNABLE_PARAMS_PATH
    if not path.exists():
        return {
            "name": "learnable_params",
            "passed": False,
            "detail": f"File not found: {LEARNABLE_PARAMS_PATH}",
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    try:
        data = json.loads(path.read_text())
        param_count = len(data.get("parameters", []))
        group_count = len(data.get("groups", {}))
        return {
            "name": "learnable_params",
            "passed": True,
            "detail": f"valid JSON, {param_count} params, {group_count} groups",
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except json.JSONDecodeError as e:
        return {
            "name": "learnable_params",
            "passed": False,
            "detail": f"JSON parse error: {e}",
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }


def check_config_files() -> list[dict]:
    """Check required config files exist."""
    results = []
    for rel in REQUIRED_CONFIGS:
        t0 = time.monotonic()
        full = PROJECT_ROOT / rel
        exists = full.exists()
        results.append({
            "name": f"config:{rel}",
            "passed": exists,
            "detail": "exists" if exists else "MISSING",
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        })
    return results


def activate_bandit(config_path: Path) -> None:
    """Set banditEnabled: true in learnable-params.json."""
    data = json.loads(config_path.read_text())
    if data.get("banditEnabled") is True:
        return  # already enabled, idempotent
    data["banditEnabled"] = True
    config_path.write_text(json.dumps(data, indent=2) + "\n")


def append_log(report: dict) -> None:
    """Append preflight result to data/preflight-log.jsonl."""
    log_path = PROJECT_ROOT / PREFLIGHT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "all_passed": report["all_passed"],
        "check_count": len(report["checks"]),
        "failed_count": report["failed_count"],
        "total_elapsed_ms": report["total_elapsed_ms"],
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run_preflight() -> dict:
    """Execute all preflight checks and return structured report."""
    t0 = time.monotonic()
    checks: list[dict] = []

    # 1. Data dirs (create missing ones first so tests can use them)
    checks.extend(check_data_dirs())

    # 2. Config files
    checks.extend(check_config_files())

    # 3. Learnable params parse
    checks.append(check_learnable_params())

    # 4. Test suite (most expensive, run last)
    checks.append(check_test_suite())

    total_ms = round((time.monotonic() - t0) * 1000, 1)
    failed = [c for c in checks if not c["passed"]]

    report = {
        "preflight": "meta-vengine",
        "timestamp": datetime.now().isoformat(),
        "all_passed": len(failed) == 0,
        "check_count": len(checks),
        "failed_count": len(failed),
        "total_elapsed_ms": total_ms,
        "checks": checks,
    }
    return report


def main() -> int:
    report = run_preflight()

    # Log to JSONL
    append_log(report)

    # Machine-readable JSON to stdout
    print(json.dumps(report, indent=2))

    # Human summary to stderr
    failed = [c for c in report["checks"] if not c["passed"]]
    if report["all_passed"]:
        print(
            f"\n[PREFLIGHT] ALL {report['check_count']} CHECKS PASSED "
            f"({report['total_elapsed_ms']}ms)",
            file=sys.stderr,
        )
        # Activate bandit
        config_path = PROJECT_ROOT / LEARNABLE_PARAMS_PATH
        activate_bandit(config_path)
        print("[PREFLIGHT] banditEnabled set to true", file=sys.stderr)
        return 0
    else:
        print(
            f"\n[PREFLIGHT] FAILED — {report['failed_count']}/{report['check_count']} "
            f"checks failed ({report['total_elapsed_ms']}ms)",
            file=sys.stderr,
        )
        for c in failed:
            print(f"  FAIL: {c['name']} — {c['detail']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
