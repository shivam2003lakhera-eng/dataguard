from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A page of list results."""

    items: list[T]
    total: int
    limit: int
    offset: int