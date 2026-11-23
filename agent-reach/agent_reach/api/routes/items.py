from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/v1/items", tags=["items"])


@router.get("")
def list_items(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    repository=Depends(lambda: None),
):
    page = repository.list_items(
        limit=limit, offset=offset, source=source, status=status,
        from_date=from_date, to_date=to_date
    )
    return {
        "items": [item.__dict__ for item in page.items],
        "total": page.total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{item_id}")
def get_item(item_id: str, repository=Depends(lambda: None)):
    item = repository.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item.__dict__
