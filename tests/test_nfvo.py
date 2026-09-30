"""Tests for the NFVO block (catalogs, NS LCM, Or-Vnfm client)."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from nfv_mano.common.exceptions import VnfmClientError
from nfv_mano.common.lcm import InstantiationState
from nfv_mano.config import Settings
from nfv_mano.nfvo.api import create_app
from nfv_mano.nfvo.manager import NfvoManager
from nfv_mano.nfvo.vnfm_client import VnfmClient
from nfv_mano.repositories.factory import build_repositories


class FakeVnfmClient:
    """Duck-typed VnfmClient that records calls without any network."""

    def __init__(self) -> None:
        self.instances: dict[str, dict] = {}
        self.terminated: list[str] = []

    def instantiate_vnf(
        self,
        *,
        vnfd_id: str,
        virtual_compute: dict,
        vnf_instance_name: str = "",
        vim_id: str | None = None,
    ) -> dict:
        instance_id = f"vnf-{len(self.instances) + 1}"
        self.instances[instance_id] = {"id": instance_id, "vnfd_id": vnfd_id}
        return self.instances[instance_id]

    def terminate_vnf(self, instance_id: str) -> dict:
        self.terminated.append(instance_id)
        return {"id": instance_id}

    def close(self) -> None:  # pragma: no cover - no resources to release
        pass


class FailingVnfmClient(FakeVnfmClient):
    """Fails on the second instantiation to exercise rollback."""

    def instantiate_vnf(self, **kwargs) -> dict:
        if len(self.instances) >= 1:
            raise VnfmClientError("simulated VNFM failure")
        return super().instantiate_vnf(**kwargs)


@pytest.fixture
def fake_vnfm() -> FakeVnfmClient:
    return FakeVnfmClient()


def _build_client(tmp_path, fake_vnfm) -> TestClient:
    settings = Settings(_env_file=None, repository_backend="file", data_dir=tmp_path)
    repos = build_repositories(settings)
    manager = NfvoManager(
        vnf_catalog=repos.vnf_catalog,
        ns_catalog=repos.ns_catalog,
        ns_instances_repo=repos.ns_instances,
        vnfm_client=fake_vnfm,
    )
    return TestClient(create_app(settings, manager=manager))


@pytest.fixture
def client(tmp_path, fake_vnfm: FakeVnfmClient) -> TestClient:
    return _build_client(tmp_path, fake_vnfm)


def _register_vnfd(client: TestClient, name: str = "fw") -> str:
    body = {
        "name": name,
        "virtual_compute": {"image": "alpine:latest", "num_cpus": 1, "mem_size": "256m"},
    }
    response = client.post("/os/vnfds", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def _register_nsd(client: TestClient, vnfd_ids: list[str]) -> str:
    body = {"name": "chain", "vnfd_ids": vnfd_ids}
    response = client.post("/os/nsds", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["component"] == "nfvo"


def test_register_and_list_catalogs(client: TestClient) -> None:
    vnfd_id = _register_vnfd(client)
    assert len(client.get("/os/vnfds").json()) == 1
    assert client.get(f"/os/vnfds/{vnfd_id}").json()["id"] == vnfd_id

    nsd_id = _register_nsd(client, [vnfd_id])
    assert len(client.get("/os/nsds").json()) == 1
    assert client.get(f"/os/nsds/{nsd_id}").json()["id"] == nsd_id


def test_register_nsd_with_unknown_vnfd(client: TestClient) -> None:
    response = client.post("/os/nsds", json={"name": "bad", "vnfd_ids": ["vnfd-missing"]})
    assert response.status_code == 404


def test_instantiate_ns(client: TestClient, fake_vnfm: FakeVnfmClient) -> None:
    vnfd_id = _register_vnfd(client)
    nsd_id = _register_nsd(client, [vnfd_id, vnfd_id])

    response = client.post(
        "/os/ns_instances",
        json={"nsd_id": nsd_id, "ns_instance_name": "svc"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["instantiation_state"] == InstantiationState.INSTANTIATED
    assert len(body["vnf_instance_ids"]) == 2
    assert len(fake_vnfm.instances) == 2


def test_terminate_ns(client: TestClient, fake_vnfm: FakeVnfmClient) -> None:
    vnfd_id = _register_vnfd(client)
    nsd_id = _register_nsd(client, [vnfd_id])
    created = client.post("/os/ns_instances", json={"nsd_id": nsd_id}).json()

    response = client.delete(f"/os/ns_instances/{created['id']}")
    assert response.status_code == 200
    assert response.json()["instantiation_state"] == InstantiationState.NOT_INSTANTIATED
    assert fake_vnfm.terminated == created["vnf_instance_ids"]

    again = client.delete(f"/os/ns_instances/{created['id']}")
    assert again.status_code == 409


def test_get_missing_ns(client: TestClient) -> None:
    assert client.get("/os/ns_instances/ns-unknown").status_code == 404


def test_instantiate_rolls_back_on_failure(tmp_path) -> None:
    fake = FailingVnfmClient()
    client = _build_client(tmp_path, fake)
    vnfd_id = _register_vnfd(client)
    nsd_id = _register_nsd(client, [vnfd_id, vnfd_id])

    response = client.post("/os/ns_instances", json={"nsd_id": nsd_id})
    assert response.status_code == 502
    assert fake.terminated == ["vnf-1"]

    instances = client.get("/os/ns_instances").json()
    assert len(instances) == 1
    assert instances[0]["instantiation_state"] == InstantiationState.NOT_INSTANTIATED


def test_vnfm_client_instantiate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/or/vnf_instances"
        return httpx.Response(201, json={"id": "vnf-1"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    vnfm = VnfmClient("http://vnfm", client=http)

    result = vnfm.instantiate_vnf(
        vnfd_id="vnfd-1",
        virtual_compute={"image": "alpine", "num_cpus": 1, "mem_size": "128m"},
    )
    assert result["id"] == "vnf-1"


def test_vnfm_client_maps_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"detail": "down"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    vnfm = VnfmClient("http://vnfm", client=http)

    with pytest.raises(VnfmClientError):
        vnfm.get_vnf("vnf-1")
