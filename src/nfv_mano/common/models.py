"""Data models aligned with the ETSI NFV information model.

The models are intentionally small but keep the ETSI naming so they can grow
towards the full IFA/SOL schemas:

* ``Vnfd`` / ``Nsd``            - catalogue descriptors (GS NFV-SOL 001/002).
* ``VnfInstance`` / ``NsInstance`` - instantiated entities (GS NFV-SOL 003/005).
* ``NfviResource``              - NFVI resources tracked by the VIM.
* ``VimInfo``                   - a registered VIM.
* ``LcmOperationOccurrence``    - a lifecycle operation and its state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from nfv_mano.common.ids import generate_id
from nfv_mano.common.lcm import (
    InstantiationState,
    LcmOperationState,
    LcmOperationType,
    ResourceState,
)


def utcnow() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)


class VirtualCompute(BaseModel):
    """Compute requirements/attributes of a virtualised container (VDU)."""

    image: str
    num_cpus: int = Field(default=1, ge=1)
    mem_size: str = "256m"


class Vnfd(BaseModel):
    """VNF Descriptor as stored in the VNF Catalog."""

    id: str = Field(default_factory=lambda: generate_id("vnfd-"))
    name: str
    version: str = "1.0"
    description: str = ""
    provider: str = ""
    virtual_compute: VirtualCompute
    metadata: dict[str, Any] = Field(default_factory=dict)


class Nsd(BaseModel):
    """Network Service Descriptor as stored in the NS Catalog."""

    id: str = Field(default_factory=lambda: generate_id("nsd-"))
    name: str
    version: str = "1.0"
    description: str = ""
    provider: str = ""
    vnfd_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VimInfo(BaseModel):
    """A VIM registered in the NFVI Resources repository."""

    id: str = Field(default_factory=lambda: generate_id("vim-"))
    name: str
    vim_type: str = "docker"
    url: str = ""
    description: str = ""


class NfviResource(BaseModel):
    """A virtualised resource allocated by a VIM (compute, storage, network)."""

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


class LcmOperationOccurrence(BaseModel):
    """An LCM operation occurrence and its current state."""

    id: str = Field(default_factory=lambda: generate_id("lcm-"))
    operation: LcmOperationType
    target_id: str
    state: LcmOperationState = LcmOperationState.STARTING
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def touch(self) -> None:
        """Refresh ``updated_at`` after a state change."""
        self.updated_at = utcnow()


class VnfInstance(BaseModel):
    """An instantiated VNF managed by a VNFM."""

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
    """An instantiated Network Service managed by the NFVO."""

    id: str = Field(default_factory=lambda: generate_id("ns-"))
    nsd_id: str
    name: str = ""
    instantiation_state: InstantiationState = InstantiationState.NOT_INSTANTIATED
    vnf_instance_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
