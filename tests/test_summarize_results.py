import unittest

from scripts.summarize_results import validate_results


class SummaryTests(unittest.TestCase):
    def test_requires_each_expected_gate(self):
        self.assertEqual(validate_results({"security": {"result": "success"}}, ["security"]), [])
        self.assertTrue(validate_results({"security": {"result": "success"}}, ["security", "machine"]))

    def test_skipped_or_cancelled_gate_fails(self):
        for result in ("skipped", "cancelled", "failure", None):
            self.assertTrue(validate_results({"security": {"result": result}}, ["security"]))

    def test_rejects_malformed_inputs(self):
        self.assertTrue(validate_results([], ["security"]))
        self.assertTrue(validate_results({"security": {"result": "success"}}, []))


if __name__ == "__main__":
    unittest.main()
