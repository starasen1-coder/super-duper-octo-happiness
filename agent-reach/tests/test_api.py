from fastapi.testclient import TestClient

from agent_reach.api.app import create_app
from agent_reach.storage.repository import ResearchRepository
from agent_reach.worker.normalize import normalize_record


def seeded_repository(tmp_path):
    repository = ResearchRepository(tmp_path / "research.sqlite3")
    item = normalize_record(
        {
            "source_name": "public-github",
            "source_type": "github",
            "source_url": "https://github.com/example/project",
            "title": "Example project",
            "content_text": "Public project summary",
        },
        job_id="job-1",
    )
    repository.insert_items([item])
    repository.create_job("job-1", "public-github", started_at="2026-11-23T00:00:00Z")
    repository.finish_job(
        "job-1", status="completed", finished_at="2026-11-23T00:01:00Z",
        items_seen=1, items_saved=1, error_summary=None
    )
    return repository, item


def test_api_lists_items_sources_jobs_and_item_detail(tmp_path):
    repository, item = seeded_repository(tmp_path)
    client = TestClient(create_app(repository=repository, api_token="test-token"))

    headers = {"Authorization": "Bearer test-token"}
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["last_collection_status"] == "completed"
    assert client.get("/v1/sources", headers=headers).json()[0]["name"] == "public-github"
    assert client.get("/v1/items", headers=headers).json()["items"][0]["id"] == item.id
    assert client.get(f"/v1/items/{item.id}", headers=headers).json()["title"] == "Example project"
    assert client.get("/v1/jobs", headers=headers).json()[0]["job_id"] == "job-1"


def test_api_requires_authentication_for_non_local_client(tmp_path):
    repository, _ = seeded_repository(tmp_path)
    client = TestClient(create_app(repository=repository, api_token="test-token"))

    assert client.get("/v1/items").status_code == 401
    assert client.get("/v1/items", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/v1/items", headers={"Authorization": "Bearer test-token"}).status_code == 200


def test_api_returns_404_for_unknown_item_and_422_for_invalid_page(tmp_path):
    repository, _ = seeded_repository(tmp_path)
    client = TestClient(create_app(repository=repository, api_token="test-token"))
    headers = {"Authorization": "Bearer test-token"}

    assert client.get("/v1/items/missing", headers=headers).status_code == 404
    assert client.get("/v1/items?limit=0", headers=headers).status_code == 422

def test_default_api_opens_existing_database_read_only(tmp_path):
    repository, item = seeded_repository(tmp_path)
    database_path = repository.database_path
    client = TestClient(create_app(database_path=database_path, api_token="test-token"))

    response = client.get(
        f"/v1/items/{item.id}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == item.id
