"""NFVO HTTP API.

Exposes the ``Os-Ma-nfvo`` reference point: VNF/NS catalog management and NS
lifecycle management. Resource orchestration across multiple VIMs (``Or-Vi``)
is out of scope for the non-fault-tolerant base and is left as future work.
"""

from __future__ import annotations

from fastapi import FastAPI, status
from pydantic import BaseModel

from nfv_mano.common.api import register_exception_handlers
from nfv_mano.common.models import Nsd, NsInstance, Vnfd
from nfv_mano.config import Settings, get_settings
from nfv_mano.nfvo.manager import NfvoManager
from nfv_mano.nfvo.vnfm_client import VnfmClient
from nfv_mano.repositories.factory import build_repositories


class InstantiateNsRequest(BaseModel):
    """Payload of a Network Service instantiation request."""

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

    app = FastAPI(
        title="NFV-MANO NFVO",
        version="0.1.0",
        description="NFV Orchestrator (Os-Ma-nfvo reference point)",
    )
    app.state.manager = manager
    register_exception_handlers(app)

    @app.get("/health", tags=["lifecycle"])
    def health() -> dict[str, str]:
        return {"status": "ok", "component": "nfvo"}

    @app.post(
        "/os/vnfds",
        response_model=Vnfd,
        status_code=status.HTTP_201_CREATED,
        tags=["vnf-catalog"],
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
        "/os/nsds",
        response_model=Nsd,
        status_code=status.HTTP_201_CREATED,
        tags=["ns-catalog"],
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
        return manager.instantiate_ns(
            nsd_id=request.nsd_id,
            name=request.ns_instance_name,
        )

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


app = create_app()
