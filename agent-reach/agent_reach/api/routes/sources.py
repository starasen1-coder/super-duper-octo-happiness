from fastapi import APIRouter, Depends

router = APIRouter(prefix="/v1/sources", tags=["sources"])


@router.get("")
def list_sources(repository=Depends(lambda: None)):
    names = sorted({item.source_name for item in repository.list_items(limit=200).items})
    return [{"name": name} for name in names]
