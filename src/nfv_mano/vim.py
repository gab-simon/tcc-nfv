"""VIM (Virtualised Infrastructure Manager).

Manages NFVI compute resources on the ``Vi-Vnfm`` reference point and talks to
the infrastructure through an ``Nf-Vi`` driver (mock or Docker).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, status
from pydantic import BaseModel, Field

from nfv_mano.common import (
    DriverError,
    InvalidStateError,
    configure_logging,
    register_exception_handlers,
)
from nfv_mano.config import Settings, get_settings
from nfv_mano.models import NfviResource, ResourceState, VimInfo
from nfv_mano.repositories import Repository, build_repositories

logger = configure_logging("vim")


# --- Nf-Vi drivers --------------------------------------------------------
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
    ) -> AllocatedResource: ...

    @abstractmethod
    def terminate(self, external_id: str) -> None: ...

    @abstractmethod
    def status(self, external_id: str) -> ResourceState: ...

    @abstractmethod
    def ip_address(self, external_id: str) -> str | None: ...


class MockDriver(VimDriver):
    """Simulates NFVI resources in memory."""

    def __init__(self) -> None:
        self._resources: dict[str, ResourceState] = {}
        self._ips: dict[str, str] = {}
        self._counter = 0

    def allocate(self, *, image, num_cpus, mem_size, name=None) -> AllocatedResource:
        self._counter += 1
        external_id = f"mock-{self._counter:04d}"
        ip_address = f"10.0.0.{self._counter}"
        self._resources[external_id] = ResourceState.RUNNING
        self._ips[external_id] = ip_address
        return AllocatedResource(
            external_id=external_id,
            ip_address=ip_address,
            extra={"image": image, "num_cpus": num_cpus, "mem_size": mem_size, "name": name},
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


_STATUS_MAP = {
    "created": ResourceState.CREATING,
    "running": ResourceState.RUNNING,
    "paused": ResourceState.STOPPED,
    "restarting": ResourceState.CREATING,
    "removing": ResourceState.DELETING,
    "exited": ResourceState.STOPPED,
    "dead": ResourceState.FAILED,
}


class DockerDriver(VimDriver):
    """Manages NFVI resources as Docker containers."""

    def __init__(self, network: str | None = None) -> None:
        self.network = network
        self._client: Any | None = None

    def _docker(self) -> Any:
        import docker

        if self._client is None:
            try:
                self._client = docker.from_env()
            except Exception as exc:
                raise DriverError(f"could not connect to the Docker daemon: {exc}") from exc
        return self._client

    def allocate(self, *, image, num_cpus, mem_size, name=None) -> AllocatedResource:
        import docker

        try:
            container = self._docker().containers.run(
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
            extra={"short_id": container.short_id, "image": image},
        )

    def terminate(self, external_id: str) -> None:
        import docker

        try:
            container = self._docker().containers.get(external_id)
        except docker.errors.NotFound:
            return
        try:
            container.remove(force=True)
        except docker.errors.APIError as exc:
            raise DriverError(f"failed to remove container {external_id!r}: {exc}") from exc

    def status(self, external_id: str) -> ResourceState:
        import docker

        try:
            container = self._docker().containers.get(external_id)
        except docker.errors.NotFound:
            return ResourceState.NOT_CREATED
        return _STATUS_MAP.get(container.status, ResourceState.FAILED)

    def ip_address(self, external_id: str) -> str | None:
        import docker

        try:
            container = self._docker().containers.get(external_id)
        except docker.errors.NotFound:
            return None
        return self._ip_of(container)

    @staticmethod
    def _ip_of(container: Any) -> str | None:
        for settings in container.attrs.get("NetworkSettings", {}).get("Networks", {}).values():
            if ip := settings.get("IPAddress"):
                return ip
        return None


def build_driver(settings: Settings) -> VimDriver:
    if settings.vim_driver == "docker":
        return DockerDriver(network=settings.docker_network)
    return MockDriver()


# --- VIM manager ----------------------------------------------------------
class VimManager:
    """Manages NFVI compute resources and registered VIMs."""

    def __init__(
        self,
        *,
        driver: VimDriver,
        resources_repo: Repository[NfviResource],
        vims_repo: Repository[VimInfo],
        settings: Settings,
    ) -> None:
        self.driver = driver
        self.resources_repo = resources_repo
        self.vims_repo = vims_repo
        self.settings = settings
        self.ensure_default_vim()

    def ensure_default_vim(self) -> VimInfo:
        existing = self.vims_repo.list()
        if existing:
            return existing[0]
        vim = VimInfo(
            name="default-vim",
            vim_type=self.settings.vim_driver,
            url=self.settings.vim_base_url,
            description=f"Local {self.settings.vim_driver} VIM",
        )
        return self.vims_repo.add(vim)

    @property
    def default_vim_id(self) -> str:
        return self.vims_repo.list()[0].id

    def list_vims(self) -> list[VimInfo]:
        return self.vims_repo.list()

    def get_vim(self, vim_id: str) -> VimInfo:
        return self.vims_repo.get(vim_id)

    def allocate_compute(
        self, *, image: str, num_cpus: int, mem_size: str, vim_id: str | None = None
    ) -> NfviResource:
        """Allocate a virtualised compute resource through the driver."""
        target_vim = vim_id or self.default_vim_id
        self.vims_repo.get(target_vim)

        resource = NfviResource(
            vim_id=target_vim,
            image=image,
            num_cpus=num_cpus,
            mem_size=mem_size,
            state=ResourceState.CREATING,
        )
        self.resources_repo.add(resource)
        try:
            allocated = self.driver.allocate(
                image=image, num_cpus=num_cpus, mem_size=mem_size, name=resource.id
            )
        except Exception:
            resource.state = ResourceState.FAILED
            self.resources_repo.update(resource)
            logger.exception("allocation failed for resource %s", resource.id)
            raise

        resource.external_id = allocated.external_id
        resource.ip_address = allocated.ip_address
        resource.state = allocated.state
        resource.metadata.update(allocated.extra)
        return self.resources_repo.update(resource)

    def list_resources(self) -> list[NfviResource]:
        return self.resources_repo.list()

    def get_resource(self, resource_id: str) -> NfviResource:
        return self.resources_repo.get(resource_id)

    def refresh_resource(self, resource_id: str) -> NfviResource:
        resource = self.resources_repo.get(resource_id)
        if resource.external_id is not None:
            resource.state = self.driver.status(resource.external_id)
            resource.ip_address = self.driver.ip_address(resource.external_id)
            self.resources_repo.update(resource)
        return resource

    def terminate_resource(self, resource_id: str) -> NfviResource:
        resource = self.resources_repo.get(resource_id)
        if resource.state is ResourceState.DELETED:
            raise InvalidStateError(f"resource {resource_id!r} is already deleted")
        resource.state = ResourceState.DELETING
        self.resources_repo.update(resource)
        if resource.external_id is not None:
            self.driver.terminate(resource.external_id)
        resource.state = ResourceState.DELETED
        return self.resources_repo.update(resource)


# --- Vi-Vnfm API ----------------------------------------------------------
class AllocateComputeRequest(BaseModel):
    image: str
    num_cpus: int = Field(default=1, ge=1)
    mem_size: str = "256m"
    vim_id: str | None = None


def create_app(settings: Settings | None = None, driver: VimDriver | None = None) -> FastAPI:
    """Build the VIM FastAPI application."""
    settings = settings or get_settings()
    repos = build_repositories(settings)
    manager = VimManager(
        driver=driver or build_driver(settings),
        resources_repo=repos.nfvi_resources,
        vims_repo=repos.vims,
        settings=settings,
    )

    app = FastAPI(title="NFV-MANO VIM", version="0.1.0")
    app.state.manager = manager
    register_exception_handlers(app)

    @app.get("/health", tags=["lifecycle"])
    def health() -> dict[str, str]:
        return {"status": "ok", "component": "vim"}

    @app.get("/vi/vims", response_model=list[VimInfo], tags=["inventory"])
    def list_vims() -> list[VimInfo]:
        return manager.list_vims()

    @app.get("/vi/vims/{vim_id}", response_model=VimInfo, tags=["inventory"])
    def get_vim(vim_id: str) -> VimInfo:
        return manager.get_vim(vim_id)

    @app.post(
        "/vi/resources",
        response_model=NfviResource,
        status_code=status.HTTP_201_CREATED,
        tags=["resources"],
    )
    def allocate_resource(request: AllocateComputeRequest) -> NfviResource:
        return manager.allocate_compute(
            image=request.image,
            num_cpus=request.num_cpus,
            mem_size=request.mem_size,
            vim_id=request.vim_id,
        )

    @app.get("/vi/resources", response_model=list[NfviResource], tags=["resources"])
    def list_resources() -> list[NfviResource]:
        return manager.list_resources()

    @app.get("/vi/resources/{resource_id}", response_model=NfviResource, tags=["resources"])
    def get_resource(resource_id: str) -> NfviResource:
        return manager.get_resource(resource_id)

    @app.get("/vi/resources/{resource_id}/status", response_model=NfviResource, tags=["resources"])
    def get_resource_status(resource_id: str) -> NfviResource:
        return manager.refresh_resource(resource_id)

    @app.delete("/vi/resources/{resource_id}", response_model=NfviResource, tags=["resources"])
    def terminate_resource(resource_id: str) -> NfviResource:
        return manager.terminate_resource(resource_id)

    return app
