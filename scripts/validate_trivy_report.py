#!/usr/bin/env python3
"""Enforce Trivy's severity threshold without emitting sensitive report data."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


FINDING_KEYS = ("Vulnerabilities", "Misconfigurations", "Secrets")
BLOCKING_SEVERITIES = {"HIGH", "CRITICAL"}


def validate_report(value: Any, scan_outcome: str) -> tuple[int, list[str]]:
    if not isinstance(value, dict) or not isinstance(value.get("Results"), list):
        return 0, ["report root or Results array is invalid"]

    blocking = 0
    failures: list[str] = []
    for result in value["Results"]:
        if not isinstance(result, dict):
            failures.append("report contains a malformed result")
            continue
        for key in FINDING_KEYS:
            findings = result.get(key) or []
            if not isinstance(findings, list):
                failures.append("report contains a malformed finding list")
                continue
            for finding in findings:
                if not isinstance(finding, dict):
                    failures.append("report contains a malformed finding")
                    continue
                severity = finding.get("Severity")
                if severity in BLOCKING_SEVERITIES:
                    blocking += 1
                elif not isinstance(severity, str) or not severity:
                    failures.append("report contains a finding with unknown severity")

    if scan_outcome not in {"success", "failure"}:
        failures.append("scanner outcome is missing or invalid")
    elif scan_outcome == "failure" and blocking == 0:
        failures.append("scanner failed without a high or critical finding")

    return blocking, failures


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: validate_trivy_report.py REPORT.json SCAN_OUTCOME", file=sys.stderr)
        return 2
    try:
        value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Trivy report is unavailable or invalid; failing closed.", file=sys.stderr)
        return 1

    blocking, failures = validate_report(value, sys.argv[2])
    if blocking:
        print(f"Trivy policy blocked the change: {blocking} HIGH/CRITICAL finding(s).")
    else:
        print("Trivy completed: 0 HIGH/CRITICAL findings.")
    if failures:
        print("Trivy validation failed closed: " + "; ".join(failures) + ".", file=sys.stderr)
        return 1
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
