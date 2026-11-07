#!/usr/bin/env python3
"""Reject floating actions and workflow container references."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


USES_RE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
IMAGE_RE = re.compile(r"^\s*image:\s*([^\s#]+)", re.MULTILINE)
ACTION_SHA_RE = re.compile(r"@[0-9a-fA-F]{40}$")
IMAGE_SHA_RE = re.compile(r"@sha256:[0-9a-fA-F]{64}$")


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    content = path.read_text(encoding="utf-8")
    for value in USES_RE.findall(content):
        if value.startswith("./"):
            continue
        if value.startswith("docker://"):
            if not IMAGE_SHA_RE.search(value):
                errors.append(f"Docker action is not digest-pinned: {value}")
        elif not ACTION_SHA_RE.search(value):
            errors.append(f"Action or reusable workflow is not commit-pinned: {value}")
    for value in IMAGE_RE.findall(content):
        if not IMAGE_SHA_RE.search(value):
            errors.append(f"Workflow image is not digest-pinned: {value}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".forgejo/workflows")
    arguments = parser.parse_args()
    root = Path(arguments.root)
    files = sorted([*root.rglob("*.yml"), *root.rglob("*.yaml")])
    errors = [f"{path}: {error}" for path in files for error in validate_file(path)]
    if errors:
        for error in errors:
            print(f"workflow pin error: {error}", file=sys.stderr)
        return 1
    print(f"All external actions and workflow images are pinned in {len(files)} workflow files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
