"""Fail-closed admission checks for explicitly approved third-party extensions."""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

PINNED_SCANNER_VERSION = "2.13.6"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _valid_repository(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment:
        return False
    parts = parsed.path.strip("/").split("/")
    return len(parts) == 2 and all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts)


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def evaluate_extension(
    registry: object,
    extension_id: str,
    revision: str,
    report_sha256: str,
    scanner_version: str = PINNED_SCANNER_VERSION,
) -> tuple[bool, list[str]]:
    """Allow only an exact, reviewed repository revision and scan report."""
    reasons: list[str] = []
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        return False, ["registry is missing or has an unsupported schema version"]
    entries = registry.get("extensions")
    if not isinstance(entries, list):
        return False, ["registry extensions must be a list"]
    if not isinstance(extension_id, str) or not _ID_RE.fullmatch(extension_id):
        return False, ["extension identifier is invalid"]
    if not _COMMIT_RE.fullmatch(revision or ""):
        return False, ["requested revision must be a 40-character lowercase Git commit"]
    if not _SHA256_RE.fullmatch(report_sha256 or ""):
        return False, ["requested report digest must be a 64-character SHA-256"]
    if scanner_version != PINNED_SCANNER_VERSION:
        return False, ["scanner version differs from the pinned version"]

    matching = [item for item in entries if isinstance(item, dict) and item.get("id") == extension_id]
    if not matching:
        return False, ["extension is not present in the approved registry"]
    if len(matching) != 1:
        return False, ["duplicate extension identifiers make the registry ambiguous"]
    item = matching[0]

    required = ("repository", "revision", "scanner_version", "decision", "report_sha256",
                "approved_by", "approved_at", "permissions")
    missing = [field for field in required if field not in item]
    if missing:
        return False, ["approval record is missing: " + ", ".join(missing)]
    if not _valid_repository(item["repository"]):
        reasons.append("approval repository must be a canonical HTTPS github.com owner/repository URL")
    if item["revision"] != revision:
        reasons.append("requested Git revision does not match the approved revision")
    if item["report_sha256"] != report_sha256:
        reasons.append("requested scan report digest does not match the approved report")
    if item["scanner_version"] != scanner_version:
        reasons.append("approval record scanner version does not match the pinned scanner")
    if item["decision"] != "pass":
        reasons.append("only a pass decision can be admitted")
    if not isinstance(item["approved_by"], str) or not item["approved_by"].strip():
        reasons.append("human approver identity is missing")
    if not _valid_timestamp(item["approved_at"]):
        reasons.append("human approval timestamp is missing or invalid")
    permissions = item["permissions"]
    if not isinstance(permissions, list) or not permissions or any(
        not isinstance(permission, str) or not permission.strip() for permission in permissions
    ):
        reasons.append("explicit non-empty permission list is required")
    return not reasons, reasons
