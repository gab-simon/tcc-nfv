"""Tests for the shared ETSI data models and LCM enums."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nfv_mano.common.lcm import (
    InstantiationState,
    LcmOperationState,
    LcmOperationType,
)
from nfv_mano.common.models import (
    LcmOperationOccurrence,
    NsInstance,
    VirtualCompute,
    Vnfd,
    VnfInstance,
)


def test_ids_are_unique_by_default() -> None:
    first = Vnfd(name="a", virtual_compute=VirtualCompute(image="alpine"))
    second = Vnfd(name="b", virtual_compute=VirtualCompute(image="alpine"))
    assert first.id != second.id
    assert first.id.startswith("vnfd-")


def test_virtual_compute_requires_positive_cpus() -> None:
    with pytest.raises(ValidationError):
        VirtualCompute(image="alpine", num_cpus=0)


def test_vnf_instance_defaults() -> None:
    instance = VnfInstance(vnfd_id="vnfd-1", vnfm_id="vnfm-1")
    assert instance.instantiation_state is InstantiationState.NOT_INSTANTIATED
    assert instance.vim_resource_ids == []


def test_vnf_instance_rejects_duplicate_resources() -> None:
    with pytest.raises(ValidationError):
        VnfInstance(vnfd_id="vnfd-1", vnfm_id="vnfm-1", vim_resource_ids=["res-1", "res-1"])


def test_ns_instance_defaults() -> None:
    instance = NsInstance(nsd_id="nsd-1", name="service")
    assert instance.instantiation_state is InstantiationState.NOT_INSTANTIATED


def test_lcm_operation_terminal_states() -> None:
    assert LcmOperationState.COMPLETED.is_terminal
    assert LcmOperationState.FAILED.is_terminal
    assert not LcmOperationState.PROCESSING.is_terminal
    assert LcmOperationState.COMPLETED.is_success
    assert not LcmOperationState.FAILED.is_success


def test_lcm_operation_occurrence_touch() -> None:
    occurrence = LcmOperationOccurrence(
        operation=LcmOperationType.INSTANTIATE,
        target_id="vnf-1",
    )
    before = occurrence.updated_at
    occurrence.touch()
    assert occurrence.updated_at >= before
