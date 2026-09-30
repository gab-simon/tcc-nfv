"""Tests for the configuration layer."""

from __future__ import annotations

from pathlib import Path

from nfv_mano.config import Settings, get_settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.nfvo_port == 9002
    assert settings.vnfm_port == 9001
    assert settings.vim_port == 9000
    assert settings.repository_backend == "memory"
    assert settings.vim_driver == "mock"


def test_reference_point_urls() -> None:
    settings = Settings(_env_file=None)
    assert settings.nfvo_base_url == "http://127.0.0.1:9002"
    assert settings.vnfm_base_url == "http://127.0.0.1:9001"
    assert settings.vim_base_url == "http://127.0.0.1:9000"


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("NFV_MANO_NFVO_PORT", "9100")
    monkeypatch.setenv("NFV_MANO_REPOSITORY_BACKEND", "file")
    monkeypatch.setenv("NFV_MANO_DATA_DIR", "/tmp/nfv-mano-test")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.nfvo_port == 9100
    assert settings.repository_backend == "file"
    assert settings.data_dir == Path("/tmp/nfv-mano-test")
    get_settings.cache_clear()
