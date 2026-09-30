"""VIM HTTP API.

Exposes the ``Vi-Vnfm`` reference point (resource lifecycle requests coming
from the VNFM/NFVO) and a small view of the registered VIMs. The internal
``Nf-Vi`` calls are performed by the driver behind :class:`VimManager`.
"""

from __future__ import annotations

from fastapi import FastAPI, status
from pydantic import BaseModel, Field

from nfv_mano.common.api import register_exception_handlers
from nfv_mano.common.models import NfviResource, VimInfo
from nfv_mano.config import Settings, get_settings
from nfv_mano.repositories.factory import build_repositories
from nfv_mano.vim.drivers.base import VimDriver
from nfv_mano.vim.drivers.factory import build_driver
from nfv_mano.vim.manager import VimManager


class AllocateComputeRequest(BaseModel):
    """Payload of a compute allocation request on ``Vi-Vnfm``."""

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

    app = FastAPI(
        title="NFV-MANO VIM",
        version="0.1.0",
        description="Virtualised Infrastructure Manager (Vi-Vnfm reference point)",
    )
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

    @app.get(
        "/vi/resources/{resource_id}/status",
        response_model=NfviResource,
        tags=["resources"],
    )
    def get_resource_status(resource_id: str) -> NfviResource:
        return manager.refresh_resource(resource_id)

    @app.delete("/vi/resources/{resource_id}", response_model=NfviResource, tags=["resources"])
    def terminate_resource(resource_id: str) -> NfviResource:
        return manager.terminate_resource(resource_id)

    return app


app = create_app()
