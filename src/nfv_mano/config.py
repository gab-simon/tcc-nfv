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

    # Identity assigned to the VNFM instance (stored on VNF instances).
    vnfm_id: str = "vnfm-1"

    # Reference point bind addresses (ETSI: Os-Ma-nfvo, Or-Vnfm, Vi-Vnfm).
    nfvo_host: str = "127.0.0.1"
    nfvo_port: int = 9002
    vnfm_host: str = "127.0.0.1"
    vnfm_port: int = 9001
    vim_host: str = "127.0.0.1"
    vim_port: int = 9000

    # ETSI data repositories backend. ``memory`` is ephemeral, ``file`` persists
    # JSON documents under ``data_dir``. A distributed backend (etcd/Raft) is
    # planned as future work and must implement the same interface.
    repository_backend: Literal["memory", "file"] = "memory"
    data_dir: Path = Field(default=Path("data"))

    # VIM driver. ``mock`` simulates NFVI resources in memory; ``docker``
    # really manages containers through the Docker daemon (Nf-Vi).
    vim_driver: Literal["mock", "docker"] = "mock"
    docker_network: str = "nfv-mano-net"
    default_vnf_image: str = "alpine:latest"

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
