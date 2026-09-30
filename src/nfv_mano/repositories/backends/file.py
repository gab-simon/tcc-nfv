"""File-based repository backend.

Each entity is stored as a JSON document under
``<data_dir>/<collection>/<id>.json``. This mirrors the flat-file persistence
used by the reference implementations while keeping a clean, per-entity
layout that is easier to migrate to a distributed key-value store later.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from nfv_mano.common.exceptions import RepositoryError
from nfv_mano.repositories.base import Repository


class FileRepository[T: BaseModel](Repository[T]):
    """A repository that persists each entity as a JSON file."""

    def __init__(self, model: type[T], collection: str, data_dir: Path) -> None:
        super().__init__(model, collection)
        self.directory = Path(data_dir) / collection
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, entity_id: str) -> Path:
        return self.directory / f"{entity_id}.json"

    def _persist(self, entity: T) -> None:
        try:
            self._path(entity.id).write_text(entity.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise RepositoryError(f"failed to persist {entity.id!r}: {exc}") from exc

    def _retrieve(self, entity_id: str) -> T | None:
        path = self._path(entity_id)
        if not path.exists():
            return None
        try:
            return self.model.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:  # pragma: no cover - filesystem failure
            raise RepositoryError(f"failed to load {entity_id!r}: {exc}") from exc

    def _list(self) -> list[T]:
        entities: list[T] = []
        for path in sorted(self.directory.glob("*.json")):
            entity = self._retrieve(path.stem)
            if entity is not None:
                entities.append(entity)
        return entities

    def _remove(self, entity_id: str) -> None:
        try:
            self._path(entity_id).unlink()
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise RepositoryError(f"failed to remove {entity_id!r}: {exc}") from exc

    def _keys(self) -> set[str]:
        return {path.stem for path in self.directory.glob("*.json")}
