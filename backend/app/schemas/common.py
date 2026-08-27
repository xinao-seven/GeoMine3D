from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    data: T


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class PageResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta
