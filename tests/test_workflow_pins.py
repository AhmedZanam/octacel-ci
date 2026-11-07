import tempfile
import unittest
from pathlib import Path

from scripts.validate_workflow_pins import validate_file


class WorkflowPinTests(unittest.TestCase):
    def test_accepts_immutable_action_and_image_refs(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workflow.yml"
            path.write_text(
                "steps:\n  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n"
                "container: image: python:3.13@sha256:" + "a" * 64 + "\n"
            )
            self.assertEqual(validate_file(path), [])

    def test_rejects_floating_action_docker_action_and_container(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workflow.yml"
            path.write_text("uses: actions/checkout@main\nuses: docker://alpine:latest\nimage: node:latest\n")
            self.assertEqual(len(validate_file(path)), 3)


if __name__ == "__main__":
    unittest.main()
