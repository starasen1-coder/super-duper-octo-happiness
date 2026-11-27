from security.skillspector.scan_remote import validate_request


def test_accepts_pinned_github_repository_and_subdirectory():
    valid, reason = validate_request("NVIDIA/SkillSpector", "a" * 40, "plugin/skills/demo")
    assert valid is True
    assert reason == ""


def test_rejects_non_repository_url_and_command_injection():
    assert not validate_request("https://example.com/evil", "a" * 40, ".")[0]
    assert not validate_request("owner/repo;echo-pwned", "a" * 40, ".")[0]


def test_rejects_mutable_or_malformed_revision():
    assert not validate_request("owner/repo", "main", ".")[0]
    assert not validate_request("owner/repo", "A" * 40, ".")[0]


def test_rejects_path_traversal_and_absolute_paths():
    assert not validate_request("owner/repo", "a" * 40, "../outside")[0]
    assert not validate_request("owner/repo", "a" * 40, "/etc")[0]
    assert not validate_request("owner/repo", "a" * 40, "folder\\..\\outside")[0]
