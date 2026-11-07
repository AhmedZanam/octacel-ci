#!/usr/bin/env python3
"""Execute each pgTAP file and reject missing plans or failed assertions."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


PLAN_RE = re.compile(r"^1\.\.(\d+)\s*$", re.MULTILINE)
RESULT_RE = re.compile(r"^(?:ok|not ok)\s+(\d+)(?:\s|$)", re.MULTILINE)


def run_directory(database_url: str, directory: Path) -> list[str]:
    if not database_url:
        return ["TEST_DATABASE_URL is required"]
    if not directory.is_dir():
        return [f"pgTAP test directory does not exist: {directory}"]
    tests = sorted(path for path in directory.glob("*.sql") if path.is_file())
    if not tests:
        return [f"pgTAP test directory contains no SQL tests: {directory}"]
    failures: list[str] = []
    for path in tests:
        result = subprocess.run(
            ["psql", "--no-psqlrc", "--tuples-only", "--no-align", "--set", "ON_ERROR_STOP=1", "--dbname", database_url, "--file", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        if result.returncode:
            failures.append(f"{path}: psql exited {result.returncode}: {result.stderr.strip()}")
            continue
        plans = PLAN_RE.findall(output)
        results = RESULT_RE.findall(output)
        failed = re.findall(r"^not ok\s+\d+.*$", output, re.MULTILINE)
        if failed:
            failures.extend(f"{path}: {line}" for line in failed)
        if len(plans) != 1:
            failures.append(f"{path}: expected exactly one pgTAP plan, found {len(plans)}")
        elif len(results) != int(plans[0]):
            failures.append(f"{path}: planned {plans[0]} assertions but produced {len(results)}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--database-url", default=None)
    arguments = parser.parse_args()
    from os import environ
    database_url = arguments.database_url or environ.get("TEST_DATABASE_URL", "")
    failures = run_directory(database_url, Path(arguments.directory))
    if failures:
        for failure in failures:
            print(f"pgTAP failure: {failure}", file=sys.stderr)
        return 1
    print(f"pgTAP passed for {arguments.directory}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
