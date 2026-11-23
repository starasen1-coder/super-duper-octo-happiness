import subprocess

import pytest

from agent_reach.worker.adapters.agent_reach_cli import AgentReachCLI


def test_cli_uses_argument_array_without_shell(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = AgentReachCLI(executable="/usr/bin/agent-reach").run(["--help"])

    assert result.stdout == "ok"
    assert seen["command"] == ["/usr/bin/agent-reach", "--help"]
    assert seen["shell"] is False
    assert seen["timeout"] == 90


def test_cli_rejects_empty_or_shell_style_arguments():
    cli = AgentReachCLI()

    with pytest.raises(ValueError):
        cli.run([])

    with pytest.raises(ValueError, match="shell"):
        cli.run(["--shell", "rm -rf /"])

def test_github_search_forces_public_api_and_parses_json(monkeypatch):
    from agent_reach.worker.adapters.agent_reach_cli import CommandResult

    seen = {}

    def fake_run(self, arguments):
        seen["arguments"] = list(arguments)
        return CommandResult(
            0,
            '{"schema_version":1,"ok":true,"channel":"github","action":"search","items":[{"title":"org/repo","url":"https://github.com/org/repo","text":"Public summary","published_at":null,"raw":{}}]}',
            "",
        )

    monkeypatch.setattr(AgentReachCLI, "run", fake_run)
    result = AgentReachCLI().search_github("market microstructure", limit=3)

    assert seen["arguments"] == [
        "github", "search", "market microstructure", "--limit", "3", "--backend", "github-api"
    ]
    assert result[0]["source_url"] == "https://github.com/org/repo"
    assert result[0]["content_text"] == "Public summary"
