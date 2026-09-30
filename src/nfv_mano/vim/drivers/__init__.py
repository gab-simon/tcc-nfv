"""VIM drivers implementing the Nf-Vi interface.

A driver abstracts the concrete NFVI technology. The base ships a ``mock``
driver (in-memory, for tests and demos) and a ``docker`` driver (real
containers). Adding another NFVI backend means adding another driver, without
touching the VIM logic.
"""

from nfv_mano.vim.drivers.base import AllocatedResource, VimDriver
from nfv_mano.vim.drivers.docker_driver import DockerDriver
from nfv_mano.vim.drivers.factory import build_driver
from nfv_mano.vim.drivers.mock_driver import MockDriver

__all__ = [
    "AllocatedResource",
    "DockerDriver",
    "MockDriver",
    "VimDriver",
    "build_driver",
]
