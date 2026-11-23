"""Command-line entry for scheduled, allowlisted research collection."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from agent_reach.storage.repository import ResearchRepository
from agent_reach.worker.config import load_sources
from agent_reach.worker.runner import collect_github_search


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-reach-worker")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--config", required=True)
    collect.add_argument("--db", default=os.getenv("AGENT_REACH_DB", "/var/lib/agent-reach/research.sqlite3"))
    args = parser.parse_args(argv)

    try:
        sources = [source for source in load_sources(args.config) if source.enabled]
        repository = ResearchRepository(args.db)
        for source in sources:
            if source.source_type != "github" or not source.query.strip():
                raise ValueError(f"unsupported or incomplete source configuration: {source.name}")
            result = collect_github_search(
                source.query,
                job_id=str(uuid.uuid4()),
                repository=repository,
            )
            print(json.dumps({
                "source": source.name,
                "inserted": result.inserted,
                "duplicates": result.duplicates,
            }))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
