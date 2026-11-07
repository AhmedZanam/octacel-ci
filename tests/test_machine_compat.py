import unittest

from scripts.validate_machine_compat import validate


class MachineCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "targets": ["vps41"],
            "resources": {"cpuCount": 2, "memoryMiB": 2048, "storageGiB": 20},
            "container": {"architectures": ["amd64"]},
        }
        self.profiles = {
            "targets": {
                "vps41": {
                    "status": "measured-live",
                    "architecture": "amd64",
                    "capacity": {"cpuCount": 4, "memoryMiB": 7941, "rootStorageGiB": 95},
                }
            }
        }

    def test_accepts_requirements_within_measured_capacity(self):
        self.assertEqual(validate(self.project, self.profiles), [])

    def test_rejects_planned_unverified_capacity(self):
        self.profiles["targets"]["vps41"] = {"status": "planned-unverified", "architecture": "amd64", "capacity": None}
        self.assertIn("vps41 has no verified capacity; runtime compatibility is not claimed", validate(self.project, self.profiles))

    def test_rejects_architecture_mismatch(self):
        self.project["container"]["architectures"] = ["arm64"]
        self.assertIn("vps41 architecture amd64 is not in container.architectures", validate(self.project, self.profiles))

    def test_rejects_malformed_capacity_without_traceback(self):
        self.profiles["targets"]["vps41"]["capacity"]["cpuCount"] = "four"
        self.assertIn("vps41 has incomplete or invalid measured capacity", validate(self.project, self.profiles))


if __name__ == "__main__":
    unittest.main()
