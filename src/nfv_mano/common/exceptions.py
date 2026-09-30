"""Exception hierarchy for the NFV-MANO base."""

from __future__ import annotations


class NFVManoError(Exception):
    """Base class for all NFV-MANO errors."""


class NotFoundError(NFVManoError):
    """A requested ETSI entity or resource does not exist."""


class ConflictError(NFVManoError):
    """An entity already exists or conflicts with the current state."""


class InvalidStateError(NFVManoError):
    """An operation is not allowed for the entity's current lifecycle state."""


class RepositoryError(NFVManoError):
    """A data repository backend failed to read or write state."""


class DriverError(NFVManoError):
    """A VIM driver failed to manage NFVI resources."""


class VimClientError(NFVManoError):
    """A call to the VIM on the ``Vi-Vnfm`` reference point failed."""


class VnfmClientError(NFVManoError):
    """A call to the VNFM on the ``Or-Vnfm`` reference point failed."""
