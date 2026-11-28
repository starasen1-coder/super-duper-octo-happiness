"""Run pinned SkillSpector on a local, immutable Git checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PINNED_VERSION = "2.13.7"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def verify_revision(target: Path, revision: str) -> bool:
    if not COMMIT_RE.fullmatch(revision):
        return False
    result = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        check=False, capture_output=True, text=True, timeout=10, shell=False,
    )
    return result.returncode == 0 and result.stdout.strip().lower() == revision


def evaluate_report(report: object) -> tuple[str, list[str]]:
    from security.skillspector.policy import evaluate_report as evaluate
    return evaluate(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scanner-version", default=PINNED_VERSION)
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "skillspector-report.json"
    manifest_path = args.output_dir / "scan-manifest.json"
    reason = []
    decision = "block"
    report = None
    scanner_exit = 2

    if args.scanner_version != PINNED_VERSION:
        reason.append("scanner version differs from pinned version")
    elif not args.target.is_dir() or not verify_revision(args.target, args.revision):
        reason.append("target must be a local Git checkout at the supplied immutable commit")
    else:
        version = subprocess.run(
            ["skillspector", "--version"], check=False, capture_output=True, text=True,
            timeout=15, shell=False,
        )
        version_text = (version.stdout + version.stderr).strip()
        if version.returncode != 0 or PINNED_VERSION not in version_text:
            reason.append("installed SkillSpector version does not match the pin")
        else:
            scan = subprocess.run(
                [
                    "skillspector", "scan", str(args.target), "--no-llm",
                    "--format", "json", "--output", str(report_path), "--fail-on-incomplete",
                ],
                check=False, capture_output=True, text=True, timeout=600, shell=False,
            )
            scanner_exit = scan.returncode
            if scanner_exit != 0:
                reason.append(f"scanner exited with status {scanner_exit}")
            if report_path.is_file():
                try:
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    reason.append("scanner report is missing or malformed")
            else:
                reason.append("scanner report is missing")
            if scanner_exit == 0 and report is not None:
                decision, policy_reasons = evaluate_report(report)
                reason.extend(policy_reasons)

    report_digest = None
    if report_path.is_file():
        report_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    manifest = {
        "target": str(args.target.resolve()),
        "target_revision": args.revision,
        "scanner": "NVIDIA SkillSpector",
        "scanner_version": args.scanner_version,
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "scanner_exit_code": scanner_exit,
        "decision": decision,
        "reasons": reason,
        "report_sha256": report_digest,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
    return 0 if decision == "pass" else (2 if decision == "review" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
