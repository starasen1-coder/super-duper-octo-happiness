import pytest

from agent_reach.storage.repository import ResearchRepository
from agent_reach.worker.runner import collect_github_search


class FakeCLI:
    def search_github(self, query, *, limit):
        assert query == "agent security"
        assert limit == 10
        return [{
            "source_name": "agent-reach-github",
            "source_type": "github",
            "source_url": "https://github.com/example/skill",
            "title": "example/skill",
            "content_text": "Public skill source.",
        }]


class FailingCLI:
    def search_github(self, query, *, limit):
        raise TimeoutError("upstream timeout")


def test_collection_persists_records_and_completed_job(tmp_path):
    repository = ResearchRepository(tmp_path / "research.sqlite3")

    result = collect_github_search(
        "agent security", job_id="job-1", repository=repository, cli=FakeCLI()
    )

    assert result.inserted == 1
    assert repository.count_items() == 1
    assert repository.list_jobs()[0]["status"] == "completed"


def test_collection_marks_job_failed_and_reraises(tmp_path):
    repository = ResearchRepository(tmp_path / "research.sqlite3")

    with pytest.raises(TimeoutError):
        collect_github_search(
            "agent security", job_id="job-2", repository=repository, cli=FailingCLI()
        )

    assert repository.list_jobs()[0]["status"] == "failed"
    assert repository.list_jobs()[0]["error_summary"] == "TimeoutError"

def test_collection_retries_one_transient_timeout(tmp_path, monkeypatch):
    class FlakyCLI:
        calls = 0

        def search_github(self, query, *, limit):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary timeout")
            return FakeCLI().search_github(query, limit=limit)

    monkeypatch.setattr("agent_reach.worker.runner.time.sleep", lambda seconds: None)
    repository = ResearchRepository(tmp_path / "research.sqlite3")
    cli = FlakyCLI()

    result = collect_github_search(
        "agent security", job_id="job-retry", repository=repository, cli=cli
    )

    assert cli.calls == 2
    assert result.inserted == 1
    assert repository.list_jobs()[0]["status"] == "completed"
