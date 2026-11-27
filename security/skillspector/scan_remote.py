"""Fetch a public GitHub candidate at an immutable commit and scan it statically."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_request(repository: str, revision: str, subdirectory: str) -> tuple[bool, str]:
    if not _REPOSITORY_RE.fullmatch(repository or ""):
        return False, "repository must be owner/name on github.com"
    if not _REVISION_RE.fullmatch(revision or ""):
        return False, "revision must be a 40-character lowercase Git commit"
    if not subdirectory or "\\" in subdirectory:
        return False, "subdirectory must be a relative POSIX path"
    path = PurePosixPath(subdirectory)
    if path.is_absolute() or any(part in ("..", "") for part in path.parts):
        return False, "subdirectory cannot be absolute or traverse outside the checkout"
    return True, ""


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout, shell=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub owner/name")
    parser.add_argument("--revision", required=True, help="immutable 40-character commit")
    parser.add_argument("--subdirectory", default=".", help="skill folder within the checkout")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    valid, reason = validate_request(args.repository, args.revision, args.subdirectory)
    if not valid:
        parser.error(reason)

    with tempfile.TemporaryDirectory(prefix="skillspector-candidate-") as temporary:
        checkout = Path(temporary) / "checkout"
        checkout.mkdir()
        commands = [
            ["git", "-C", str(checkout), "init", "--quiet"],
            ["git", "-C", str(checkout), "remote", "add", "origin",
             f"https://github.com/{args.repository}.git"],
            ["git", "-C", str(checkout), "fetch", "--quiet", "--depth", "1", "origin", args.revision],
            ["git", "-C", str(checkout), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
        ]
        for command in commands:
            result = _run(command)
            if result.returncode:
                print("BLOCK: candidate checkout failed")
                return 1
        head = _run(["git", "-C", str(checkout), "rev-parse", "HEAD"])
        if head.returncode or head.stdout.strip() != args.revision:
            print("BLOCK: fetched commit does not match the requested immutable revision")
            return 1

        target = (checkout / args.subdirectory).resolve()
        if not target.is_relative_to(checkout.resolve()) or not target.is_dir():
            print("BLOCK: target directory is missing or escapes the checkout")
            return 1
        command = [
            sys.executable, "security/skillspector/scan.py",
            "--target", str(target), "--revision", args.revision,
            "--output-dir", str(args.output_dir),
        ]
        result = _run(command, timeout=660)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
