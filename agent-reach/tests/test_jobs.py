from agent_reach.storage.repository import ResearchRepository


def test_job_lifecycle_is_persisted(tmp_path):
    repository = ResearchRepository(tmp_path / "research.sqlite3")

    repository.create_job("job-42", "github-public", started_at="2026-11-23T10:00:00Z")
    repository.finish_job(
        "job-42",
        status="completed",
        finished_at="2026-11-23T10:00:10Z",
        items_seen=3,
        items_saved=2,
        error_summary=None,
    )

    jobs = repository.list_jobs(limit=10)
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == "job-42"
    assert jobs[0]["status"] == "completed"
    assert jobs[0]["items_seen"] == 3
    assert jobs[0]["items_saved"] == 2


def test_job_cannot_finish_with_unknown_status(tmp_path):
    repository = ResearchRepository(tmp_path / "research.sqlite3")
    repository.create_job("job-43", "github-public", started_at="2026-11-23T10:00:00Z")

    try:
        repository.finish_job(
            "job-43", status="mystery", finished_at="2026-11-23T10:00:10Z",
            items_seen=0, items_saved=0, error_summary=None
        )
    except ValueError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("invalid job status was accepted")
