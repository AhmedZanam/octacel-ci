#!/usr/bin/env python3
"""Fail the final summary if any applicable CI gate failed or was cancelled."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def validate_results(value: Any, expected: Any) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["workflow results are missing"]
    if not isinstance(expected, list) or not expected or any(not isinstance(name, str) for name in expected):
        return ["expected workflow list is invalid"]
    failures: list[str] = []
    for name in expected:
        item = value.get(name)
        if not isinstance(item, dict):
            failures.append(f"{name}: expected CI job did not report a result")
            continue
        result = item.get("result")
        if result != "success":
            failures.append(f"{name}: {result or 'unknown'}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", help="JSON from the Forgejo needs context")
    parser.add_argument("expected", help="JSON array of required reusable workflow job names")
    arguments = parser.parse_args()
    try:
        results = json.loads(arguments.results)
        expected = json.loads(arguments.expected)
    except json.JSONDecodeError as error:
        print(f"final CI summary cannot parse job results: {error}", file=sys.stderr)
        return 2
    failures = validate_results(results, expected)
    if failures:
        print("CI did not pass all applicable gates:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("CI summary: every applicable validation, test, and security gate passed.")
    print("Release publishing is handled by a downstream protected job.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
