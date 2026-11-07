import unittest

from scripts.validate_semgrep_report import validate_report as validate_semgrep
from scripts.validate_trivy_report import validate_report as validate_trivy


class SemgrepReportTests(unittest.TestCase):
    def test_blocks_error_without_returning_source_content(self):
        report = {"results": [{"extra": {"severity": "ERROR", "lines": "do-not-print"}}], "errors": []}
        blocking, nonblocking, failures = validate_semgrep(report, "failure")
        self.assertEqual((blocking, nonblocking, failures), (1, 0, []))

    def test_allows_warning_but_fails_closed_on_scanner_error(self):
        report = {"results": [{"extra": {"severity": "WARNING"}}], "errors": []}
        self.assertEqual(validate_semgrep(report, "success"), (0, 1, []))
        self.assertTrue(validate_semgrep(report, "failure")[2])

    def test_fails_closed_on_invalid_report_shape(self):
        self.assertTrue(validate_semgrep({}, "success")[2])


class TrivyReportTests(unittest.TestCase):
    def test_blocks_secret_match_without_returning_value(self):
        report = {"Results": [{"Secrets": [{"Severity": "CRITICAL", "Match": "do-not-print"}]}]}
        self.assertEqual(validate_trivy(report, "failure"), (1, []))

    def test_allows_reports_without_high_or_critical_findings(self):
        report = {"Results": [{"Vulnerabilities": [{"Severity": "LOW"}]}]}
        self.assertEqual(validate_trivy(report, "success"), (0, []))

    def test_fails_closed_on_unclassified_finding_and_scanner_error(self):
        report = {"Results": [{"Secrets": [{"Match": "do-not-print"}]}]}
        self.assertTrue(validate_trivy(report, "success")[1])
        self.assertTrue(validate_trivy({"Results": []}, "failure")[1])


if __name__ == "__main__":
    unittest.main()
