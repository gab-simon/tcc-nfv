"""In-memory repository backend.

Useful for tests and for running the MANO base without touching the disk. All
state is lost when the process exits, which is acceptable because the base is
explicitly not fault tolerant yet.
"""

from __future__ import annotations

from pydantic import BaseModel

from nfv_mano.repositories.base import Repository


class MemoryRepository[T: BaseModel](Repository[T]):
    """A repository that keeps entities in a dictionary."""

    def __init__(self, model: type[T], collection: str) -> None:
        super().__init__(model, collection)
        self._data: dict[str, T] = {}

    def _persist(self, entity: T) -> None:
        self._data[entity.id] = entity.model_copy(deep=True)

    def _retrieve(self, entity_id: str) -> T | None:
        entity = self._data.get(entity_id)
        return entity.model_copy(deep=True) if entity is not None else None

    def _list(self) -> list[T]:
        return [entity.model_copy(deep=True) for entity in self._data.values()]

    def _remove(self, entity_id: str) -> None:
        del self._data[entity_id]

    def _keys(self) -> set[str]:
        return set(self._data)
