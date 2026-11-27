"""CLI admission gate: deny installation unless exact scan evidence is approved."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from security.skillspector.registry import PINNED_SCANNER_VERSION, evaluate_extension


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("security/skillspector/approved-extensions.json"))
    parser.add_argument("--extension-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--scanner-version", default=PINNED_SCANNER_VERSION)
    args = parser.parse_args(argv)
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("DENY: approval registry is unavailable or malformed")
        return 1
    allowed, reasons = evaluate_extension(
        registry, args.extension_id, args.repository, args.revision, args.report_sha256, args.scanner_version
    )
    if not allowed:
        for reason in reasons:
            print(f"DENY: {reason}")
        return 1
    print(f"ALLOW: {args.extension_id} at {args.revision} matches its reviewed scan evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
