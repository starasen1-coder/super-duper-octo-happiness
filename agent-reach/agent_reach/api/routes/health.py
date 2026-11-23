from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health(repository):
    try:
        repository.count_items()
        latest = repository.list_jobs(limit=1)
        job = latest[0] if latest else None
        return {
            "ok": True,
            "database": "available",
            "last_collection_status": job["status"] if job else None,
            "last_collection_finished_at": job["finished_at"] if job else None,
            "last_collection_source": job["source_name"] if job else None,
        }
    except Exception:
        return {
            "ok": False,
            "database": "unavailable",
            "last_collection_status": None,
            "last_collection_finished_at": None,
            "last_collection_source": None,
        }
