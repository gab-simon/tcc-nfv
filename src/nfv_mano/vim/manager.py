"""VIM manager: lifecycle of NFVI resources on the ``Vi-Vnfm`` reference point.

The manager applies the resource lifecycle state transitions and delegates the
actual NFVI work to a Nf-Vi driver. All state is stored through the NFVI
Resources repository.
"""

from __future__ import annotations

from nfv_mano.common.exceptions import InvalidStateError
from nfv_mano.common.lcm import ResourceState
from nfv_mano.common.logging import configure_logging
from nfv_mano.common.models import NfviResource, VimInfo
from nfv_mano.config import Settings
from nfv_mano.repositories.base import Repository
from nfv_mano.vim.drivers.base import VimDriver

logger = configure_logging("vim")


class VimManager:
    """Manages NFVI compute resources and registered VIMs."""

    def __init__(
        self,
        *,
        driver: VimDriver,
        resources_repo: Repository[NfviResource],
        vims_repo: Repository[VimInfo],
        settings: Settings,
    ) -> None:
        self.driver = driver
        self.resources_repo = resources_repo
        self.vims_repo = vims_repo
        self.settings = settings
        self.ensure_default_vim()

    def ensure_default_vim(self) -> VimInfo:
        """Register the local VIM once, so resources can reference it."""
        existing = self.vims_repo.list()
        if existing:
            return existing[0]
        vim = VimInfo(
            name="default-vim",
            vim_type=self.settings.vim_driver,
            url=self.settings.vim_base_url,
            description=f"Local {self.settings.vim_driver} VIM",
        )
        logger.info("registering default VIM %s", vim.id)
        return self.vims_repo.add(vim)

    @property
    def default_vim_id(self) -> str:
        return self.vims_repo.list()[0].id

    def list_vims(self) -> list[VimInfo]:
        return self.vims_repo.list()

    def allocate_compute(
        self,
        *,
        image: str,
        num_cpus: int,
        mem_size: str,
        vim_id: str | None = None,
    ) -> NfviResource:
        """Allocate a virtualised compute resource through the driver."""
        target_vim = vim_id or self.default_vim_id
        self.vims_repo.get(target_vim)

        resource = NfviResource(
            vim_id=target_vim,
            resource_type="virtual_compute",
            image=image,
            num_cpus=num_cpus,
            mem_size=mem_size,
            state=ResourceState.CREATING,
        )
        self.resources_repo.add(resource)

        try:
            allocated = self.driver.allocate(
                image=image,
                num_cpus=num_cpus,
                mem_size=mem_size,
                name=resource.id,
            )
        except Exception:
            resource.state = ResourceState.FAILED
            self.resources_repo.update(resource)
            logger.exception("allocation failed for resource %s", resource.id)
            raise

        resource.external_id = allocated.external_id
        resource.ip_address = allocated.ip_address
        resource.state = allocated.state
        resource.metadata.update(allocated.extra)
        logger.info("allocated resource %s (%s)", resource.id, resource.external_id)
        return self.resources_repo.update(resource)

    def list_resources(self) -> list[NfviResource]:
        return self.resources_repo.list()

    def get_resource(self, resource_id: str) -> NfviResource:
        return self.resources_repo.get(resource_id)

    def refresh_resource(self, resource_id: str) -> NfviResource:
        """Synchronise the stored state with the driver's current state."""
        resource = self.resources_repo.get(resource_id)
        if resource.external_id is not None:
            resource.state = self.driver.status(resource.external_id)
            resource.ip_address = self.driver.ip_address(resource.external_id)
            self.resources_repo.update(resource)
        return resource

    def terminate_resource(self, resource_id: str) -> NfviResource:
        """Destroy a resource and mark it deleted."""
        resource = self.resources_repo.get(resource_id)
        if resource.state is ResourceState.DELETED:
            raise InvalidStateError(f"resource {resource_id!r} is already deleted")

        resource.state = ResourceState.DELETING
        self.resources_repo.update(resource)

        if resource.external_id is not None:
            self.driver.terminate(resource.external_id)

        resource.state = ResourceState.DELETED
        logger.info("terminated resource %s", resource_id)
        return self.resources_repo.update(resource)

    def register_vim(self, info: VimInfo) -> VimInfo:
        """Register an additional VIM."""
        return self.vims_repo.add(info)

    def get_vim(self, vim_id: str) -> VimInfo:
        return self.vims_repo.get(vim_id)
