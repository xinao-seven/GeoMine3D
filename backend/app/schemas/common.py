"""统一响应包装。

成功载荷一律包成 ``{data}``（列表端点另加 ``meta`` 分页信息）；错误响应不在
Pydantic 这层定义，见 ``app/core/exceptions.py`` 的 ``{code, message, details, requestId}``。
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    """单条/对象响应：``{"data": T}``。"""

    data: T


class PageMeta(BaseModel):
    """分页元信息。"""

    page: int
    page_size: int
    total: int


class PageResponse(BaseModel, Generic[T]):
    """分页列表响应：``{"data": [T], "meta": PageMeta}``。"""

    data: list[T]
    meta: PageMeta
