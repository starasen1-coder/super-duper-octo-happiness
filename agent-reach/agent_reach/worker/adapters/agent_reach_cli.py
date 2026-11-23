"""Bounded subprocess adapter. Only fixed, reviewed CLI argument arrays are accepted."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence


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
