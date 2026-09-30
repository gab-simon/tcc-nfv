"""Identifier helpers shared by all NFV-MANO components."""

from __future__ import annotations

import uuid


def generate_id(prefix: str = "") -> str:
    """Return a globally unique identifier, optionally prefixed.

    ETSI entities (VNFD, NSD, VNF/NS instances, LCM operations) are identified
    by opaque strings. A UUID4 hex keeps them collision-free without a central
    sequence, which also helps the future distributed (Raft/etcd) store.
    """
    value = uuid.uuid4().hex
    return f"{prefix}{value}" if prefix else value
