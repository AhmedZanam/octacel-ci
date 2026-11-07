#!/usr/bin/env python3
"""Validate Semgrep JSON without emitting source paths or code excerpts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def validate_report(value: Any, scan_outcome: str) -> tuple[int, int, list[str]]:
    if not isinstance(value, dict):
        return 0, 0, ["report root must be an object"]

    results = value.get("results")
    errors = value.get("errors")
    if not isinstance(results, list) or not isinstance(errors, list):
        return 0, 0, ["report is missing valid results or errors arrays"]

    blocking = 0
    nonblocking = 0
    failures: list[str] = []
    for finding in results:
        if not isinstance(finding, dict):
            failures.append("report contains a malformed finding")
            continue
        extra = finding.get("extra")
        severity = extra.get("severity") if isinstance(extra, dict) else None
        if severity == "ERROR":
            blocking += 1
        elif severity in {"WARNING", "INFO"}:
            nonblocking += 1
        else:
            failures.append("report contains a finding with unknown severity")

    if errors:
        failures.append(f"scanner reported {len(errors)} internal error(s)")
    if scan_outcome not in {"success", "failure"}:
        failures.append("scanner outcome is missing or invalid")
    elif scan_outcome == "failure" and blocking == 0 and not errors:
        failures.append("scanner failed without a policy finding")

    return blocking, nonblocking, failures


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: validate_semgrep_report.py REPORT.json SCAN_OUTCOME", file=sys.stderr)
        return 2
    try:
        value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Semgrep report is unavailable or invalid; failing closed.", file=sys.stderr)
        return 1

    blocking, nonblocking, failures = validate_report(value, sys.argv[2])
    if blocking:
        print(f"Semgrep policy blocked the change: {blocking} ERROR finding(s).")
    else:
        print(f"Semgrep completed: 0 blocking findings, {nonblocking} nonblocking finding(s).")
    if failures:
        print("Semgrep validation failed closed: " + "; ".join(failures) + ".", file=sys.stderr)
        return 1
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
