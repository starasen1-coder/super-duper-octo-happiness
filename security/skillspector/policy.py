"""Fail-closed policy for NVIDIA SkillSpector's JSON report."""
from __future__ import annotations


def evaluate_report(report: object) -> tuple[str, list[str]]:
    if not isinstance(report, dict):
        return "block", ["scanner report is missing or not a JSON object"]
    assessment = report.get("risk_assessment")
    completeness = report.get("analysis_completeness")
    issues = report.get("issues")
    if not isinstance(assessment, dict) or not isinstance(completeness, dict) or not isinstance(issues, list):
        return "block", ["scanner report is missing required risk, completeness, or issue fields"]

    reasons: list[str] = []
    if report.get("execution_successful") is not True:
        reasons.append("scanner execution was not successful")
    if completeness.get("is_complete") is not True:
        reasons.append("analysis coverage is incomplete")
    if reasons:
        return "block", reasons

    recommendation = assessment.get("recommendation")
    severities = [
        str(issue.get("severity", "")).upper()
        for issue in issues
        if isinstance(issue, dict)
    ]
    max_severity = str(assessment.get("max_issue_severity", "NONE")).upper()
    observed = set(severities + [max_severity])

    if "CRITICAL" in observed or "HIGH" in observed or recommendation == "DO_NOT_INSTALL":
        return "block", [f"high-risk finding or blocking recommendation: {recommendation}/{max_severity}"]
    if recommendation == "CAUTION" or "MEDIUM" in observed:
        return "review", ["medium-risk result requires human review"]
    if recommendation != "SAFE":
        return "block", ["unknown scanner recommendation; fail-closed policy"]
    return "pass", []
