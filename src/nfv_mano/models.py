"""ETSI data models and lifecycle states.

Kept close to the ETSI naming (GS NFV-SOL 001/002/003/005) so the API can
evolve to the standard schemas later.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from nfv_mano.common import generate_id


class InstantiationState(StrEnum):
    NOT_INSTANTIATED = "NOT_INSTANTIATED"
    INSTANTIATED = "INSTANTIATED"


class ResourceState(StrEnum):
    NOT_CREATED = "NOT_CREATED"
    CREATING = "CREATING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    DELETING = "DELETING"
    DELETED = "DELETED"
    FAILED = "FAILED"


def utcnow() -> datetime:
    return datetime.now(UTC)


class VirtualCompute(BaseModel):
    image: str
    num_cpus: int = Field(default=1, ge=1)
    mem_size: str = "256m"


class Vnfd(BaseModel):
    """VNF Descriptor (VNF Catalog)."""

    id: str = Field(default_factory=lambda: generate_id("vnfd-"))
    name: str
    version: str = "1.0"
    description: str = ""
    provider: str = ""
    virtual_compute: VirtualCompute
    metadata: dict[str, Any] = Field(default_factory=dict)


class Nsd(BaseModel):
    """Network Service Descriptor (NS Catalog)."""

    id: str = Field(default_factory=lambda: generate_id("nsd-"))
    name: str
    version: str = "1.0"
    description: str = ""
    provider: str = ""
    vnfd_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VimInfo(BaseModel):
    """A registered VIM."""

    id: str = Field(default_factory=lambda: generate_id("vim-"))
    name: str
    vim_type: str = "docker"
    url: str = ""
    description: str = ""


class NfviResource(BaseModel):
    """A virtualised resource allocated by a VIM."""

    id: str = Field(default_factory=lambda: generate_id("res-"))
    vim_id: str
    resource_type: str = "virtual_compute"
    external_id: str | None = None
    image: str | None = None
    num_cpus: int | None = None
    mem_size: str | None = None
    ip_address: str | None = None
    state: ResourceState = ResourceState.NOT_CREATED
    metadata: dict[str, Any] = Field(default_factory=dict)


class VnfInstance(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("vnf-"))
    vnfd_id: str
    vnfm_id: str
    instantiation_state: InstantiationState = InstantiationState.NOT_INSTANTIATED
    vim_resource_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("vim_resource_ids")
    @classmethod
    def _no_duplicate_resources(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("vim_resource_ids must not contain duplicates")
        return value


class NsInstance(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("ns-"))
    nsd_id: str
    name: str = ""
    instantiation_state: InstantiationState = InstantiationState.NOT_INSTANTIATED
    vnf_instance_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
