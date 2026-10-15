from typing import Optional

from pydantic import BaseModel, Field

class VideoGame(BaseModel):
    id: int
    title: str
    developer: str
    publisher: str
    year_published: int
    sales: int
    price: Optional[float] = Field(default=None, gt=0)
    discount: float = Field(default=0.0, ge=0, lt=1)

class PriceUpdate(BaseModel):
    price: float = Field(gt=0)
    # Leave out to apply the standard promotional discount.
    discount: Optional[float] = Field(default=None, ge=0, lt=1)

class User(BaseModel):
    username: str
    token: str
    is_admin: bool
    email: str
