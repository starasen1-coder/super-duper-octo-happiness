from pydantic import BaseModel


class ItemListResponse(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int
