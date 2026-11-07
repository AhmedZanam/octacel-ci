#!/usr/bin/env python3
"""Discover a project, collect explicit CI settings, and write its CI contract."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

from scripts.validate_project_config import NODE_REQUIRED_COMMANDS, TERRAFORM_REQUIRED_COMMANDS, validate_project


PROJECT_TYPES = (
    "nextjs",
    "node-backend",
    "typescript-library",
    "browser-extension",
    "containerized-backend",
    "saas",
    "supabase-postgres",
    "terraform-infrastructure",
    "terraform-module",
    "podman-service",
)
NODE_COMMANDS = {
    "format": "format:check",
    "lint": "lint",
    "typecheck": "typecheck",
    "build": "build",
    "unit": "test:unit",
}
COMMAND_LABELS = {
    "format": "Formatting check",
    "lint": "Lint",
    "typecheck": "Type check",
    "build": "Build",
    "unit": "Unit test",
    "integration": "Integration test",
    "migrateTest": "Disposable database migration",
    "schemaCheck": "Database schema check",
    "rlsTests": "Row-level security tests",
    "tenantIsolation": "Organization and tenant isolation tests",
    "terraformFormat": "Terraform format check",
    "terraformValidate": "Terraform validate",
}


def node_manifest(root: Path) -> dict[str, Any]:
    try:
        return json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def discover_project_type(root: Path, package: dict[str, Any]) -> str | None:
    if (root / "supabase/config.toml").is_file() or (root / "supabase/migrations").is_dir():
        return "supabase-postgres"
    dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    if "next" in dependencies:
        return "nextjs"
    if (root / "manifest.json").is_file() or (root / "src/manifest.json").is_file():
        return "browser-extension"
    if package and package.get("main") and package.get("types"):
        return "typescript-library"
    if package:
        return "node-backend"
    if any(root.glob("**/*.tf")):
        return "terraform-infrastructure"
    if (root / "Containerfile").is_file() or (root / "Dockerfile").is_file():
        return "podman-service"
    return None


def detect_node_version(root: Path, package: dict[str, Any]) -> str | None:
    for filename in (".nvmrc", ".node-version"):
        path = root / filename
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip().removeprefix("v")
            if re.fullmatch(r"\d+\.\d+\.\d+", value):
                return value
    value = package.get("engines", {}).get("node")
    if isinstance(value, str) and re.fullmatch(r"v?\d+\.\d+\.\d+", value.strip()):
        return value.strip().removeprefix("v")
    return None


def detect_package_manager(root: Path, package: dict[str, Any]) -> str | None:
    declared = package.get("packageManager")
    if isinstance(declared, str):
        value = declared.split("@", maxsplit=1)[0]
        if value in {"npm", "pnpm", "yarn"}:
            return value
    for lockfile, manager in (("package-lock.json", "npm"), ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn")):
        if (root / lockfile).is_file():
            return manager
    return None


def detect_terraform_version(root: Path) -> str | None:
    for filename in (".terraform-version", ".tfswitchrc"):
        path = root / filename
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip().removeprefix("v")
            if re.fullmatch(r"\d+\.\d+\.\d+", value):
                return value
    return None


def detect_commands(root: Path, project_type: str, package: dict[str, Any], manager: str | None) -> dict[str, list[str] | None]:
    scripts = package.get("scripts", {})
    commands: dict[str, list[str] | None] = {}
    if project_type in {
        "nextjs", "node-backend", "typescript-library", "browser-extension",
        "containerized-backend", "saas", "supabase-postgres",
    }:
        install = {"npm": ["npm", "ci"], "pnpm": ["pnpm", "install", "--frozen-lockfile"], "yarn": ["yarn", "install", "--immutable"]}
        commands["install"] = install.get(manager)
        for key, script in NODE_COMMANDS.items():
            commands[key] = [manager, "run", script] if manager and script in scripts else None
        unit_script = "test:unit" if "test:unit" in scripts else "test" if "test" in scripts else None
        commands["unit"] = [manager, "run", unit_script] if manager and unit_script else None
        integration_script = next((name for name in ("test:integration:ci", "test:integration") if name in scripts), None)
        commands["integration"] = [manager, "run", integration_script] if manager and integration_script else None
        if project_type == "supabase-postgres":
            for key, names in {
                "migrateTest": ("db:migrate:test", "migrate:test"),
                "schemaCheck": ("db:schema:check", "schema:check"),
                "rlsTests": ("test:rls", "db:test:rls"),
                "tenantIsolation": ("test:tenant-isolation", "db:test:tenant-isolation"),
            }.items():
                script_name = next((name for name in names if name in scripts), None)
                commands[key] = [manager, "run", script_name] if manager and script_name else None
    if project_type in {"terraform-infrastructure", "terraform-module"}:
        commands["terraformFormat"] = ["terraform", "fmt", "-check", "-recursive"]
        commands["terraformValidate"] = ["terraform", "validate"]
    return commands


def ask(label: str, detected: str | None = None) -> str:
    hint = f" [{detected}]" if detected else ""
    return input(f"{label}{hint}: ").strip() or (detected or "")


def ask_command(label: str, detected: list[str] | None) -> list[str] | None:
    default = shlex.join(detected) if detected else None
    answer = ask(f"{label} command (blank leaves it incomplete)", default)
    if not answer:
        return None
    try:
        return shlex.split(answer)
    except ValueError as error:
        print(f"Invalid command: {error}", file=sys.stderr)
        return None


def parse_command(value: str | None) -> list[str] | None:
    if value is None or not value.strip():
        return None
    return shlex.split(value)


def initialize(arguments: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    root = Path(arguments.root).resolve()
    package = node_manifest(root)
    detected_type = arguments.project_type or discover_project_type(root, package)
    project_type = detected_type or ""
    if not project_type and sys.stdin.isatty():
        print("Project type:")
        for index, kind in enumerate(PROJECT_TYPES, start=1):
            print(f"  {index}. {kind}")
        selected = ask("Choose a project type by number")
        if selected.isdigit() and 1 <= int(selected) <= len(PROJECT_TYPES):
            project_type = PROJECT_TYPES[int(selected) - 1]
    if project_type not in PROJECT_TYPES:
        raise ValueError("could not detect a supported project type; pass --project-type")

    manager = arguments.package_manager or detect_package_manager(root, package)
    commands = detect_commands(root, project_type, package, manager)
    if project_type in {
        "nextjs", "node-backend", "typescript-library", "browser-extension", "containerized-backend", "saas", "supabase-postgres",
    }:
        for key in NODE_REQUIRED_COMMANDS:
            if arguments.command_overrides.get(key):
                commands[key] = parse_command(arguments.command_overrides[key])
            elif sys.stdin.isatty():
                commands[key] = ask_command(COMMAND_LABELS[key], commands.get(key))
        if arguments.integration_command:
            commands["integration"] = parse_command(arguments.integration_command)
        elif commands.get("integration") is None and sys.stdin.isatty():
            commands["integration"] = ask_command(COMMAND_LABELS["integration"], None)

    if project_type == "supabase-postgres":
        for key in ("migrateTest", "schemaCheck", "rlsTests", "tenantIsolation"):
            if arguments.command_overrides.get(key):
                commands[key] = parse_command(arguments.command_overrides[key])
            elif sys.stdin.isatty():
                commands[key] = ask_command(COMMAND_LABELS[key], commands.get(key))
        database = {
            "kind": "supabase-postgres",
            "migrationsPath": arguments.migrations_path or ("supabase/migrations" if (root / "supabase/migrations").is_dir() else ""),
            "pgTapPath": arguments.pgtap_path or ("supabase/tests/database" if (root / "supabase/tests/database").is_dir() else ""),
            "rlsTestPath": arguments.rls_test_path or ("supabase/tests/rls" if (root / "supabase/tests/rls").is_dir() else ""),
            "tenantIsolationTestPath": arguments.tenant_isolation_path or ("supabase/tests/tenant-isolation" if (root / "supabase/tests/tenant-isolation").is_dir() else ""),
        }
    else:
        database = None

    if project_type in {"terraform-infrastructure", "terraform-module"} and sys.stdin.isatty():
        for key in TERRAFORM_REQUIRED_COMMANDS:
            commands.setdefault(key, ["terraform", "fmt", "-check", "-recursive"] if key == "terraformFormat" else ["terraform", "validate"])

    container_file = next((name for name in ("Containerfile", "Dockerfile") if (root / name).is_file()), None)
    container_enabled = arguments.container if arguments.container is not None else bool(container_file)
    if project_type == "podman-service" or project_type == "containerized-backend":
        container_enabled = True
    architectures = arguments.architecture or ["amd64"]
    image_name = arguments.container_image or f"git.octacel.com/octacel/{arguments.name or root.name}"
    container = {
        "enabled": container_enabled,
        "image": image_name if container_enabled else None,
        "containerfile": arguments.containerfile or container_file if container_enabled else None,
        "architectures": architectures,
    }

    node_version = arguments.node_version or detect_node_version(root, package)
    if project_type in {"terraform-infrastructure", "terraform-module"}:
        terraform_root = arguments.terraform_root or next((str(path.parent) for path in root.glob("**/*.tf") if ".terraform" not in path.parts), "")
        terraform_version = arguments.terraform_version or detect_terraform_version(root) or ""
    else:
        terraform_root = None
        terraform_version = None
    description = arguments.description or ""
    if sys.stdin.isatty():
        project_name = ask("Lowercase project slug", arguments.name or root.name)
        arguments.name = project_name
        description = ask("Project description", description)
        if project_type in {
            "nextjs", "node-backend", "typescript-library", "browser-extension", "containerized-backend", "saas", "supabase-postgres",
        }:
            node_version = ask("Exact Node.js version", node_version)
            manager = ask("Package manager (npm, pnpm, or yarn)", manager)
        if project_type in {"terraform-infrastructure", "terraform-module"}:
            terraform_version = ask("Exact Terraform version", terraform_version)
            terraform_root = ask("Terraform root path", terraform_root)
        if database:
            prompts = {
                "migrationsPath": "Migration directory",
                "pgTapPath": "pgTAP test directory",
                "rlsTestPath": "RLS test directory",
                "tenantIsolationTestPath": "Tenant-isolation test directory",
            }
            for field, label in prompts.items():
                if not database[field]:
                    database[field] = ask(label)
        if arguments.targets is None:
            print("Supported targets: contabo-vps41-development, contabo-vps42-staging, oci-riyadh-amd64, oci-riyadh-arm64")
        if arguments.memory_mib is None:
            arguments.memory_mib = int(ask("Minimum memory MiB"))
        if arguments.cpu_count is None:
            arguments.cpu_count = int(ask("Minimum CPU count"))
        if arguments.storage_gib is None:
            arguments.storage_gib = int(ask("Minimum root storage GiB"))

    targets = arguments.targets or []
    if sys.stdin.isatty() and not targets:
        selected = ask("Deployment target IDs separated by commas")
        targets = [item.strip() for item in selected.split(",") if item.strip()]
    config = {
        "schemaVersion": 1,
        "name": arguments.name or root.name,
        "description": description,
        "projectType": project_type,
        "packageManager": manager if project_type in {
            "nextjs", "node-backend", "typescript-library", "browser-extension", "containerized-backend", "saas", "supabase-postgres",
        } else None,
        "nodeVersion": node_version if project_type in {
            "nextjs", "node-backend", "typescript-library", "browser-extension", "containerized-backend", "saas", "supabase-postgres",
        } else None,
        "terraformVersion": terraform_version,
        "terraformRoot": terraform_root,
        "commands": commands,
        "database": database,
        "container": container,
        "targets": targets,
        "resources": {
            "memoryMiB": arguments.memory_mib,
            "cpuCount": arguments.cpu_count,
            "storageGiB": arguments.storage_gib,
        },
        "secretReferences": [],
    }
    issues = validate_project(config)
    if database:
        for key, field in (("migrationsPath", "migrationsPath"), ("pgTapPath", "pgTapPath"), ("rlsTestPath", "rlsTestPath"), ("tenantIsolationTestPath", "tenantIsolationTestPath")):
            value = database.get(field)
            if not isinstance(value, str) or not value or value.startswith("/") or not (root / value).is_dir():
                issues.append(f"database.{key} must name an existing repository-relative directory")
    return config, issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--name")
    parser.add_argument("--project-type", choices=PROJECT_TYPES)
    parser.add_argument("--description")
    parser.add_argument("--node-version")
    parser.add_argument("--package-manager", choices=("npm", "pnpm", "yarn"))
    parser.add_argument("--terraform-version")
    parser.add_argument("--terraform-root")
    parser.add_argument("--targets", nargs="*")
    parser.add_argument("--memory-mib", type=int)
    parser.add_argument("--cpu-count", type=int)
    parser.add_argument("--storage-gib", type=int)
    parser.add_argument("--container", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--container-image")
    parser.add_argument("--containerfile")
    parser.add_argument("--architecture", action="append")
    parser.add_argument("--migrations-path")
    parser.add_argument("--pgtap-path")
    parser.add_argument("--rls-test-path")
    parser.add_argument("--tenant-isolation-path")
    parser.add_argument("--integration-command")
    parser.add_argument("--command", action="append", default=[], metavar="KEY=COMMAND")
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    arguments.command_overrides = {}
    try:
        for item in arguments.command:
            key, value = item.split("=", maxsplit=1)
            arguments.command_overrides[key] = value
        config, issues = initialize(arguments)
    except (ValueError, OSError) as error:
        print(f"Project initialization failed: {error}", file=sys.stderr)
        return 2

    target = Path(arguments.root).resolve() / ".octacel/project.json"
    if target.exists() and not arguments.force:
        print(f"{target} already exists; pass --force to replace it", file=sys.stderr)
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if issues:
        print(f"Wrote incomplete project configuration to {target}")
        print("Complete the following settings before CI can pass:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"Wrote valid project configuration to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
