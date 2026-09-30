"""Tests for the ETSI data repositories (memory and file backends)."""

from __future__ import annotations

import pytest

from nfv_mano.common.exceptions import ConflictError, NotFoundError
from nfv_mano.common.models import VirtualCompute, Vnfd
from nfv_mano.repositories.backends import FileRepository, MemoryRepository
from nfv_mano.repositories.base import Repository


@pytest.fixture(params=["memory", "file"])
def repo(request: pytest.FixtureRequest, tmp_path) -> Repository[Vnfd]:
    """Run every test against both backends."""
    if request.param == "memory":
        return MemoryRepository(Vnfd, "vnf_catalog")
    return FileRepository(Vnfd, "vnf_catalog", tmp_path)


def _make_vnfd(name: str = "vnf-a") -> Vnfd:
    return Vnfd(name=name, virtual_compute=VirtualCompute(image="alpine:latest"))


def test_add_and_get(repo: Repository[Vnfd]) -> None:
    vnfd = _make_vnfd()
    repo.add(vnfd)

    loaded = repo.get(vnfd.id)
    assert loaded.id == vnfd.id
    assert loaded.name == "vnf-a"
    assert loaded.virtual_compute.image == "alpine:latest"


def test_add_conflict(repo: Repository[Vnfd]) -> None:
    vnfd = _make_vnfd()
    repo.add(vnfd)

    with pytest.raises(ConflictError):
        repo.add(vnfd)


def test_get_missing(repo: Repository[Vnfd]) -> None:
    with pytest.raises(NotFoundError):
        repo.get("does-not-exist")
    assert repo.get_optional("does-not-exist") is None


def test_list(repo: Repository[Vnfd]) -> None:
    first = _make_vnfd("vnf-a")
    second = _make_vnfd("vnf-b")
    repo.add(first)
    repo.add(second)

    ids = {entity.id for entity in repo.list()}
    assert ids == {first.id, second.id}


def test_update(repo: Repository[Vnfd]) -> None:
    vnfd = _make_vnfd()
    repo.add(vnfd)

    vnfd.description = "updated"
    repo.update(vnfd)

    assert repo.get(vnfd.id).description == "updated"


def test_update_missing(repo: Repository[Vnfd]) -> None:
    with pytest.raises(NotFoundError):
        repo.update(_make_vnfd())


def test_delete(repo: Repository[Vnfd]) -> None:
    vnfd = _make_vnfd()
    repo.add(vnfd)

    repo.delete(vnfd.id)

    assert not repo.exists(vnfd.id)
    with pytest.raises(NotFoundError):
        repo.delete(vnfd.id)


def test_stored_entities_are_isolated(repo: Repository[Vnfd]) -> None:
    vnfd = _make_vnfd()
    repo.add(vnfd)

    loaded = repo.get(vnfd.id)
    loaded.name = "mutated"

    assert repo.get(vnfd.id).name == "vnf-a"
