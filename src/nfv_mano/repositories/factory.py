"""Factory that builds repositories according to the configured backend.

The rest of the code only depends on the :class:`~nfv_mano.repositories.base.Repository`
interface. Switching from the ephemeral in-memory backend to a persistent file
backend (or, in the future, a replicated etcd/Raft backend) is a configuration
change, not a code change.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from nfv_mano.common.models import (
    NfviResource,
    Nsd,
    NsInstance,
    VimInfo,
    Vnfd,
    VnfInstance,
)
from nfv_mano.config import Settings
from nfv_mano.repositories.backends import FileRepository, MemoryRepository
from nfv_mano.repositories.base import Repository

VNF_CATALOG = "vnf_catalog"
NS_CATALOG = "ns_catalog"
VNF_INSTANCES = "vnf_instances"
NS_INSTANCES = "ns_instances"
NFVI_RESOURCES = "nfvi_resources"
VIMS = "vims"


def build_repository[T: BaseModel](
    model: type[T], collection: str, settings: Settings
) -> Repository[T]:
    """Build a repository for ``model`` using the configured backend."""
    if settings.repository_backend == "file":
        return FileRepository(model, collection, settings.data_dir)
    return MemoryRepository(model, collection)


@dataclass(frozen=True)
class RepositorySet:
    """The four ETSI repositories plus the registered VIMs."""

    vnf_catalog: Repository[Vnfd]
    ns_catalog: Repository[Nsd]
    vnf_instances: Repository[VnfInstance]
    ns_instances: Repository[NsInstance]
    nfvi_resources: Repository[NfviResource]
    vims: Repository[VimInfo]


def build_repositories(settings: Settings) -> RepositorySet:
    """Build every ETSI repository for the given settings."""
    return RepositorySet(
        vnf_catalog=build_repository(Vnfd, VNF_CATALOG, settings),
        ns_catalog=build_repository(Nsd, NS_CATALOG, settings),
        vnf_instances=build_repository(VnfInstance, VNF_INSTANCES, settings),
        ns_instances=build_repository(NsInstance, NS_INSTANCES, settings),
        nfvi_resources=build_repository(NfviResource, NFVI_RESOURCES, settings),
        vims=build_repository(VimInfo, VIMS, settings),
    )
