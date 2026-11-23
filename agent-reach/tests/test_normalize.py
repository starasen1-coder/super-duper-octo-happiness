from datetime import datetime, timezone

import pytest

from agent_reach.worker.normalize import normalize_record


def test_normalize_record_preserves_missing_publication_time():
    item = normalize_record(
        {
            "source_name": "example",
            "source_type": "web",
            "source_url": "https://example.org/article",
            "title": "Research note",
            "content_text": "A concise public research extract.",
        },
        job_id="job-1",
        retrieved_at=datetime(2026, 11, 23, tzinfo=timezone.utc),
    )

    assert item.published_at is None
    assert item.retrieved_at == "2026-11-23T00:00:00Z"
    assert item.source_url == "https://example.org/article"
    assert len(item.content_hash) == 64


def test_normalize_record_rejects_missing_source_provenance():
    with pytest.raises(ValueError, match="source_name"):
        normalize_record(
            {
                "source_type": "web",
                "source_url": "https://example.org/article",
                "title": "Research note",
                "content_text": "Text",
            },
            job_id="job-1",
        )


def test_normalize_record_rejects_non_http_source_url():
    with pytest.raises(ValueError, match="http"):
        normalize_record(
            {
                "source_name": "example",
                "source_type": "web",
                "source_url": "file:///etc/passwd",
                "title": "Research note",
                "content_text": "Text",
            },
            job_id="job-1",
        )
