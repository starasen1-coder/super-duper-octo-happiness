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
);
CREATE INDEX IF NOT EXISTS idx_research_retrieved
    ON research_items(retrieved_at DESC);
