"""Factory that builds the configured Nf-Vi driver."""

from __future__ import annotations

from nfv_mano.config import Settings
from nfv_mano.vim.drivers.base import VimDriver
from nfv_mano.vim.drivers.docker_driver import DockerDriver
from nfv_mano.vim.drivers.mock_driver import MockDriver


def build_driver(settings: Settings) -> VimDriver:
    """Build the VIM driver selected by ``settings.vim_driver``."""
    if settings.vim_driver == "docker":
        return DockerDriver(network=settings.docker_network)
    return MockDriver()
