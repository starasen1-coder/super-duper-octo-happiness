import json

from agent_reach.worker.config import load_sources


def test_source_configuration_preserves_query_and_disabled_state(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps([
        {"name": "github", "source_type": "github", "query": "agent security", "enabled": True},
        {"name": "disabled", "source_type": "github", "query": "ignore", "enabled": False},
    ]), encoding="utf-8")

    sources = load_sources(path)

    assert sources[0].query == "agent security"
    assert sources[0].enabled is True
    assert sources[1].enabled is False
