from collections import defaultdict
from typing import Self

from gitlab2prov.adapters.repository import InMemoryRepository


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        # self.resources = repository.InMemoryRepository()
        self.resources = defaultdict(InMemoryRepository)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args) -> None:
        self.rollback()

    def commit(self) -> None:
        pass

    def reset(self) -> None:
        self.resources = InMemoryRepository()

    def rollback(self) -> None:
        pass
