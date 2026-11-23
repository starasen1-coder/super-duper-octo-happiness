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
