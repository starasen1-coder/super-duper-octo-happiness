"""Small ingestion orchestration seam; scheduling is managed by systemd."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from agent_reach.storage.repository import IngestResult, ResearchRepository
from agent_reach.worker.normalize import normalize_record


def ingest_records(
    records: Iterable[dict],
    *,
    source_name: str,
    source_type: str,
    job_id: str,
    repository: ResearchRepository,
) -> IngestResult:
    normalized = []
    for record in records:
        candidate = dict(record)
        candidate.setdefault("source_name", source_name)
        candidate.setdefault("source_type", source_type)
        normalized.append(
            normalize_record(
                candidate,
                job_id=job_id,
                retrieved_at=datetime.now(timezone.utc),
            )
        )
    return repository.insert_items(normalized)

def collect_github_search(
    query: str,
    *,
    job_id: str,
    repository: ResearchRepository,
    cli=None,
) -> IngestResult:
    """Collect a bounded public GitHub search; persist a terminal job state."""
    from datetime import datetime, timezone
    from agent_reach.worker.adapters.agent_reach_cli import AgentReachCLI

    adapter = cli or AgentReachCLI()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    repository.create_job(job_id, "agent-reach-github", started_at=started)
    try:
        records = adapter.search_github(query, limit=10)
        result = ingest_records(
            records,
            source_name="agent-reach-github",
            source_type="github",
            job_id=job_id,
            repository=repository,
        )
        finished = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        repository.finish_job(
            job_id,
            status="completed",
            finished_at=finished,
            items_seen=len(records),
            items_saved=result.inserted,
            error_summary=None,
        )
        return result
    except Exception as exc:
        finished = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        repository.finish_job(
            job_id,
            status="failed",
            finished_at=finished,
            items_seen=0,
            items_saved=0,
            error_summary=type(exc).__name__,
        )
        raise
