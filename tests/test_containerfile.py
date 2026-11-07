import tempfile
import unittest
from pathlib import Path

from scripts.validate_containerfile import validate


class ContainerfileTests(unittest.TestCase):
    def test_requires_base_image_and_rejects_host_socket(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Containerfile"
            path.write_text(
                "FROM alpine@sha256:" + "a" * 64 + "\nUSER nobody\nEXPOSE 8080\n"
                "HEALTHCHECK CMD true\nCMD [\"app\"]\nRUN echo /var/run/docker.sock\n"
            )
            self.assertTrue(any("host access" in error for error in validate(path)))
            path.write_text("RUN echo no-base-image\n")
            self.assertIn("container build file must declare at least one FROM image", validate(path))


if __name__ == "__main__":
    unittest.main()
