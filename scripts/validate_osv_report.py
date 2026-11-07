#!/usr/bin/env python3
"""Fail OSV scanning only for actionable high or critical advisories."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def scores(value: Any) -> list[float]:
    weights = {
        "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
        "AC": {"L": 0.77, "H": 0.44},
        "PR_U": {"N": 0.85, "L": 0.62, "H": 0.27},
        "PR_C": {"N": 0.85, "L": 0.68, "H": 0.5},
        "UI": {"N": 0.85, "R": 0.62},
        "CIA": {"N": 0.0, "L": 0.22, "H": 0.56},
    }

    def cvss_v3_base_score(vector: str) -> float | None:
        parts = vector.split("/")
        if not parts or parts[0] not in {"CVSS:3.0", "CVSS:3.1"}:
            return None
        metrics = dict(part.split(":", maxsplit=1) for part in parts[1:] if ":" in part)
        required = {"AV", "AC", "PR", "UI", "S", "C", "I", "A"}
        if not required.issubset(metrics) or metrics["S"] not in {"U", "C"}:
            return None
        try:
            av = weights["AV"][metrics["AV"]]
            ac = weights["AC"][metrics["AC"]]
            pr = weights["PR_U" if metrics["S"] == "U" else "PR_C"][metrics["PR"]]
            ui = weights["UI"][metrics["UI"]]
            confidentiality = weights["CIA"][metrics["C"]]
            integrity = weights["CIA"][metrics["I"]]
            availability = weights["CIA"][metrics["A"]]
        except KeyError:
            return None
        impact_subscore = 1 - (1 - confidentiality) * (1 - integrity) * (1 - availability)
        if metrics["S"] == "U":
            impact = 6.42 * impact_subscore
        else:
            impact = 7.52 * (impact_subscore - 0.029) - 3.25 * (impact_subscore - 0.02) ** 15
        if impact <= 0:
            return 0.0
        exploitability = 8.22 * av * ac * pr * ui
        base = min(impact + exploitability, 10.0)
        if metrics["S"] == "C":
            base = min(1.08 * base, 10.0)
        return math.ceil(base * 10 - 1e-10) / 10

    found: list[float] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"score", "cvss_v3_score", "cvssv3score"} and isinstance(child, (float, int, str)):
                try:
                    found.append(float(child))
                except ValueError:
                    vector_score = cvss_v3_base_score(child) if isinstance(child, str) else None
                    if vector_score is not None:
                        found.append(vector_score)
                    else:
                        found.extend(scores(child))
            elif key.lower() in {"severity", "rating", "maxseverity"} and isinstance(child, str):
                severity_scores = {"LOW": 3.9, "MODERATE": 6.9, "MEDIUM": 6.9, "HIGH": 8.9, "CRITICAL": 10.0}
                if child.upper() in severity_scores:
                    found.append(severity_scores[child.upper()])
            else:
                found.extend(scores(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(scores(child))
    elif isinstance(value, str):
        for segment in value.split("/"):
            if segment.startswith("CVSS:3"):
                from urllib.parse import parse_qs
                from urllib.parse import urlparse
                parsed = parse_qs(urlparse(segment).query)
                for score in parsed.get("score", []):
                    try:
                        found.append(float(score))
                    except ValueError:
                        pass
    return found


def advisories(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "vulnerabilities" and isinstance(child, list):
                found.extend(item for item in child if isinstance(item, dict))
            else:
                found.extend(advisories(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(advisories(child))
    return found


def validate_report(value: Any, maximum_findings: int) -> list[str]:
    if not isinstance(value, dict):
        return ["OSV report root must be a JSON object"]
    entries = advisories(value)
    failures: list[str] = []
    for item in entries:
        item_scores = scores(item)
        if not item_scores:
            failures.append(f"{item.get('id', 'unknown advisory')}: severity score is unavailable")
        elif max(item_scores) >= 7.0:
            failures.append(f"{item.get('id', 'unknown advisory')}: CVSS {max(item_scores):.1f}")
    if len(entries) > maximum_findings and maximum_findings >= 0:
        failures.append(f"OSV report contains {len(entries)} advisories; maximum allowed is {maximum_findings}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--maximum-findings", type=int, default=-1)
    arguments = parser.parse_args()
    try:
        report = json.loads(Path(arguments.report).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"OSV report is missing or invalid: {error}", file=sys.stderr)
        return 2
    failures = validate_report(report, arguments.maximum_findings)
    if failures:
        for failure in failures:
            print(f"OSV policy failure: {failure}", file=sys.stderr)
        return 1
    print("OSV report contains no actionable HIGH or CRITICAL vulnerabilities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
