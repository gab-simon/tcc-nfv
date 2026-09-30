"""Generic repository interface shared by all ETSI data repositories.

The interface is deliberately CRUD-only and synchronous. The MANO logic never
talks to a concrete database, only to this abstraction, which is the seam where
a replicated store (etcd, backed by the Raft consensus algorithm) will be
plugged in as future work.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from nfv_mano.common.exceptions import ConflictError, NotFoundError


class Repository[T: BaseModel](ABC):
    """CRUD interface for a collection of ETSI entities.

    Every entity is a :class:`pydantic.BaseModel` with a string ``id``.
    """

    def __init__(self, model: type[T], collection: str) -> None:
        self.model = model
        self.collection = collection

    def add(self, entity: T) -> T:
        """Insert a new entity, raising :class:`ConflictError` if it exists."""
        if self.exists(entity.id):
            raise ConflictError(f"{self.collection}: entity {entity.id!r} already exists")
        self._persist(entity)
        return entity

    def get(self, entity_id: str) -> T:
        """Return an entity by id, raising :class:`NotFoundError` if missing."""
        entity = self._retrieve(entity_id)
        if entity is None:
            raise NotFoundError(f"{self.collection}: entity {entity_id!r} not found")
        return entity

    def get_optional(self, entity_id: str) -> T | None:
        """Return an entity by id or ``None`` if it does not exist."""
        return self._retrieve(entity_id)

    def list(self) -> list[T]:
        """Return all entities in the collection."""
        return self._list()

    def update(self, entity: T) -> T:
        """Replace an existing entity, raising :class:`NotFoundError` if missing."""
        if not self.exists(entity.id):
            raise NotFoundError(f"{self.collection}: entity {entity.id!r} not found")
        self._persist(entity)
        return entity

    def delete(self, entity_id: str) -> None:
        """Delete an entity by id, raising :class:`NotFoundError` if missing."""
        if not self.exists(entity_id):
            raise NotFoundError(f"{self.collection}: entity {entity_id!r} not found")
        self._remove(entity_id)

    def exists(self, entity_id: str) -> bool:
        """Return ``True`` if an entity with the given id exists."""
        return entity_id in self._keys()

    @abstractmethod
    def _persist(self, entity: T) -> None:
        """Persist (insert or replace) an entity."""

    @abstractmethod
    def _retrieve(self, entity_id: str) -> T | None:
        """Load an entity, returning ``None`` when absent."""

    @abstractmethod
    def _list(self) -> list[T]:
        """Load every entity in the collection."""

    @abstractmethod
    def _remove(self, entity_id: str) -> None:
        """Remove an entity from the collection."""

    @abstractmethod
    def _keys(self) -> set[str]:
        """Return the ids currently stored in the collection."""
