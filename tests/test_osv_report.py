import unittest

from scripts.validate_osv_report import validate_report


class OsvReportTests(unittest.TestCase):
    def test_allows_low_severity_advisories(self):
        value = {"results": [{"packages": [{"vulnerabilities": [{"id": "GHSA-low", "severity": [{"score": "4.0"}]}]}]}]}
        self.assertEqual(validate_report(value, -1), [])

    def test_blocks_high_severity_advisories(self):
        value = {"results": [{"packages": [{"vulnerabilities": [{"id": "GHSA-high", "severity": [{"score": "7.0"}]}]}]}]}
        self.assertIn("GHSA-high: CVSS 7.0", validate_report(value, -1))

    def test_parses_osv_cvss_vectors_and_allows_low_findings(self):
        high = {"id": "GHSA-high-vector", "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}]}
        low = {"id": "GHSA-low-vector", "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N"}]}
        high_report = {"results": [{"packages": [{"vulnerabilities": [high]}]}]}
        low_report = {"results": [{"packages": [{"vulnerabilities": [low]}]}]}
        self.assertIn("GHSA-high-vector: CVSS 9.8", validate_report(high_report, -1))
        self.assertEqual(validate_report(low_report, -1), [])

    def test_fails_closed_when_severity_is_missing(self):
        self.assertTrue(validate_report({"results": [{"packages": [{"vulnerabilities": [{"id": "GHSA-unknown"}]}]}]}, -1))


if __name__ == "__main__":
    unittest.main()
