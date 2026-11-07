import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_migration_history import validate


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


class MigrationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "ci@example.invalid")
        git(self.root, "config", "user.name", "CI Test")
        self.migrations = self.root / "supabase/migrations"
        self.migrations.mkdir(parents=True)
        (self.migrations / "20260101000000_initial.sql").write_text("select 1;\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "initial migration")
        git(self.root, "checkout", "-b", "feature")

    def tearDown(self):
        self.temporary.cleanup()

    def test_accepts_new_append_only_migration(self):
        (self.migrations / "20260102000000_add_table.sql").write_text("create table sample (id int);\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "append migration")
        self.assertEqual(validate("main", self.migrations), [])

    def test_rejects_modification_of_existing_migration(self):
        (self.migrations / "20260101000000_initial.sql").write_text("select 2;\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "rewrite migration")
        self.assertTrue(any("existing migration is modified" in item for item in validate("main", self.migrations)))

    def test_rejects_empty_and_duplicate_migrations(self):
        (self.migrations / "20260102000000_add_table.sql").write_text("")
        (self.migrations / "20260102000000_other.sql").write_text("select 1;\n")
        errors = validate("main", self.migrations)
        self.assertTrue(any("must not be empty" in item for item in errors))
        self.assertTrue(any("timestamp must be unique" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
