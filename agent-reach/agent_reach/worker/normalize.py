"""Normalize untrusted public-source records into bounded research items."""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any

MAX_CONTENT_CHARS = 20_000


@dataclass(frozen=True)
class ResearchItem:
    id: str
    source_name: str
    source_type: str
    source_url: str
    title: str
    published_at: str | None
    retrieved_at: str
    content_text: str
    content_hash: str
    job_id: str
    status: str
    validation_notes: str


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _published(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _utc_iso(value)
    if not isinstance(value, str):
        raise ValueError("published_at must be an ISO timestamp or null")
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("published_at must be an ISO timestamp or null") from exc
    return _utc_iso(parsed)


def normalize_record(
    record: dict[str, Any],
    *,
    job_id: str,
    retrieved_at: datetime | None = None,
) -> ResearchItem:
    if not isinstance(record, dict):
        raise ValueError("record must be an object")

    required = ("source_name", "source_type", "source_url", "title", "content_text")
    for field in required:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"{field} is required")

    source_url = record["source_url"].strip()
    parsed_url = urlparse(source_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise ValueError("source_url must use http or https")

    title = record["title"].strip()[:500]
    content = re.sub(r"\s+", " ", record["content_text"]).strip()[:MAX_CONTENT_CHARS]
    if not content:
        raise ValueError("content_text is empty after normalization")

    source_name = record["source_name"].strip()[:120]
    source_type = record["source_type"].strip()[:80]
    digest_input = f"{source_name.lower()}\0{content}".encode("utf-8")
    content_hash = hashlib.sha256(digest_input).hexdigest()
    timestamp = retrieved_at or datetime.now(timezone.utc)

    return ResearchItem(
        id=str(uuid.uuid4()),
        source_name=source_name,
        source_type=source_type,
        source_url=source_url,
        title=title,
        published_at=_published(record.get("published_at")),
        retrieved_at=_utc_iso(timestamp),
        content_text=content,
        content_hash=content_hash,
        job_id=job_id,
        status="validated",
        validation_notes="",
    )
