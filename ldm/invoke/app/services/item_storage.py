
from typing import TypeVar, Generic
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel
from abc import ABC, abstractmethod

T = TypeVar('T', bound=BaseModel)

class PaginatedResults(GenericModel, Generic[T]):
    """Paginated results"""
    items: list[T]   = Field(description = "Items")
    page: int        = Field(description = "Current Page")
    pages: int       = Field(description = "Total number of pages")
    per_page: int    = Field(description = "Number of items per page")
    total: int       = Field(description = "Total number of items in result")


class ItemStorageABC(ABC, Generic[T]):
    """Base item storage class"""
    @abstractmethod
    def get(self, item_id: str) -> T:
        pass

    @abstractmethod
    def set(self, item: T) -> None:
        pass

    @abstractmethod
    def list(self, page: int = 0, per_page: int = 10) -> PaginatedResults[T]:
        pass

    @abstractmethod
    def search(self, query: str, page: int = 0, per_page: int = 10) -> PaginatedResults[T]:
        pass
