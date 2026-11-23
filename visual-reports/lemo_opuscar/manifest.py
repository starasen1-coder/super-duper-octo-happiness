"""Create provenance manifests for optional, manually rendered LEMO reports."""
from __future__ import annotations

import hashlib
from pathlib import Path


def build_manifest(
    *,
    report_id: str,
    input_paths: list[Path],
    input_root: Path,
    renderer_version: str,
    asset_credits: list[str],
    intended_use: str,
    commercial_permission: bool = False,
) -> dict:
    if not report_id.strip():
        raise ValueError("report_id is required")
    if not renderer_version.strip():
        raise ValueError("renderer_version is required")
    if intended_use not in {"personal_noncommercial", "commercial"}:
        raise ValueError("intended_use must be personal_noncommercial or commercial")

    root = input_root.resolve()
    inputs = []
    for path in input_paths:
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(root):
            raise ValueError("every input file must exist inside the curated report input directory")
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        inputs.append({"path": resolved.relative_to(root).as_posix(), "sha256": digest})
    if not inputs:
        raise ValueError("at least one curated report input is required")

    credits = [str(value).strip() for value in asset_credits if str(value).strip()]
    uses_noncommercial_docs = any("CC BY-NC" in value.upper() for value in credits)
    if intended_use == "commercial" and uses_noncommercial_docs and not commercial_permission:
        raise ValueError("LEMO Opuscar style documentation is CC BY-NC 4.0; commercial permission is required")

    return {
        "input_report_id": report_id,
        "renderer": "LEMO Opuscar",
        "renderer_version": renderer_version,
        "inputs": inputs,
        "asset_credits": credits,
        "intended_use": intended_use,
        "commercial_permission_recorded": bool(commercial_permission),
    }
