from agent_reach.storage.repository import ResearchRepository
from agent_reach.worker.normalize import normalize_record


def item(source_name="source-a", content="Same text"):
    return normalize_record(
        {
            "source_name": source_name,
            "source_type": "web",
            "source_url": f"https://{source_name}.example/item",
            "title": "Research item",
            "content_text": content,
        },
        job_id="job-1",
    )


def test_repository_deduplicates_within_source_but_keeps_provenance(tmp_path):
    repository = ResearchRepository(tmp_path / "research.sqlite3")
    first = item("source-a")
    duplicate = item("source-a")
    other_source = item("source-b")

    result = repository.insert_items([first, duplicate, other_source])

    assert result.inserted == 2
    assert result.duplicates == 1
    assert repository.count_items() == 2
    assert repository.get_item(first.id).source_name == "source-a"
    assert repository.get_item(other_source.id).source_name == "source-b"


def test_repository_lists_items_and_returns_none_for_unknown_id(tmp_path):
    repository = ResearchRepository(tmp_path / "research.sqlite3")
    saved = item()
    repository.insert_items([saved])

    page = repository.list_items(limit=10)

    assert len(page.items) == 1
    assert page.items[0].id == saved.id
    assert repository.get_item("missing") is None
