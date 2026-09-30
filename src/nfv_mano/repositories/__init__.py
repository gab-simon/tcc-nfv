"""ETSI data repositories.

ETSI defines four repositories used by the NFV-MANO functional blocks:

* NS Catalog and VNF Catalog (descriptors).
* NS/VNF Instance repositories (instantiated entities).
* NFVI Resources repository (resources and VIMs).

They all share one generic interface (:class:`~nfv_mano.repositories.base.Repository`),
so the in-memory/file backends used in the non-fault-tolerant base can later be
replaced by a distributed store (etcd/Raft) without touching the MANO logic.
"""
