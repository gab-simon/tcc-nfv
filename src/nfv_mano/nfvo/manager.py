"""Network Service lifecycle management performed by the NFVO.

The NFVO composes Network Services from VNF descriptors: instantiating an NS
means asking the VNFM to instantiate every VNF referenced by the NSD, then
tracking the resulting VNF instance ids.
"""

from __future__ import annotations

from nfv_mano.common.exceptions import InvalidStateError, NotFoundError
from nfv_mano.common.lcm import InstantiationState
from nfv_mano.common.logging import configure_logging
from nfv_mano.common.models import Nsd, NsInstance, Vnfd
from nfv_mano.nfvo.vnfm_client import VnfmClient
from nfv_mano.repositories.base import Repository

logger = configure_logging("nfvo")


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

    # --- Catalogues -------------------------------------------------------
    def register_vnfd(self, vnfd: Vnfd) -> Vnfd:
        logger.info("registering VNFD %s", vnfd.id)
        return self.vnf_catalog.add(vnfd)

    def register_nsd(self, nsd: Nsd) -> Nsd:
        """Register an NSD, ensuring all referenced VNFDs exist."""
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

    # --- NS lifecycle -----------------------------------------------------
    def instantiate_ns(self, *, nsd_id: str, name: str = "") -> NsInstance:
        """Instantiate a Network Service and all of its VNFs."""
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
                except Exception:  # pragma: no cover - best effort rollback
                    logger.exception("failed to roll back VNF %s", vnf_id)
            raise

        instance.vnf_instance_ids = created_vnfs
        instance.instantiation_state = InstantiationState.INSTANTIATED
        logger.info("instantiated NS %s with %d VNF(s)", instance.id, len(created_vnfs))
        return self.ns_instances_repo.update(instance)

    def terminate_ns(self, instance_id: str) -> NsInstance:
        """Terminate a Network Service and all of its VNFs."""
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

    def close(self) -> None:
        self.vnfm_client.close()
