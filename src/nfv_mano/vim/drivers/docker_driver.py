"""Docker-based Nf-Vi driver.

Manages NFVI compute resources as Docker containers, mirroring the reference
implementations. The Docker client is created lazily so importing this module
never requires a running daemon.
"""

from __future__ import annotations

from typing import Any

from nfv_mano.common.exceptions import DriverError
from nfv_mano.common.lcm import ResourceState
from nfv_mano.vim.drivers.base import AllocatedResource, VimDriver

_STATUS_MAP: dict[str, ResourceState] = {
    "created": ResourceState.CREATING,
    "running": ResourceState.RUNNING,
    "paused": ResourceState.STOPPED,
    "restarting": ResourceState.CREATING,
    "removing": ResourceState.DELETING,
    "exited": ResourceState.STOPPED,
    "dead": ResourceState.FAILED,
}


class DockerDriver(VimDriver):
    """A driver backed by the local Docker daemon."""

    def __init__(self, network: str | None = None) -> None:
        self.network = network
        self._client: Any | None = None

    def _docker(self) -> Any:
        """Return a Docker client, connecting on first use."""
        if self._client is None:
            import docker

            try:
                self._client = docker.from_env()
            except Exception as exc:  # pragma: no cover - depends on environment
                raise DriverError(f"could not connect to the Docker daemon: {exc}") from exc
        return self._client

    def allocate(
        self,
        *,
        image: str,
        num_cpus: int,
        mem_size: str,
        name: str | None = None,
    ) -> AllocatedResource:
        import docker

        client = self._docker()
        try:
            container = client.containers.run(
                image,
                name=name,
                detach=True,
                cpu_count=num_cpus,
                mem_limit=mem_size,
                stdin_open=True,
            )
        except docker.errors.APIError as exc:
            raise DriverError(f"failed to start container from {image!r}: {exc}") from exc

        return AllocatedResource(
            external_id=container.id,
            ip_address=self._ip_of(container),
            state=ResourceState.RUNNING,
            extra={"short_id": container.short_id, "image": image},
        )

    def terminate(self, external_id: str) -> None:
        import docker

        client = self._docker()
        try:
            container = client.containers.get(external_id)
        except docker.errors.NotFound:
            return
        try:
            container.remove(force=True)
        except docker.errors.APIError as exc:
            raise DriverError(f"failed to remove container {external_id!r}: {exc}") from exc

    def status(self, external_id: str) -> ResourceState:
        import docker

        client = self._docker()
        try:
            container = client.containers.get(external_id)
        except docker.errors.NotFound:
            return ResourceState.NOT_CREATED
        return _STATUS_MAP.get(container.status, ResourceState.FAILED)

    def ip_address(self, external_id: str) -> str | None:
        import docker

        client = self._docker()
        try:
            container = client.containers.get(external_id)
        except docker.errors.NotFound:
            return None
        return self._ip_of(container)

    @staticmethod
    def _ip_of(container: Any) -> str | None:
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        for settings in networks.values():
            ip = settings.get("IPAddress")
            if ip:
                return ip
        return None
