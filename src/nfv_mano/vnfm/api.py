"""VNFM HTTP API.

Exposes the ``Or-Vnfm`` reference point used by the NFVO to manage VNF
instances, plus a read-only ``Ve-Vnfm-em`` view for an Element Manager.

The ``Ve-Vnfm-vnf`` reference point (direct VNF interaction) is not part of the
base and is left as future work.
"""

from __future__ import annotations

from fastapi import FastAPI, status
from pydantic import BaseModel

from nfv_mano.common.api import register_exception_handlers
from nfv_mano.common.models import VirtualCompute, VnfInstance
from nfv_mano.config import Settings, get_settings
from nfv_mano.repositories.factory import build_repositories
from nfv_mano.vnfm.manager import VnfmManager
from nfv_mano.vnfm.vim_client import VimClient


class InstantiateVnfRequest(BaseModel):
    """Payload of a VNF instantiation request on ``Or-Vnfm``."""

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

    app = FastAPI(
        title="NFV-MANO VNFM",
        version="0.1.0",
        description="VNF Manager (Or-Vnfm and Ve-Vnfm-em reference points)",
    )
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

    @app.get("/ve/vnf_instances", response_model=list[VnfInstance], tags=["ve-vnfm-em"])
    def em_list_vnf_instances() -> list[VnfInstance]:
        return manager.list_vnfs()

    @app.get("/ve/vnf_instances/{instance_id}", response_model=VnfInstance, tags=["ve-vnfm-em"])
    def em_get_vnf_instance(instance_id: str) -> VnfInstance:
        return manager.get_vnf(instance_id)

    return app


app = create_app()
