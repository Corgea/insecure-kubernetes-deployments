from typing import List, Optional

from pydantic import BaseModel, Field

class VideoGame(BaseModel):
    id: int
    title: str
    developer: str
    publisher: str
    year_published: int
    sales: int

class User(BaseModel):
    username: str
    token: str
    is_admin: bool
    email: str

class OrderItem(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=99)

class OrderRequest(BaseModel):
    items: List[OrderItem] = Field(..., min_length=1, max_length=50)
    currency: str = Field("USD", pattern="^[A-Z]{3}$")

class OrderStatusEvent(BaseModel):
    # Free-form on purpose: the warehouse adds scan types ("packed", "in_transit")
    # faster than we release the API, and statuses the order lifecycle does not
    # model are kept in the order history instead of being rejected.
    status: str = Field(..., min_length=1, max_length=32)
    carrier: Optional[str] = Field(None, max_length=32)
    tracking_number: Optional[str] = Field(None, max_length=64)
    source: str = Field("unknown", min_length=1, max_length=64)
