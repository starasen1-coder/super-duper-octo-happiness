"""SQLite persistence for provenance-bearing research records."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from agent_reach.worker.normalize import ResearchItem


@dataclass(frozen=True)
class IngestResult:
    inserted: int
    duplicates: int


@dataclass(frozen=True)
class ItemPage:
    items: list[ResearchItem]
    total: int


class ResearchRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_items (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    published_at TEXT NULL,
                    retrieved_at TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    validation_notes TEXT NOT NULL,
                    UNIQUE(source_name, content_hash)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_research_retrieved ON research_items(retrieved_at DESC)"
            )

    def insert_items(self, items: Sequence[ResearchItem]) -> IngestResult:
        inserted = 0
        duplicates = 0
        with self._connect() as connection:
            for item in items:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO research_items (
                        id, source_name, source_type, source_url, title,
                        published_at, retrieved_at, content_text, content_hash,
                        job_id, status, validation_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id, item.source_name, item.source_type, item.source_url,
                        item.title, item.published_at, item.retrieved_at,
                        item.content_text, item.content_hash, item.job_id,
                        item.status, item.validation_notes,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
                else:
                    duplicates += 1
        return IngestResult(inserted=inserted, duplicates=duplicates)

    def count_items(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM research_items").fetchone()[0])

    @staticmethod
    def _to_item(row: sqlite3.Row) -> ResearchItem:
        return ResearchItem(**dict(row))

    def get_item(self, item_id: str) -> ResearchItem | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_items WHERE id = ?", (item_id,)
            ).fetchone()
        return self._to_item(row) if row else None

    def list_items(self, *, limit: int = 50, offset: int = 0) -> ItemPage:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        with self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM research_items").fetchone()[0])
            rows = connection.execute(
                "SELECT * FROM research_items ORDER BY retrieved_at DESC, id ASC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return ItemPage(items=[self._to_item(row) for row in rows], total=total)
