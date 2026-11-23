from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("")
def list_jobs(limit: int = Query(50, ge=1, le=200), repository=Depends(lambda: None)):
    return repository.list_jobs(limit=limit)
