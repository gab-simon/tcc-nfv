"""ETSI data repositories with memory and file backends.

NFVO, VNFM and VIM only talk to the ``Repository`` interface, so the storage
can later be swapped for a distributed store (etcd/Raft) without touching the
MANO logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from nfv_mano.common import ConflictError, NotFoundError, RepositoryError
from nfv_mano.config import Settings
from nfv_mano.models import NfviResource, Nsd, NsInstance, VimInfo, Vnfd, VnfInstance


class Repository[T: BaseModel](ABC):
    """CRUD interface for a collection of ETSI entities."""

    def __init__(self, model: type[T], collection: str) -> None:
        self.model = model
        self.collection = collection

    def add(self, entity: T) -> T:
        if self.exists(entity.id):
            raise ConflictError(f"{self.collection}: {entity.id!r} already exists")
        self._persist(entity)
        return entity

    def get(self, entity_id: str) -> T:
        entity = self._retrieve(entity_id)
        if entity is None:
            raise NotFoundError(f"{self.collection}: {entity_id!r} not found")
        return entity

    def update(self, entity: T) -> T:
        if not self.exists(entity.id):
            raise NotFoundError(f"{self.collection}: {entity.id!r} not found")
        self._persist(entity)
        return entity

    def delete(self, entity_id: str) -> None:
        if not self.exists(entity_id):
            raise NotFoundError(f"{self.collection}: {entity_id!r} not found")
        self._remove(entity_id)

    def list(self) -> list[T]:
        return self._list()

    def exists(self, entity_id: str) -> bool:
        return entity_id in self._keys()

    @abstractmethod
    def _persist(self, entity: T) -> None: ...

    @abstractmethod
    def _retrieve(self, entity_id: str) -> T | None: ...

    @abstractmethod
    def _list(self) -> list[T]: ...

    @abstractmethod
    def _remove(self, entity_id: str) -> None: ...

    @abstractmethod
    def _keys(self) -> set[str]: ...


class MemoryRepository[T: BaseModel](Repository[T]):
    """Keeps entities in a dictionary (ephemeral)."""

    def __init__(self, model: type[T], collection: str) -> None:
        super().__init__(model, collection)
        self._data: dict[str, T] = {}

    # Store and return copies so a caller changing an object does not change
    # the stored state without going through update().
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


class FileRepository[T: BaseModel](Repository[T]):
    """Persists each entity as ``<data_dir>/<collection>/<id>.json``."""

    def __init__(self, model: type[T], collection: str, data_dir: Path) -> None:
        super().__init__(model, collection)
        self.directory = Path(data_dir) / collection
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, entity_id: str) -> Path:
        return self.directory / f"{entity_id}.json"

    def _persist(self, entity: T) -> None:
        try:
            self._path(entity.id).write_text(entity.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:
            raise RepositoryError(f"failed to persist {entity.id!r}: {exc}") from exc

    def _retrieve(self, entity_id: str) -> T | None:
        path = self._path(entity_id)
        if not path.exists():
            return None
        try:
            return self.model.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RepositoryError(f"failed to load {entity_id!r}: {exc}") from exc

    def _list(self) -> list[T]:
        return [
            entity
            for path in sorted(self.directory.glob("*.json"))
            if (entity := self._retrieve(path.stem)) is not None
        ]

    def _remove(self, entity_id: str) -> None:
        try:
            self._path(entity_id).unlink()
        except OSError as exc:
            raise RepositoryError(f"failed to remove {entity_id!r}: {exc}") from exc

    def _keys(self) -> set[str]:
        return {path.stem for path in self.directory.glob("*.json")}


def _build[T: BaseModel](model: type[T], collection: str, settings: Settings) -> Repository[T]:
    if settings.repository_backend == "file":
        return FileRepository(model, collection, settings.data_dir)
    return MemoryRepository(model, collection)


@dataclass(frozen=True)
class RepositorySet:
    """The ETSI repositories used by the MANO blocks."""

    vnf_catalog: Repository[Vnfd]
    ns_catalog: Repository[Nsd]
    vnf_instances: Repository[VnfInstance]
    ns_instances: Repository[NsInstance]
    nfvi_resources: Repository[NfviResource]
    vims: Repository[VimInfo]


def build_repositories(settings: Settings) -> RepositorySet:
    """Build every ETSI repository for the given settings."""
    return RepositorySet(
        vnf_catalog=_build(Vnfd, "vnf_catalog", settings),
        ns_catalog=_build(Nsd, "ns_catalog", settings),
        vnf_instances=_build(VnfInstance, "vnf_instances", settings),
        ns_instances=_build(NsInstance, "ns_instances", settings),
        nfvi_resources=_build(NfviResource, "nfvi_resources", settings),
        vims=_build(VimInfo, "vims", settings),
    )
