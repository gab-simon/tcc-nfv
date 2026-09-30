"""In-memory Nf-Vi driver.

Simulates NFVI compute resources without any real infrastructure. It is the
default driver so the MANO base can run for tests and demos on any machine.
"""

from __future__ import annotations

from nfv_mano.common.exceptions import DriverError
from nfv_mano.common.lcm import ResourceState
from nfv_mano.vim.drivers.base import AllocatedResource, VimDriver


class MockDriver(VimDriver):
    """A driver that keeps simulated resources in memory."""

    def __init__(self) -> None:
        self._resources: dict[str, ResourceState] = {}
        self._ips: dict[str, str] = {}
        self._counter = 0

    def allocate(
        self,
        *,
        image: str,
        num_cpus: int,
        mem_size: str,
        name: str | None = None,
    ) -> AllocatedResource:
        self._counter += 1
        external_id = f"mock-{self._counter:04d}"
        ip_address = f"10.0.0.{self._counter}"

        self._resources[external_id] = ResourceState.RUNNING
        self._ips[external_id] = ip_address

        return AllocatedResource(
            external_id=external_id,
            ip_address=ip_address,
            state=ResourceState.RUNNING,
            extra={
                "image": image,
                "num_cpus": num_cpus,
                "mem_size": mem_size,
                "name": name,
            },
        )

    def terminate(self, external_id: str) -> None:
        if external_id not in self._resources:
            raise DriverError(f"mock resource {external_id!r} not found")
        del self._resources[external_id]
        self._ips.pop(external_id, None)

    def status(self, external_id: str) -> ResourceState:
        return self._resources.get(external_id, ResourceState.NOT_CREATED)

    def ip_address(self, external_id: str) -> str | None:
        return self._ips.get(external_id)
