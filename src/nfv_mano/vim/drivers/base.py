"""Nf-Vi driver interface.

Drivers hide the NFVI technology from the VIM. A driver only needs to
allocate, terminate and inspect virtualised compute resources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from nfv_mano.common.lcm import ResourceState


@dataclass
class AllocatedResource:
    """Result of allocating a resource on the NFVI."""

    external_id: str
    ip_address: str | None = None
    state: ResourceState = ResourceState.RUNNING
    extra: dict[str, Any] = field(default_factory=dict)


class VimDriver(ABC):
    """Abstract Nf-Vi driver for virtualised compute resources."""

    @abstractmethod
    def allocate(
        self, *, image: str, num_cpus: int, mem_size: str, name: str | None = None
    ) -> AllocatedResource:
        """Allocate a compute resource and return its NFVI identity."""

    @abstractmethod
    def terminate(self, external_id: str) -> None:
        """Destroy a previously allocated resource."""

    @abstractmethod
    def status(self, external_id: str) -> ResourceState:
        """Return the current state of a resource."""

    @abstractmethod
    def ip_address(self, external_id: str) -> str | None:
        """Return the management IP of a resource, if any."""
