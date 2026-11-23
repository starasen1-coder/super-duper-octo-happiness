"""Bounded subprocess adapter. Only fixed, reviewed CLI argument arrays are accepted."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence
from urllib.parse import urlparse


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class AgentReachCLI:
    def __init__(self, executable: str = "agent-reach", timeout_seconds: int = 90, max_output_chars: int = 200_000):
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def run(self, arguments: Sequence[str]) -> CommandResult:
        if not arguments or any(not isinstance(arg, str) or not arg for arg in arguments):
            raise ValueError("a non-empty argument list is required")
        if any(arg.startswith(("--shell", "--command")) for arg in arguments):
            raise ValueError("shell execution flags are not permitted")
        completed = subprocess.run(
            [self.executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            shell=False,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout[: self.max_output_chars],
            stderr=completed.stderr[: min(self.max_output_chars, 4_000)],
        )

    def search_github(self, query: str, *, limit: int = 5) -> list[dict]:
        """Search public GitHub through Agent Reach's unauthenticated REST backend."""
        import json

        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required")
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        result = self.run([
            "github", "search", query.strip(), "--limit", str(limit), "--backend", "github-api"
        ])
        if result.returncode != 0:
            raise RuntimeError(f"Agent Reach exited with status {result.returncode}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("Agent Reach returned invalid JSON") from exc
        if payload.get("ok") is not True:
            error = payload.get("error") or {}
            raise RuntimeError(f"Agent Reach {error.get('code', 'ERROR')}: {error.get('message', 'request failed')}")
        if payload.get("channel") != "github" or payload.get("action") != "search":
            raise ValueError("Agent Reach response does not match the requested GitHub search")
        records = []
        for item in payload.get("items", []):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            parsed_url = urlparse(str(item["url"]))
            if parsed_url.scheme != "https" or parsed_url.netloc.lower() != "github.com":
                continue
            raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
            content = item.get("text") or raw.get("description") or item.get("title") or ""
            if not str(content).strip():
                continue
            records.append({
                "source_name": "agent-reach-github",
                "source_type": "github",
                "source_url": item["url"],
                "title": item.get("title") or "GitHub result",
                "published_at": item.get("published_at"),
                "content_text": str(content),
            })
        return records
