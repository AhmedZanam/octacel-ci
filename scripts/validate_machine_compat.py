#!/usr/bin/env python3
"""Compare declared project requirements with the versioned target profiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def validate(project: Any, profiles: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(project, dict) or not isinstance(profiles, dict):
        return ["project and target profile documents must be JSON objects"]
    targets = profiles.get("targets")
    requirements = project.get("resources")
    if not isinstance(targets, dict) or not isinstance(requirements, dict):
        return ["target profiles and project.resources are required"]

    selected_targets = project.get("targets")
    if not isinstance(selected_targets, list) or not selected_targets:
        return ["project.targets must be a non-empty array"]
    container = project.get("container")
    architectures = container.get("architectures", []) if isinstance(container, dict) else []
    if not isinstance(architectures, list):
        return ["container.architectures must be an array"]

    for target_id in selected_targets:
        target = targets.get(target_id)
        if not isinstance(target, dict):
            errors.append(f"unknown target profile: {target_id}")
            continue
        architectures = project.get("container", {}).get("architectures", [])
        if target.get("architecture") not in architectures:
            errors.append(
                f"{target_id} architecture {target.get('architecture')} is not in container.architectures"
            )
        if target.get("status") != "measured-live" or not isinstance(target.get("capacity"), dict):
            errors.append(f"{target_id} has no verified capacity; runtime compatibility is not claimed")
            continue
        capacity = target["capacity"]
        capacity_fields = ("cpuCount", "memoryMiB", "rootStorageGiB")
        if any(
            not isinstance(capacity.get(field), int)
            or isinstance(capacity.get(field), bool)
            or capacity[field] <= 0
            for field in capacity_fields
        ):
            errors.append(f"{target_id} has incomplete or invalid measured capacity")
            continue
        resource_fields = {"cpuCount": "cpuCount", "memoryMiB": "memoryMiB", "rootStorageGiB": "storageGiB"}
        if any(
            not isinstance(requirements.get(project_field), int)
            or isinstance(requirements.get(project_field), bool)
            or requirements[project_field] <= 0
            for project_field in resource_fields.values()
        ):
            errors.append("project.resources must contain positive integer CPU, memory, and storage values")
            continue
        if requirements["cpuCount"] > capacity["cpuCount"]:
            errors.append(f"{target_id} provides {capacity['cpuCount']} CPUs, below requested {requirements['cpuCount']}")
        if requirements["memoryMiB"] > capacity["memoryMiB"]:
            errors.append(
                f"{target_id} provides {capacity['memoryMiB']} MiB, below requested {requirements['memoryMiB']} MiB"
            )
        if requirements["storageGiB"] > capacity["rootStorageGiB"]:
            errors.append(
                f"{target_id} provides {capacity['rootStorageGiB']} GiB root storage, below requested {requirements['storageGiB']} GiB"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".octacel/project.json")
    parser.add_argument("--profiles", default=".octacel-ci/profiles/targets.json")
    arguments = parser.parse_args()
    try:
        project = json.loads(Path(arguments.project).read_text(encoding="utf-8"))
        profiles = json.loads(Path(arguments.profiles).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"machine compatibility inputs could not be read: {error}", file=sys.stderr)
        return 2

    errors = validate(project, profiles)
    if errors:
        for error in errors:
            print(f"machine compatibility error: {error}", file=sys.stderr)
        return 1
    print("Static machine compatibility checks passed for the selected measured targets.")
    print("This result does not replace runtime startup, health, filesystem, port, or architecture tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
