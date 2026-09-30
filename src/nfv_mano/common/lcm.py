"""Lifecycle management (LCM) enumerations.

The values mirror the ones defined by ETSI for VNF and NS lifecycle
management (GS NFV-SOL 003 for VNF LCM and GS NFV-SOL 005 for NS LCM), so the
API payloads can later follow the standard without renaming states.
"""

from __future__ import annotations

from enum import StrEnum


class InstantiationState(StrEnum):
    """Whether a VNF/NS instance is instantiated or not."""

    NOT_INSTANTIATED = "NOT_INSTANTIATED"
    INSTANTIATED = "INSTANTIATED"


class LcmOperationType(StrEnum):
    """LCM operation types common to VNF and NS management."""

    INSTANTIATE = "INSTANTIATE"
    SCALE = "SCALE"
    UPDATE = "UPDATE"
    TERMINATE = "TERMINATE"
    HEAL = "HEAL"
    QUERY = "QUERY"


class LcmOperationState(StrEnum):
    """State of an ongoing LCM operation occurrence."""

    STARTING = "STARTING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED_TEMP = "FAILED_TEMP"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLING_BACK_FAILED = "ROLLING_BACK_FAILED"

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if no further transition is expected."""
        return self in {
            LcmOperationState.COMPLETED,
            LcmOperationState.FAILED,
            LcmOperationState.ROLLING_BACK_FAILED,
        }

    @property
    def is_success(self) -> bool:
        """Return ``True`` only for a successfully finished operation."""
        return self is LcmOperationState.COMPLETED


class ResourceState(StrEnum):
    """State of an NFVI resource managed by the VIM."""

    NOT_CREATED = "NOT_CREATED"
    CREATING = "CREATING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    DELETING = "DELETING"
    DELETED = "DELETED"
    FAILED = "FAILED"
