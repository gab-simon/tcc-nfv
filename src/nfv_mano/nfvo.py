"""NFVO (NFV Orchestrator).

Owns the VNF/NS catalogs and orchestrates Network Services on the
``Os-Ma-nfvo`` reference point, driving VNFs through the VNFM (``Or-Vnfm``).
"""

import httpx
from fastapi import FastAPI, status
from pydantic import BaseModel

from nfv_mano.common import (
    InvalidStateError,
    NotFoundError,
    VnfmClientError,
    configure_logging,
    register_exception_handlers,
)
from nfv_mano.config import Settings, get_settings
from nfv_mano.models import InstantiationState, Nsd, NsInstance, Vnfd
from nfv_mano.repositories import Repository, build_repositories

logger = configure_logging("nfvo")


class VnfmClient:
    """Client for the VNFM lifecycle API (``Or-Vnfm``)."""

    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=10.0)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VnfmClientError(f"VNFM call {method} {path} failed: {exc}") from exc
        return response.json()

    def instantiate_vnf(
        self, *, vnfd_id: str, virtual_compute: dict, vnf_instance_name: str = "", vim_id=None
    ) -> dict:
        payload = {
            "vnfd_id": vnfd_id,
            "virtual_compute": virtual_compute,
            "vnf_instance_name": vnf_instance_name,
            "vim_id": vim_id,
        }
        return self._request("POST", "/or/vnf_instances", json=payload)

    def get_vnf(self, instance_id: str) -> dict:
        return self._request("GET", f"/or/vnf_instances/{instance_id}")

    def terminate_vnf(self, instance_id: str) -> dict:
        return self._request("DELETE", f"/or/vnf_instances/{instance_id}")

    def close(self) -> None:
        self._client.close()


class NfvoManager:
    """Owns the catalogs and orchestrates Network Services."""

    def __init__(
        self,
        *,
        vnf_catalog: Repository[Vnfd],
        ns_catalog: Repository[Nsd],
        ns_instances_repo: Repository[NsInstance],
        vnfm_client: VnfmClient,
    ) -> None:
        self.vnf_catalog = vnf_catalog
        self.ns_catalog = ns_catalog
        self.ns_instances_repo = ns_instances_repo
        self.vnfm_client = vnfm_client

    # Catalogues
    def register_vnfd(self, vnfd: Vnfd) -> Vnfd:
        logger.info("registering VNFD %s", vnfd.id)
        return self.vnf_catalog.add(vnfd)

    def register_nsd(self, nsd: Nsd) -> Nsd:
        for vnfd_id in nsd.vnfd_ids:
            if not self.vnf_catalog.exists(vnfd_id):
                raise NotFoundError(f"NSD references unknown VNFD {vnfd_id!r}")
        logger.info("registering NSD %s", nsd.id)
        return self.ns_catalog.add(nsd)

    def list_vnfds(self) -> list[Vnfd]:
        return self.vnf_catalog.list()

    def get_vnfd(self, vnfd_id: str) -> Vnfd:
        return self.vnf_catalog.get(vnfd_id)

    def list_nsds(self) -> list[Nsd]:
        return self.ns_catalog.list()

    def get_nsd(self, nsd_id: str) -> Nsd:
        return self.ns_catalog.get(nsd_id)

    # NS lifecycle
    def instantiate_ns(self, *, nsd_id: str, name: str = "") -> NsInstance:
        nsd = self.ns_catalog.get(nsd_id)
        instance = NsInstance(nsd_id=nsd_id, name=name)
        self.ns_instances_repo.add(instance)

        created_vnfs: list[str] = []
        try:
            for index, vnfd_id in enumerate(nsd.vnfd_ids, start=1):
                vnfd = self.vnf_catalog.get(vnfd_id)
                vnf = self.vnfm_client.instantiate_vnf(
                    vnfd_id=vnfd.id,
                    virtual_compute=vnfd.virtual_compute.model_dump(),
                    vnf_instance_name=f"{name or nsd.name}-vnf-{index}",
                )
                created_vnfs.append(vnf["id"])
        except Exception:
            logger.exception("NS %s instantiation failed, rolling back", instance.id)
            for vnf_id in created_vnfs:
                try:
                    self.vnfm_client.terminate_vnf(vnf_id)
                except Exception:
                    logger.exception("failed to roll back VNF %s", vnf_id)
            raise

        instance.vnf_instance_ids = created_vnfs
        instance.instantiation_state = InstantiationState.INSTANTIATED
        logger.info("instantiated NS %s with %d VNF(s)", instance.id, len(created_vnfs))
        return self.ns_instances_repo.update(instance)

    def terminate_ns(self, instance_id: str) -> NsInstance:
        instance = self.ns_instances_repo.get(instance_id)
        if instance.instantiation_state is not InstantiationState.INSTANTIATED:
            raise InvalidStateError(f"NS {instance_id!r} is not instantiated")
        for vnf_id in instance.vnf_instance_ids:
            self.vnfm_client.terminate_vnf(vnf_id)
        instance.instantiation_state = InstantiationState.NOT_INSTANTIATED
        logger.info("terminated NS %s", instance_id)
        return self.ns_instances_repo.update(instance)

    def get_ns(self, instance_id: str) -> NsInstance:
        return self.ns_instances_repo.get(instance_id)

    def list_ns(self) -> list[NsInstance]:
        return self.ns_instances_repo.list()


