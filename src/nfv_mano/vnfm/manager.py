"""VNF lifecycle management performed by the VNFM.

This is a deliberately simple, non-fault-tolerant implementation: a VNF
instance owns one compute resource on the VIM. The lifecycle is persisted in
the VNF Instance repository, so it can later be moved behind a replicated store.
"""

from __future__ import annotations

from nfv_mano.common.exceptions import InvalidStateError
from nfv_mano.common.lcm import InstantiationState
from nfv_mano.common.logging import configure_logging
from nfv_mano.common.models import VirtualCompute, VnfInstance
from nfv_mano.repositories.base import Repository
from nfv_mano.vnfm.vim_client import VimClient

logger = configure_logging("vnfm")


class VnfmManager:
    """Manages the lifecycle of VNF instances."""

    def __init__(
        self,
        *,
        instances_repo: Repository[VnfInstance],
        vim_client: VimClient,
        vnfm_id: str,
    ) -> None:
        self.instances_repo = instances_repo
        self.vim_client = vim_client
        self.vnfm_id = vnfm_id

    def instantiate_vnf(
        self,
        *,
        vnfd_id: str,
        virtual_compute: VirtualCompute,
        name: str = "",
        vim_id: str | None = None,
    ) -> VnfInstance:
        """Create and instantiate a VNF instance, allocating its resource."""
        instance = VnfInstance(
            vnfd_id=vnfd_id,
            vnfm_id=self.vnfm_id,
            metadata={"name": name},
        )
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
        """Terminate a VNF instance and release its NFVI resources."""
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

    def close(self) -> None:
        self.vim_client.close()
