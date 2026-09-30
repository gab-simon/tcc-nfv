"""Tests for the repository factory."""

from __future__ import annotations

from nfv_mano.config import Settings
from nfv_mano.repositories.backends import FileRepository, MemoryRepository
from nfv_mano.repositories.factory import build_repositories


def test_memory_backend() -> None:
    repos = build_repositories(Settings(_env_file=None, repository_backend="memory"))
    assert isinstance(repos.vnf_catalog, MemoryRepository)
    assert isinstance(repos.nfvi_resources, MemoryRepository)


def test_file_backend(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        repository_backend="file",
        data_dir=tmp_path,
    )
    repos = build_repositories(settings)

    assert isinstance(repos.vnf_catalog, FileRepository)
    assert (tmp_path / "vnf_catalog").is_dir()
    assert (tmp_path / "vims").is_dir()
