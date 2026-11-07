import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_release import validate


class ReleaseValidationTests(unittest.TestCase):
    def test_branch_ref_is_not_a_release(self):
        self.assertEqual(validate("refs/heads/feature", "nextjs"), [])

    def test_requires_semver_and_matching_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text(json.dumps({"version": "1.2.3"}))
            self.assertEqual(validate("refs/tags/v1.2.3", "nextjs", root), [])
            self.assertTrue(validate("refs/tags/v1.2", "nextjs", root))
            self.assertTrue(validate("refs/tags/v1.2.4", "nextjs", root))

    def test_rejects_conflicting_version_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text(json.dumps({"version": "1.2.3"}))
            (root / "VERSION").write_text("1.2.4\n")
            errors = validate("refs/tags/v1.2.3", "nextjs", root)
            self.assertIn("release version sources must agree before tagging; found: 1.2.3, 1.2.4", errors)


if __name__ == "__main__":
    unittest.main()
