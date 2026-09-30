"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from nfv_mano.common.models import VirtualCompute, Vnfd


@pytest.fixture
def vnfd() -> Vnfd:
    """A minimal VNF descriptor for tests."""
    return Vnfd(
        name="test-vnf",
        virtual_compute=VirtualCompute(image="alpine:latest", num_cpus=2, mem_size="512m"),
    )
