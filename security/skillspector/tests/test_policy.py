from security.skillspector.policy import evaluate_report


def report(recommendation="SAFE", severity="NONE", complete=True, execution=True, issues=None):
    return {
        "risk_assessment": {
            "recommendation": recommendation,
            "max_issue_severity": severity,
        },
        "execution_successful": execution,
        "analysis_completeness": {"is_complete": complete},
        "issues": issues or [],
    }


def test_clean_complete_scan_passes():
    decision, reasons = evaluate_report(report())
    assert decision == "pass"
    assert reasons == []


def test_high_or_critical_finding_blocks_even_if_aggregate_is_safe():
    payload = report(issues=[{"severity": "HIGH"}])
    decision, reasons = evaluate_report(payload)
    assert decision == "block"
    assert any("HIGH" in reason for reason in reasons)


def test_medium_finding_requires_human_review():
    payload = report("CAUTION", "MEDIUM", issues=[{"severity": "MEDIUM"}])
    decision, _ = evaluate_report(payload)
    assert decision == "review"


def test_incomplete_or_failed_scan_blocks():
    assert evaluate_report(report(complete=False))[0] == "block"
    assert evaluate_report(report(execution=False))[0] == "block"


def test_invalid_or_missing_report_blocks():
    assert evaluate_report(None)[0] == "block"
    assert evaluate_report({"risk_assessment": {}})[0] == "block"
