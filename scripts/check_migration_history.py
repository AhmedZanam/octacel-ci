#!/usr/bin/env python3
"""Require append-only Supabase migrations and reject empty migration suites."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path


def run(*arguments: str, cwd: Path) -> str:
    result = subprocess.run(arguments, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout


def validate(base_ref: str, migration_dir: Path) -> list[str]:
    errors: list[str] = []
    if not migration_dir.is_dir():
        return [f"migration directory does not exist: {migration_dir}"]

    migrations = sorted(path for path in migration_dir.glob("*.sql") if path.is_file())
    if not migrations:
        return ["at least one real SQL migration is required"]
    timestamps: list[str] = []
    for path in migrations:
        prefix = path.name[:14]
        if len(path.name) < 16 or not prefix.isdigit() or path.name[14] != "_" or not path.name[15:-4]:
            errors.append(f"migration filename must begin YYYYMMDDHHMMSS_: {path}")
        else:
            timestamps.append(prefix)
        if path.stat().st_size == 0:
            errors.append(f"migration must not be empty: {path}")
    for timestamp, count in Counter(timestamps).items():
        if count > 1:
            errors.append(f"migration timestamp must be unique: {timestamp}")

    root = migration_dir.parent.parent.resolve()
    relative_migration_dir = migration_dir.resolve().relative_to(root)
    try:
        base = run("git", "merge-base", "HEAD", base_ref, cwd=root).strip()
        changed = run(
            "git",
            "diff",
            "--name-status",
            "--no-renames",
            "--diff-filter=MD",
            f"{base}...HEAD",
            "--",
            str(relative_migration_dir),
            cwd=root,
        )
    except subprocess.CalledProcessError:
        return [f"cannot compare migration history with {base_ref}; fetch the base branch before CI"]

    for line in changed.splitlines():
        status, relative_path = line.split("\t", maxsplit=1)
        errors.append(f"existing migration is {('modified' if status == 'M' else 'deleted')}: {relative_path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--migration-dir", default="supabase/migrations")
    arguments = parser.parse_args()
    errors = validate(arguments.base_ref, Path(arguments.migration_dir))
    if errors:
        for error in errors:
            print(f"migration compatibility error: {error}", file=sys.stderr)
        return 1
    print("Migration history is append-only and contains SQL migrations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
