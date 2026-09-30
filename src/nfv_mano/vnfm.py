"""VNFM (VNF Manager).

Performs VNF lifecycle management on the ``Or-Vnfm`` reference point and
allocates NFVI resources on the VIM through ``Vi-Vnfm``.
"""

import httpx
from fastapi import FastAPI, status
from pydantic import BaseModel

from nfv_mano.common import (
    InvalidStateError,
    VimClientError,
    configure_logging,
    register_exception_handlers,
)
from nfv_mano.config import Settings, get_settings
from nfv_mano.models import InstantiationState, VirtualCompute, VnfInstance
from nfv_mano.repositories import Repository, build_repositories

logger = configure_logging("vnfm")


class VimClient:
    """Client for the VIM resource API (``Vi-Vnfm``)."""

    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=10.0)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VimClientError(f"VIM call {method} {path} failed: {exc}") from exc
        return response.json()

    def allocate_compute(self, *, image: str, num_cpus: int, mem_size: str, vim_id=None) -> dict:
        payload = {"image": image, "num_cpus": num_cpus, "mem_size": mem_size, "vim_id": vim_id}
        return self._request("POST", "/vi/resources", json=payload)

    def get_resource(self, resource_id: str) -> dict:
        return self._request("GET", f"/vi/resources/{resource_id}")

    def terminate_resource(self, resource_id: str) -> dict:
        return self._request("DELETE", f"/vi/resources/{resource_id}")

    def close(self) -> None:
        self._client.close()


class VnfmManager:
    """Manages the lifecycle of VNF instances."""

    def __init__(
        self, *, instances_repo: Repository[VnfInstance], vim_client: VimClient, vnfm_id: str
    ) -> None:
        self.instances_repo = instances_repo
        self.vim_client = vim_client
        self.vnfm_id = vnfm_id

    def instantiate_vnf(
        self, *, vnfd_id: str, virtual_compute: VirtualCompute, name: str = "", vim_id=None
    ) -> VnfInstance:
        instance = VnfInstance(vnfd_id=vnfd_id, vnfm_id=self.vnfm_id, metadata={"name": name})
        self.instances_repo.add(instance)
        resource = self.vim_client.allocate_compute(
            image=virtual_compute.image,
            num_cpus=virtual_compute.num_cpus,
            mem_size=virtual_compute.mem_size,
            vim_id=vim_id,
        )
        instance.vim_resource_ids.append(resource["id"])
        instance.instantiation_state = InstantiationState.INSTANTIATED
        logger.info("instantiated VNF %s (vnfd=%s)", instance.id, vnfd_id)
        return self.instances_repo.update(instance)

    def terminate_vnf(self, instance_id: str) -> VnfInstance:
        instance = self.instances_repo.get(instance_id)
        if instance.instantiation_state is not InstantiationState.INSTANTIATED:
            raise InvalidStateError(f"VNF {instance_id!r} is not instantiated")
        for resource_id in instance.vim_resource_ids:
            self.vim_client.terminate_resource(resource_id)
        instance.instantiation_state = InstantiationState.NOT_INSTANTIATED
        logger.info("terminated VNF %s", instance_id)
        return self.instances_repo.update(instance)

    def get_vnf(self, instance_id: str) -> VnfInstance:
        return self.instances_repo.get(instance_id)

    def list_vnfs(self) -> list[VnfInstance]:
        return self.instances_repo.list()


class InstantiateVnfRequest(BaseModel):
    vnfd_id: str
    virtual_compute: VirtualCompute
    vnf_instance_name: str = ""
    vim_id: str | None = None


def create_app(
    settings: Settings | None = None,
    *,
    vim_client: VimClient | None = None,
    manager: VnfmManager | None = None,
) -> FastAPI:
    """Build the VNFM FastAPI application."""
    settings = settings or get_settings()
    if manager is None:
        repos = build_repositories(settings)
        manager = VnfmManager(
            instances_repo=repos.vnf_instances,
            vim_client=vim_client or VimClient(settings.vim_base_url),
            vnfm_id=settings.vnfm_id,
        )

    app = FastAPI(title="NFV-MANO VNFM", version="0.1.0")
    app.state.manager = manager
    register_exception_handlers(app)

    @app.get("/health", tags=["lifecycle"])
    def health() -> dict[str, str]:
        return {"status": "ok", "component": "vnfm"}

    @app.post(
        "/or/vnf_instances",
        response_model=VnfInstance,
        status_code=status.HTTP_201_CREATED,
        tags=["or-vnfm"],
    )
    def instantiate_vnf(request: InstantiateVnfRequest) -> VnfInstance:
        return manager.instantiate_vnf(
            vnfd_id=request.vnfd_id,
            virtual_compute=request.virtual_compute,
            name=request.vnf_instance_name,
            vim_id=request.vim_id,
        )

    @app.get("/or/vnf_instances", response_model=list[VnfInstance], tags=["or-vnfm"])
    def list_vnf_instances() -> list[VnfInstance]:
        return manager.list_vnfs()

    @app.get("/or/vnf_instances/{instance_id}", response_model=VnfInstance, tags=["or-vnfm"])
    def get_vnf_instance(instance_id: str) -> VnfInstance:
        return manager.get_vnf(instance_id)

    @app.delete("/or/vnf_instances/{instance_id}", response_model=VnfInstance, tags=["or-vnfm"])
    def terminate_vnf_instance(instance_id: str) -> VnfInstance:
        return manager.terminate_vnf(instance_id)

    # Ve-Vnfm-em: read-only view for an Element Manager.
    @app.get("/ve/vnf_instances", response_model=list[VnfInstance], tags=["ve-vnfm-em"])
    def em_list_vnf_instances() -> list[VnfInstance]:
        return manager.list_vnfs()

    @app.get("/ve/vnf_instances/{instance_id}", response_model=VnfInstance, tags=["ve-vnfm-em"])
    def em_get_vnf_instance(instance_id: str) -> VnfInstance:
        return manager.get_vnf(instance_id)

    return app
