import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.init_project import detect_commands, detect_node_version, detect_package_manager, discover_project_type


class InitProjectDiscoveryTests(unittest.TestCase):
    def test_detects_nextjs_and_exact_node_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text(json.dumps({"dependencies": {"next": "15.0.0"}, "scripts": {"test": "vitest run"}}))
            (root / "package-lock.json").write_text("{}")
            (root / ".nvmrc").write_text("v22.14.0\n")
            package = json.loads((root / "package.json").read_text())
            self.assertEqual(discover_project_type(root, package), "nextjs")
            self.assertEqual(detect_node_version(root, package), "22.14.0")
            self.assertEqual(detect_package_manager(root, package), "npm")
            self.assertEqual(detect_commands(root, "nextjs", package, "npm")["unit"], ["npm", "run", "test"])

    def test_detects_supabase_profile_before_generic_node(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "supabase/migrations").mkdir(parents=True)
            self.assertEqual(discover_project_type(root, {"scripts": {}}), "supabase-postgres")


if __name__ == "__main__":
    unittest.main()
