import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_project_config import validate_project, validate_project_paths, validate_schema


def node_project():
    return {
        "schemaVersion": 1,
        "name": "sample-web",
        "description": "Sample app",
        "projectType": "nextjs",
        "packageManager": "npm",
        "nodeVersion": "22.14.0",
        "commands": {
            "install": ["npm", "ci"],
            "format": ["npm", "run", "format:check"],
            "lint": ["npm", "run", "lint"],
            "typecheck": ["npm", "run", "typecheck"],
            "build": ["npm", "run", "build"],
            "unit": ["npm", "run", "test:unit"],
            "integration": None,
        },
        "database": None,
        "container": {"enabled": False, "image": None, "containerfile": None, "architectures": ["amd64"]},
        "targets": ["contabo-vps41-development"],
        "resources": {"memoryMiB": 1024, "cpuCount": 1, "storageGiB": 4},
    }


class ValidateProjectTests(unittest.TestCase):
    def test_accepts_complete_node_project(self):
        self.assertEqual(validate_project(node_project()), [])

    def test_rejects_unknown_project_type(self):
        config = node_project()
        config["projectType"] = "surprise"
        self.assertIn("projectType must be one of", " ".join(validate_project(config)))

    def test_rejects_malformed_unhashable_profile_values_without_traceback(self):
        config = node_project()
        config["projectType"] = ["nextjs"]
        config["packageManager"] = []
        config["targets"] = [{}]
        config["container"]["architectures"] = [{}]
        self.assertTrue(validate_project(config))

    def test_requires_real_node_quality_commands(self):
        config = node_project()
        config["commands"]["unit"] = None
        errors = validate_project(config)
        self.assertIn("commands.unit must be a non-empty argument array for this project type", errors)

    def test_supabase_profile_requires_migrations_and_pgtap_tests(self):
        config = node_project()
        config.update(
            projectType="supabase-postgres",
            database={
                "kind": "supabase-postgres",
                "migrationsPath": "supabase/migrations",
                "pgTapPath": "supabase/tests/database",
                "rlsTestPath": "supabase/tests/rls",
                "tenantIsolationTestPath": "supabase/tests/tenant-isolation",
            },
        )
        config["commands"]["integration"] = None
        self.assertIn("commands.integration must be a non-empty argument array for this project type", validate_project(config))

    def test_supabase_profile_requires_real_rls_and_isolation_commands(self):
        config = node_project()
        config.update(
            projectType="supabase-postgres",
            database={
                "kind": "supabase-postgres",
                "migrationsPath": "supabase/migrations",
                "pgTapPath": "supabase/tests/database",
                "rlsTestPath": "supabase/tests/rls",
                "tenantIsolationTestPath": "supabase/tests/tenant-isolation",
            },
        )
        errors = validate_project(config)
        self.assertIn("commands.migrateTest must be a non-empty argument array for this project type", errors)
        self.assertIn("commands.schemaCheck must be a non-empty argument array for this project type", errors)
        self.assertIn("commands.rlsTests must be a non-empty argument array for this project type", errors)
        self.assertIn("commands.tenantIsolation must be a non-empty argument array for this project type", errors)

    def test_rejects_container_images_outside_forgejo_registry(self):
        config = node_project()
        config["container"] = {"enabled": True, "image": "docker.io/acme/sample-web", "architectures": ["amd64"]}
        self.assertIn("container.image must use git.octacel.com/octacel/<repository>", validate_project(config))

    def test_rejects_invalid_resource_and_target_values(self):
        config = node_project()
        config["resources"]["cpuCount"] = 0
        config["targets"] = ["unknown-host"]
        errors = validate_project(config)
        self.assertTrue(any(error.startswith("resources.cpuCount") for error in errors))
        self.assertTrue(any(error.startswith("targets[0]") for error in errors))

    def test_shared_infrastructure_runner_host_is_not_a_project_target(self):
        config = node_project()
        config["targets"] = ["contabo-vps61-shared-infra"]
        self.assertIn("targets[0] is not a supported target", validate_project(config))

    def test_does_not_mutate_input(self):
        config = node_project()
        before = copy.deepcopy(config)
        validate_project(config)
        self.assertEqual(config, before)

    def test_accepts_ci_secret_reference_without_a_secret_value(self):
        config = node_project()
        config["secretReferences"] = [{
            "environment": "ci",
            "path": "kv/octacel/ci#NPM_READ_TOKEN",
            "rotation": {"owner": "platform-team", "reviewAfter": "2027-02-01"},
        }]
        self.assertEqual(validate_project(config), [])

    def test_database_and_container_paths_cannot_escape_repository_through_symlink(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            root = Path(temporary)
            (root / "outside").symlink_to(outside, target_is_directory=True)
            config = node_project()
            config.update(projectType="supabase-postgres", database={
                "kind": "supabase-postgres",
                "migrationsPath": "outside",
                "pgTapPath": "outside",
                "rlsTestPath": "outside",
                "tenantIsolationTestPath": "outside",
            })
            config["commands"].update({
                "migrateTest": ["npm", "run", "migrate"],
                "schemaCheck": ["npm", "run", "schema"],
                "rlsTests": ["npm", "run", "rls"],
                "tenantIsolation": ["npm", "run", "tenant"],
            })
            self.assertTrue(any("must resolve inside the repository" in item for item in validate_project_paths(config, root)))

    def test_schema_can_be_parsed_after_profile_updates(self):
        schema = Path(__file__).parents[1] / ".octacel/project.schema.json"
        schema_value = json.loads(schema.read_text(encoding="utf-8"))
        self.assertIsInstance(schema_value, dict)
        self.assertEqual(validate_schema(node_project(), schema), [])

    def test_schema_rejects_invalid_secret_review_date(self):
        config = node_project()
        config["secretReferences"] = [{
            "environment": "ci",
            "path": "kv/octacel/ci#NPM_READ_TOKEN",
            "rotation": {"owner": "platform-team", "reviewAfter": "not-a-date"},
        }]
        schema = Path(__file__).parents[1] / ".octacel/project.schema.json"
        self.assertTrue(any("reviewAfter" in issue for issue in validate_schema(config, schema)))


if __name__ == "__main__":
    unittest.main()
