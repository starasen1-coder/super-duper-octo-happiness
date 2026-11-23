from pathlib import Path

import pytest

from visual_reports.lemo_opuscar.manifest import build_manifest


def test_manifest_records_input_renderer_and_asset_credits(tmp_path):
    report = tmp_path / "research-report.md"
    report.write_text("Curated research summary", encoding="utf-8")

    manifest = build_manifest(
        report_id="report-2026-11-23-01",
        input_paths=[report],
        input_root=tmp_path,
        renderer_version="2.0.0",
        asset_credits=["LEMO Opuscar code: MIT"],
        intended_use="personal_noncommercial",
    )

    assert manifest["input_report_id"] == "report-2026-11-23-01"
    assert manifest["renderer_version"] == "2.0.0"
    assert manifest["inputs"][0]["sha256"]
    assert manifest["asset_credits"] == ["LEMO Opuscar code: MIT"]


def test_manifest_rejects_path_outside_curated_report_root(tmp_path):
    report = tmp_path.parent / "outside.md"
    report.write_text("Not in curated directory", encoding="utf-8")

    with pytest.raises(ValueError, match="inside"):
        build_manifest(
            report_id="report-1",
            input_paths=[report],
            input_root=tmp_path,
            renderer_version="2.0.0",
            asset_credits=[],
            intended_use="personal_noncommercial",
        )


def test_manifest_blocks_commercial_use_of_noncommercial_style_docs(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("Summary", encoding="utf-8")

    with pytest.raises(ValueError, match="CC BY-NC"):
        build_manifest(
            report_id="report-2",
            input_paths=[report],
            input_root=tmp_path,
            renderer_version="2.0.0",
            asset_credits=["LEMO Opuscar style prompts: CC BY-NC 4.0"],
            intended_use="commercial",
        )
