from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Message(BaseModel):
    message: str


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    services: dict[str, str]