class InstantiateNsRequest(BaseModel):
    nsd_id: str
    ns_instance_name: str = ""


def create_app(
    settings: Settings | None = None,
    *,
    vnfm_client: VnfmClient | None = None,
    manager: NfvoManager | None = None,
) -> FastAPI:
    """Build the NFVO FastAPI application."""
    settings = settings or get_settings()
    if manager is None:
        repos = build_repositories(settings)
        manager = NfvoManager(
            vnf_catalog=repos.vnf_catalog,
            ns_catalog=repos.ns_catalog,
            ns_instances_repo=repos.ns_instances,
            vnfm_client=vnfm_client or VnfmClient(settings.vnfm_base_url),
        )

    app = FastAPI(title="NFV-MANO NFVO", version="0.1.0")
    app.state.manager = manager
    register_exception_handlers(app)

    @app.get("/health", tags=["lifecycle"])
    def health() -> dict[str, str]:
        return {"status": "ok", "component": "nfvo"}

    @app.post(
        "/os/vnfds", response_model=Vnfd, status_code=status.HTTP_201_CREATED, tags=["vnf-catalog"]
    )
    def register_vnfd(vnfd: Vnfd) -> Vnfd:
        return manager.register_vnfd(vnfd)

    @app.get("/os/vnfds", response_model=list[Vnfd], tags=["vnf-catalog"])
    def list_vnfds() -> list[Vnfd]:
        return manager.list_vnfds()

    @app.get("/os/vnfds/{vnfd_id}", response_model=Vnfd, tags=["vnf-catalog"])
    def get_vnfd(vnfd_id: str) -> Vnfd:
        return manager.get_vnfd(vnfd_id)

    @app.post(
        "/os/nsds", response_model=Nsd, status_code=status.HTTP_201_CREATED, tags=["ns-catalog"]
    )
    def register_nsd(nsd: Nsd) -> Nsd:
        return manager.register_nsd(nsd)

    @app.get("/os/nsds", response_model=list[Nsd], tags=["ns-catalog"])
    def list_nsds() -> list[Nsd]:
        return manager.list_nsds()

    @app.get("/os/nsds/{nsd_id}", response_model=Nsd, tags=["ns-catalog"])
    def get_nsd(nsd_id: str) -> Nsd:
        return manager.get_nsd(nsd_id)

    @app.post(
        "/os/ns_instances",
        response_model=NsInstance,
        status_code=status.HTTP_201_CREATED,
        tags=["ns-lcm"],
    )
    def instantiate_ns(request: InstantiateNsRequest) -> NsInstance:
        return manager.instantiate_ns(nsd_id=request.nsd_id, name=request.ns_instance_name)

    @app.get("/os/ns_instances", response_model=list[NsInstance], tags=["ns-lcm"])
    def list_ns_instances() -> list[NsInstance]:
        return manager.list_ns()

    @app.get("/os/ns_instances/{instance_id}", response_model=NsInstance, tags=["ns-lcm"])
    def get_ns_instance(instance_id: str) -> NsInstance:
        return manager.get_ns(instance_id)

    @app.delete("/os/ns_instances/{instance_id}", response_model=NsInstance, tags=["ns-lcm"])
    def terminate_ns_instance(instance_id: str) -> NsInstance:
        return manager.terminate_ns(instance_id)

    return app
