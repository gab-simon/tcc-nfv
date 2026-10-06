"""Central configuration for all NFV-MANO components.

All settings can be overridden through environment variables using the
``NFV_MANO_`` prefix (for example ``NFV_MANO_NFVO_PORT=9100``) or a local
``.env`` file. This keeps a single source of truth for ports, storage and the
VIM driver selection.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by the NFVO, VNFM and VIM."""

    model_config = SettingsConfigDict(
        env_prefix="NFV_MANO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Who this VNFM is; it gets copied into every VNF instance it creates.
    vnfm_id: str = "vnfm-1"

    # Where each component listens (Os-Ma-nfvo, Or-Vnfm and Vi-Vnfm).
    nfvo_host: str = "127.0.0.1"
    nfvo_port: int = 9002
    vnfm_host: str = "127.0.0.1"
    vnfm_port: int = 9001
    vim_host: str = "127.0.0.1"
    vim_port: int = 9000

    # Where the state lives. ``memory`` forgets everything on restart, ``file``
    # writes JSON under ``data_dir``. The etcd/Raft backend we want later just
    # has to keep this same interface.
    repository_backend: Literal["memory", "file"] = "memory"
    data_dir: Path = Field(default=Path("data"))

    # How the VIM reaches the infrastructure: ``mock`` fakes resources in
    # memory, ``docker`` really starts containers (Nf-Vi).
    vim_driver: Literal["mock", "docker"] = "mock"
    docker_network: str = "nfv-mano-net"

    @property
    def nfvo_base_url(self) -> str:
        """Base URL exposed on the ``Os-Ma-nfvo`` reference point."""
        return f"http://{self.nfvo_host}:{self.nfvo_port}"

    @property
    def vnfm_base_url(self) -> str:
        """Base URL exposed on the ``Or-Vnfm`` reference point."""
        return f"http://{self.vnfm_host}:{self.vnfm_port}"

    @property
    def vim_base_url(self) -> str:
        """Base URL exposed on the ``Vi-Vnfm`` reference point."""
        return f"http://{self.vim_host}:{self.vim_port}"


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
