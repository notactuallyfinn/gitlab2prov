from collections import defaultdict
from typing import Any, Optional, Type, TypeVar

R = TypeVar("R")


class InMemoryRepository:
    # TODO: speed up retrieval
    def __init__(self):
        self.repo = defaultdict(list)

    def add(self, resource: R) -> None:
        self.repo[type(resource)].append(resource)

    def get(self, resource_type: Type[R], **filters: Any) -> Optional[R]:
        return next(
            (
                r
                for r in self.repo.get(resource_type, [])
                if all(getattr(r, key) == val for key, val in filters.items())
            ),
            None,
        )

    def list_all(self, resource_type: Type[R], **filters: Any) -> list[R]:
        return [
            r for r in self.repo.get(resource_type, []) if all(getattr(r, key) == val for key, val in filters.items())
        ]
