from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health(repository):
    try:
        repository.count_items()
        return {"ok": True, "database": "available"}
    except Exception:
        return {"ok": False, "database": "unavailable"}
