#!/usr/bin/env python3
"""Reject missing container build inputs and unsafe build features."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


FORBIDDEN = ("--privileged", "/var/run/docker.sock", "/run/podman/podman.sock")


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"container build file does not exist: {path}"]
    content = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    from_lines = [line for line in lines if line.upper().startswith("FROM ")]
    if not from_lines:
        errors.append("container build file must declare at least one FROM image")
    for line in from_lines:
        if not re.search(r"@sha256:[0-9a-f]{64}(?:\s|$)", line):
            errors.append("every FROM image must be pinned by a SHA-256 digest")
    user_lines = [line.split(maxsplit=1)[1].strip() for line in lines if line.upper().startswith("USER ")]
    if not user_lines or user_lines[-1].lower().split(":", maxsplit=1)[0] in {"root", "0"}:
        errors.append("container build must run the final image as a non-root USER")
    if not any(line.upper().startswith("EXPOSE ") for line in lines):
        errors.append("container build must declare its service port with EXPOSE")
    if not any(line.upper().startswith("HEALTHCHECK ") for line in lines):
        errors.append("container build must declare a HEALTHCHECK")
    if not any(line.upper().startswith("CMD ") or line.upper().startswith("ENTRYPOINT ") for line in lines):
        errors.append("container build must declare CMD or ENTRYPOINT")
    for value in FORBIDDEN:
        if value in content:
            errors.append(f"container build file must not request privileged host access: {value}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("containerfile")
    arguments = parser.parse_args()
    errors = validate(Path(arguments.containerfile))
    if errors:
        for error in errors:
            print(f"Containerfile validation error: {error}", file=sys.stderr)
        return 1
    print("Container build file passes static safety checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
