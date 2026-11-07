#!/usr/bin/env python3
"""Validate the explicit per-repository octaCEL CI contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


NODE_TYPES = {
    "nextjs",
    "node-backend",
    "typescript-library",
    "browser-extension",
    "containerized-backend",
    "saas",
    "supabase-postgres",
}
TERRAFORM_TYPES = {"terraform-infrastructure", "terraform-module"}
PROJECT_TYPES = NODE_TYPES | TERRAFORM_TYPES | {"podman-service"}
NODE_REQUIRED_COMMANDS = ("install", "format", "lint", "typecheck", "build", "unit")
TERRAFORM_REQUIRED_COMMANDS = ("terraformFormat", "terraformValidate")
SUPABASE_REQUIRED_COMMANDS = ("migrateTest", "schemaCheck", "rlsTests", "tenantIsolation", "integration")
VALID_PACKAGE_MANAGERS = {"npm", "pnpm", "yarn"}
VALID_ARCHITECTURES = {"amd64", "arm64"}
VALID_TARGETS = {
    "contabo-vps41-development",
    "contabo-vps42-staging",
    "oci-riyadh-amd64",
    "oci-riyadh-arm64",
}
VALID_ENVIRONMENTS = {"ci", "development", "staging", "production"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NODE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
IMAGE_RE = re.compile(r"^git\.octacel\.com/octacel/[a-z0-9]+(?:-[a-z0-9]+)*$")


def _is_command(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _is_repository_path(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not value.startswith("/")
        and re.fullmatch(r"[A-Za-z0-9._/-]+", value) is not None
        and ".." not in Path(value).parts
    )


def validate_project(config: Any) -> list[str]:
    """Return all contract violations without mutating ``config``."""
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["configuration root must be an object"]

    if config.get("schemaVersion") != 1:
        errors.append("schemaVersion must equal 1")

    name = config.get("name")
    if not isinstance(name, str) or not SLUG_RE.fullmatch(name):
        errors.append("name must be a lowercase kebab-case project slug")

    description = config.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description must be a non-empty string")

    project_type = config.get("projectType")
    if not isinstance(project_type, str) or project_type not in PROJECT_TYPES:
        errors.append("projectType must be one of: " + ", ".join(sorted(PROJECT_TYPES)))

    commands = config.get("commands")
    if not isinstance(commands, dict):
        errors.append("commands must be an object of argument arrays")
        commands = {}

    if isinstance(project_type, str) and project_type in NODE_TYPES:
        package_manager = config.get("packageManager")
        if not isinstance(package_manager, str) or package_manager not in VALID_PACKAGE_MANAGERS:
            errors.append("packageManager must be npm, pnpm, or yarn for this project type")
        node_version = config.get("nodeVersion")
        if not isinstance(node_version, str) or not NODE_VERSION_RE.fullmatch(node_version):
            errors.append("nodeVersion must be an exact numeric version such as 22.14.0")
        for command_name in NODE_REQUIRED_COMMANDS:
            if not _is_command(commands.get(command_name)):
                errors.append(
                    f"commands.{command_name} must be a non-empty argument array for this project type"
                )
        if commands.get("integration") is not None and not _is_command(commands.get("integration")):
            errors.append("commands.integration must be null or a non-empty argument array")

    if isinstance(project_type, str) and project_type in TERRAFORM_TYPES:
        terraform_version = config.get("terraformVersion")
        if not isinstance(terraform_version, str) or not NODE_VERSION_RE.fullmatch(terraform_version):
            errors.append("terraformVersion must be an exact numeric version")
        terraform_root = config.get("terraformRoot")
        if not _is_repository_path(terraform_root):
            errors.append("terraformRoot must be a non-empty repository-relative path")
        for command_name in TERRAFORM_REQUIRED_COMMANDS:
            if not _is_command(commands.get(command_name)):
                errors.append(
                    f"commands.{command_name} must be a non-empty argument array for this project type"
                )

    if project_type == "supabase-postgres":
        database = config.get("database")
        if not isinstance(database, dict) or database.get("kind") != "supabase-postgres":
            errors.append("database.kind must equal supabase-postgres for this project type")
        else:
            for field in ("migrationsPath", "pgTapPath", "rlsTestPath", "tenantIsolationTestPath"):
                value = database.get(field)
                if not _is_repository_path(value):
                    errors.append(f"database.{field} must be a repository-relative path")
        for command_name in SUPABASE_REQUIRED_COMMANDS:
            if not _is_command(commands.get(command_name)):
                errors.append(
                    f"commands.{command_name} must be a non-empty argument array for this project type"
                )
    elif config.get("database") is not None:
        errors.append("database must be null unless projectType is supabase-postgres")

    container = config.get("container")
    if not isinstance(container, dict) or not isinstance(container.get("enabled"), bool):
        errors.append("container.enabled must be an explicit boolean")
    else:
        if isinstance(project_type, str) and project_type in {"containerized-backend", "podman-service"} and not container["enabled"]:
            errors.append(f"container.enabled must be true for {project_type}")
        if container["enabled"]:
            image = container.get("image")
            if not isinstance(image, str) or not IMAGE_RE.fullmatch(image):
                errors.append("container.image must use git.octacel.com/octacel/<repository>")
            containerfile = container.get("containerfile")
            if not _is_repository_path(containerfile):
                errors.append("container.containerfile must be a repository-relative path")
        architectures = container.get("architectures")
        if not isinstance(architectures, list) or not architectures or any(
            not isinstance(architecture, str) or architecture not in VALID_ARCHITECTURES
            for architecture in architectures
        ):
            errors.append("container.architectures must contain amd64 and/or arm64")

    targets = config.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must contain at least one supported deployment target")
    else:
        for index, target in enumerate(targets):
            if not isinstance(target, str) or target not in VALID_TARGETS:
                errors.append(f"targets[{index}] is not a supported target")

    resources = config.get("resources")
    if not isinstance(resources, dict):
        errors.append("resources must be an object")
    else:
        for field in ("memoryMiB", "cpuCount", "storageGiB"):
            value = resources.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"resources.{field} must be a positive integer")

    secret_refs = config.get("secretReferences", [])
    if not isinstance(secret_refs, list):
        errors.append("secretReferences must be an array of references, never secret values")
    else:
        for index, reference in enumerate(secret_refs):
            prefix = f"secretReferences[{index}]"
            if not isinstance(reference, dict):
                errors.append(f"{prefix} must be an object")
                continue
            environment = reference.get("environment")
            if not isinstance(environment, str) or environment not in VALID_ENVIRONMENTS:
                errors.append(f"{prefix}.environment must be development, staging, or production")
            path = reference.get("path")
            if not isinstance(path, str) or not path.startswith("kv/") or "#" not in path:
                errors.append(f"{prefix}.path must be an OpenBao path and key reference (path#key)")
            rotation = reference.get("rotation")
            if not isinstance(rotation, dict) or not all(
                isinstance(rotation.get(field), str) and rotation[field].strip()
                for field in ("owner", "reviewAfter")
            ):
                errors.append(f"{prefix}.rotation must specify owner and reviewAfter")

    return errors


def validate_project_paths(config: Any, root: Path) -> list[str]:
    """Require declared database directories and SQL suites to exist in the checkout."""
    if not isinstance(config, dict):
        return []
    errors: list[str] = []
    root = root.resolve()

    def resolve_repository_path(value: Any) -> Path | None:
        if not _is_repository_path(value):
            return None
        resolved = (root / value).resolve()
        if not resolved.is_relative_to(root):
            return None
        return resolved

    if config.get("projectType") == "supabase-postgres":
        database = config.get("database")
        if isinstance(database, dict):
            for field in ("migrationsPath", "pgTapPath", "rlsTestPath", "tenantIsolationTestPath"):
                value = database.get(field)
                path = resolve_repository_path(value)
                if path is None:
                    if _is_repository_path(value):
                        errors.append(f"database.{field} must resolve inside the repository")
                    continue
                if not path.is_dir():
                    errors.append(f"database.{field} must name an existing directory")
                    continue
                candidates = list(path.glob("*.sql"))
                if not any(item.is_file() and item.stat().st_size > 0 for item in candidates):
                    errors.append(f"database.{field} must contain at least one non-empty SQL file")
    container = config.get("container")
    if isinstance(container, dict) and container.get("enabled") is True:
        value = container.get("containerfile")
        path = resolve_repository_path(value)
        if path is None:
            if _is_repository_path(value):
                errors.append("container.containerfile must resolve inside the repository")
        elif not path.is_file():
            errors.append("container.containerfile must name an existing file")
    return errors


def validate_schema(config: Any, schema_path: Path) -> list[str]:
    """Validate the JSON shape and date formats using the published draft 2020-12 schema."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is required for project schema validation"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"project JSON schema could not be read: {error}"]
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    return [
        f"JSON schema: {'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(config), key=lambda item: tuple(map(str, item.absolute_path)))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", default=".octacel/project.json")
    parser.add_argument("--schema", help="validate the contract against a JSON Schema 2020-12 document")
    parser.add_argument("--output", help="append validated project metadata to a Forgejo output file")
    arguments = parser.parse_args()
    path = Path(arguments.config)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"configuration could not be read: {error}", file=sys.stderr)
        return 2

    errors = validate_project(config)
    if arguments.schema:
        errors.extend(validate_schema(config, Path(arguments.schema)))
    root = path.parent.parent if path.parent.name == ".octacel" else path.parent
    errors.extend(validate_project_paths(config, root))
    if errors:
        print("Project CI configuration is incomplete or invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if arguments.output:
        expected_workflows = ["project", "security", "machine"]
        if config["projectType"] in NODE_TYPES:
            expected_workflows.append("node_quality")
        if config["projectType"] in TERRAFORM_TYPES:
            expected_workflows.append("terraform")
        expected_workflows.append("release")
        if config["projectType"] == "supabase-postgres":
            expected_workflows.append("postgres")
        if config["projectType"] in TERRAFORM_TYPES:
            expected_workflows.append("iac")
        if config["container"]["enabled"]:
            expected_workflows.append("container_build")
        if config["projectType"] == "terraform-infrastructure" or config["container"]["enabled"]:
            expected_workflows.append("systemd")
        values = {
            "project_type": config["projectType"],
            "node_version": config.get("nodeVersion", ""),
            "terraform_version": config.get("terraformVersion", ""),
            "terraform_root": config.get("terraformRoot", ""),
            "container_enabled": str(config.get("container", {}).get("enabled", False)).lower(),
            "integration_enabled": str(
                config["projectType"] != "supabase-postgres" and config["commands"].get("integration") is not None
            ).lower(),
            "targets_json": json.dumps(config["targets"], separators=(",", ":")),
            "expected_workflows_json": json.dumps(expected_workflows, separators=(",", ":")),
        }
        with Path(arguments.output).open("a", encoding="utf-8") as output:
            for key, value in values.items():
                output.write(f"{key}={value}\n")
    print("Project CI configuration is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
