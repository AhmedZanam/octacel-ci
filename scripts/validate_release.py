#!/usr/bin/env python3
"""Require semantic release tags and a matching repository version source."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


VERSION_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def validate(ref: str, project_type: str, root: Path = Path(".")) -> list[str]:
    if not ref.startswith("refs/tags/"):
        return []
    tag = ref.removeprefix("refs/tags/")
    match = VERSION_RE.fullmatch(tag)
    if not match:
        return ["release tags must use vMAJOR.MINOR.PATCH"]
    version = ".".join(match.groups())
    candidates: list[str] = []
    for path in (root / "package.json", root / "apps/web/package.json", root / "VERSION", root / ".octacel/release.json"):
        if not path.is_file():
            continue
        try:
            if path.name in {"package.json", "release.json"}:
                value = json.loads(path.read_text(encoding="utf-8")).get("version")
            else:
                value = path.read_text(encoding="utf-8").strip()
        except (OSError, json.JSONDecodeError):
            return [f"cannot read release version from {path}"]
        if isinstance(value, str):
            candidates.append(value.removeprefix("v"))
    if not candidates:
        return [f"{project_type} releases require a version in package.json, VERSION, or .octacel/release.json"]
    distinct_versions = sorted(set(candidates))
    if len(distinct_versions) != 1:
        return [
            "release version sources must agree before tagging; found: "
            + (", ".join(distinct_versions) if distinct_versions else "no version values")
        ]
    if distinct_versions[0] != version:
        return [f"release tag {version} does not match version source(s): {', '.join(candidates)}"]
    return []


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: validate_release.py <ref> <project-type>", file=sys.stderr)
        return 2
    failures = validate(sys.argv[1], sys.argv[2])
    if failures:
        for failure in failures:
            print(f"release validation error: {failure}", file=sys.stderr)
        return 1
    print("Release ref is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
