from security.skillspector.registry import evaluate_extension


def approved_entry(**overrides):
    entry = {
        "id": "safe-research-skill",
        "repository": "https://github.com/example/safe-research-skill",
        "revision": "a" * 40,
        "scanner_version": "2.13.7",
        "decision": "pass",
        "report_sha256": "b" * 64,
        "approved_by": "security-reviewer",
        "approved_at": "2026-11-27T12:00:00Z",
        "permissions": ["read:public-research"],
    }
    entry.update(overrides)
    return entry


def registry(entry=None):
    return {"schema_version": 1, "extensions": [entry or approved_entry()]}


def test_exact_approved_identity_and_report_is_allowed():
    allowed, reasons = evaluate_extension(
        registry(), "safe-research-skill", "https://github.com/example/safe-research-skill", "a" * 40, "b" * 64, "2.13.7"
    )
    assert allowed is True
    assert reasons == []


def test_unknown_extension_is_denied_by_default():
    allowed, reasons = evaluate_extension(registry(), "unknown", "https://github.com/example/safe-research-skill", "a" * 40, "b" * 64, "2.13.7")
    assert allowed is False
    assert any("not present" in reason for reason in reasons)


def test_changed_revision_or_report_digest_is_denied():
    assert not evaluate_extension(registry(), "safe-research-skill", "https://github.com/example/safe-research-skill", "c" * 40, "b" * 64, "2.13.7")[0]
    assert not evaluate_extension(registry(), "safe-research-skill", "https://github.com/example/safe-research-skill", "a" * 40, "d" * 64, "2.13.7")[0]


def test_non_pass_or_missing_human_approval_is_denied():
    assert not evaluate_extension(
        registry(approved_entry(decision="review")), "safe-research-skill", "https://github.com/example/safe-research-skill", "a" * 40, "b" * 64, "2.13.7"
    )[0]
    assert not evaluate_extension(
        registry(approved_entry(approved_by="")), "safe-research-skill", "https://github.com/example/safe-research-skill", "a" * 40, "b" * 64, "2.13.7"
    )[0]


def test_duplicate_ids_and_malformed_registry_fail_closed():
    duplicate = {"schema_version": 1, "extensions": [approved_entry(), approved_entry()]}
    assert not evaluate_extension(duplicate, "safe-research-skill", "https://github.com/example/safe-research-skill", "a" * 40, "b" * 64, "2.13.7")[0]
    assert not evaluate_extension({}, "safe-research-skill", "https://github.com/example/safe-research-skill", "a" * 40, "b" * 64, "2.13.7")[0]


def test_scanner_version_must_match_pinned_version():
    assert not evaluate_extension(
        registry(), "safe-research-skill", "https://github.com/example/safe-research-skill", "a" * 40, "b" * 64, "9.9.9"
    )[0]


def test_different_repository_cannot_reuse_an_approved_id():
    allowed, reasons = evaluate_extension(
        registry(), "safe-research-skill", "https://github.com/attacker/fork",
        "a" * 40, "b" * 64, "2.13.7"
    )
    assert allowed is False
    assert any("repository" in reason for reason in reasons)


def test_checked_in_empty_registry_denies_unlisted_extension():
    from pathlib import Path
    import json

    empty_registry = json.loads(
        Path("security/skillspector/approved-extensions.json").read_text(encoding="utf-8")
    )
    allowed, reasons = evaluate_extension(
        empty_registry, "safe-research-skill",
        "https://github.com/example/safe-research-skill",
        "a" * 40, "b" * 64, "2.13.7"
    )
    assert allowed is False
    assert reasons


def test_approval_timestamp_must_include_timezone():
    allowed, reasons = evaluate_extension(
        registry(approved_entry(approved_at="2026-11-27T12:00:00")),
        "safe-research-skill", "https://github.com/example/safe-research-skill",
        "a" * 40, "b" * 64, "2.13.7"
    )
    assert allowed is False
    assert any("timestamp" in reason for reason in reasons)


def test_admission_cli_denies_unknown_extension(tmp_path):
    import json
    from security.skillspector.require_approved import main

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"schema_version": 1, "extensions": []}), encoding="utf-8")
    result = main([
        "--registry", str(registry_path),
        "--extension-id", "unknown",
        "--repository", "https://github.com/example/unknown",
        "--revision", "a" * 40,
        "--report-sha256", "b" * 64,
    ])
    assert result == 1


def test_admission_cli_allows_only_matching_approved_record(tmp_path):
    import json
    from security.skillspector.require_approved import main

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry()), encoding="utf-8")
    result = main([
        "--registry", str(registry_path),
        "--extension-id", "safe-research-skill",
        "--repository", "https://github.com/example/safe-research-skill",
        "--revision", "a" * 40,
        "--report-sha256", "b" * 64,
    ])
    assert result == 0
