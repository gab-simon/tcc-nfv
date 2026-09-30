"""Tests for config, ETSI models and repositories."""

import pytest
from pydantic import ValidationError

from nfv_mano.common import ConflictError, NotFoundError
from nfv_mano.config import Settings, get_settings
from nfv_mano.models import (
    InstantiationState,
    LcmOperationOccurrence,
    LcmOperationState,
    LcmOperationType,
    NsInstance,
    VirtualCompute,
    Vnfd,
    VnfInstance,
)
from nfv_mano.repositories import FileRepository, MemoryRepository, build_repositories


# --- config ---------------------------------------------------------------
def test_config_defaults_and_urls():
    settings = Settings(_env_file=None)
    assert settings.nfvo_port == 9002
    assert settings.vnfm_port == 9001
    assert settings.vim_port == 9000
    assert settings.nfvo_base_url == "http://127.0.0.1:9002"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("NFV_MANO_NFVO_PORT", "9100")
    monkeypatch.setenv("NFV_MANO_REPOSITORY_BACKEND", "file")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.nfvo_port == 9100
    assert settings.repository_backend == "file"
    get_settings.cache_clear()


# --- models ---------------------------------------------------------------
def test_ids_are_unique():
    first = Vnfd(name="a", virtual_compute=VirtualCompute(image="alpine"))
    second = Vnfd(name="b", virtual_compute=VirtualCompute(image="alpine"))
    assert first.id != second.id
    assert first.id.startswith("vnfd-")


def test_model_validation():
    with pytest.raises(ValidationError):
        VirtualCompute(image="alpine", num_cpus=0)
    with pytest.raises(ValidationError):
        VnfInstance(vnfd_id="vnfd-1", vnfm_id="vnfm-1", vim_resource_ids=["res-1", "res-1"])


def test_model_defaults():
    assert VnfInstance(vnfd_id="vnfd-1", vnfm_id="vnfm-1").instantiation_state is (
        InstantiationState.NOT_INSTANTIATED
    )
    assert NsInstance(nsd_id="nsd-1").instantiation_state is InstantiationState.NOT_INSTANTIATED


def test_lcm_states():
    assert LcmOperationState.COMPLETED.is_terminal
    assert LcmOperationState.COMPLETED.is_success
    assert not LcmOperationState.PROCESSING.is_terminal
    occurrence = LcmOperationOccurrence(operation=LcmOperationType.INSTANTIATE, target_id="vnf-1")
    occurrence.touch()
    assert occurrence.updated_at >= occurrence.created_at


# --- repositories ---------------------------------------------------------
def _make_vnfd(name: str = "vnf-a") -> Vnfd:
    return Vnfd(name=name, virtual_compute=VirtualCompute(image="alpine:latest"))


@pytest.fixture(params=["memory", "file"])
def repo(request, tmp_path):
    if request.param == "memory":
        return MemoryRepository(Vnfd, "vnf_catalog")
    return FileRepository(Vnfd, "vnf_catalog", tmp_path)


def test_add_get_list(repo):
    first, second = _make_vnfd("a"), _make_vnfd("b")
    repo.add(first)
    repo.add(second)
    assert repo.get(first.id).name == "a"
    assert {e.id for e in repo.list()} == {first.id, second.id}


def test_conflict_and_missing(repo):
    vnfd = _make_vnfd()
    repo.add(vnfd)
    with pytest.raises(ConflictError):
        repo.add(vnfd)
    with pytest.raises(NotFoundError):
        repo.get("missing")


def test_update_and_delete(repo):
    vnfd = _make_vnfd()
    repo.add(vnfd)
    vnfd.description = "updated"
    repo.update(vnfd)
    assert repo.get(vnfd.id).description == "updated"
    repo.delete(vnfd.id)
    assert not repo.exists(vnfd.id)
    with pytest.raises(NotFoundError):
        repo.delete(vnfd.id)


def test_stored_entities_are_isolated(repo):
    vnfd = _make_vnfd()
    repo.add(vnfd)
    loaded = repo.get(vnfd.id)
    loaded.name = "mutated"
    assert repo.get(vnfd.id).name == "vnf-a"


def test_factory_memory_and_file(tmp_path):
    memory = build_repositories(Settings(_env_file=None, repository_backend="memory"))
    assert isinstance(memory.vnf_catalog, MemoryRepository)

    settings = Settings(_env_file=None, repository_backend="file", data_dir=tmp_path)
    file_repos = build_repositories(settings)
    assert isinstance(file_repos.vnf_catalog, FileRepository)
    assert (tmp_path / "vims").is_dir()
