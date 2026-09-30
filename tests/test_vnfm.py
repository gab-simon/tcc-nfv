"""Tests for the VNFM block (VNF LCM, Vi-Vnfm client, Or-Vnfm API)."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from nfv_mano.common.exceptions import VimClientError
from nfv_mano.common.lcm import InstantiationState
from nfv_mano.config import Settings
from nfv_mano.repositories.factory import build_repositories
from nfv_mano.vnfm.api import create_app
from nfv_mano.vnfm.manager import VnfmManager
from nfv_mano.vnfm.vim_client import VimClient


class FakeVimClient:
    """Duck-typed VimClient that records calls without any network."""

    def __init__(self) -> None:
        self.allocated: list[str] = []
        self.terminated: list[str] = []

    def allocate_compute(self, *, image, num_cpus, mem_size, vim_id=None) -> dict:
        resource_id = f"res-{len(self.allocated) + 1}"
        self.allocated.append(resource_id)
        return {"id": resource_id, "state": "RUNNING", "ip_address": "10.0.0.1"}

    def terminate_resource(self, resource_id: str) -> dict:
        self.terminated.append(resource_id)
        return {"id": resource_id, "state": "DELETED"}

    def close(self) -> None:  # pragma: no cover - no resources to release
        pass


@pytest.fixture
def fake_vim() -> FakeVimClient:
    return FakeVimClient()


@pytest.fixture
def client(tmp_path, fake_vim: FakeVimClient) -> TestClient:
    settings = Settings(_env_file=None, repository_backend="file", data_dir=tmp_path)
    repos = build_repositories(settings)
    manager = VnfmManager(
        instances_repo=repos.vnf_instances,
        vim_client=fake_vim,
        vnfm_id="vnfm-test",
    )
    return TestClient(create_app(settings, manager=manager))


def _payload() -> dict:
    return {
        "vnfd_id": "vnfd-1",
        "virtual_compute": {"image": "alpine:latest", "num_cpus": 2, "mem_size": "512m"},
        "vnf_instance_name": "web",
    }


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["component"] == "vnfm"


def test_instantiate_vnf(client: TestClient, fake_vim: FakeVimClient) -> None:
    response = client.post("/or/vnf_instances", json=_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["instantiation_state"] == InstantiationState.INSTANTIATED
    assert body["vnfd_id"] == "vnfd-1"
    assert len(body["vim_resource_ids"]) == 1
    assert fake_vim.allocated == body["vim_resource_ids"]


def test_list_and_get(client: TestClient) -> None:
    created = client.post("/or/vnf_instances", json=_payload()).json()

    listed = client.get("/or/vnf_instances").json()
    assert len(listed) == 1

    fetched = client.get(f"/or/vnf_instances/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_get_missing(client: TestClient) -> None:
    assert client.get("/or/vnf_instances/vnf-unknown").status_code == 404


def test_terminate_vnf(client: TestClient, fake_vim: FakeVimClient) -> None:
    created = client.post("/or/vnf_instances", json=_payload()).json()

    response = client.delete(f"/or/vnf_instances/{created['id']}")
    assert response.status_code == 200
    assert response.json()["instantiation_state"] == InstantiationState.NOT_INSTANTIATED
    assert fake_vim.terminated == created["vim_resource_ids"]

    again = client.delete(f"/or/vnf_instances/{created['id']}")
    assert again.status_code == 409


def test_em_view(client: TestClient) -> None:
    client.post("/or/vnf_instances", json=_payload())
    assert len(client.get("/ve/vnf_instances").json()) == 1


def test_vim_client_allocate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/vi/resources"
        return httpx.Response(201, json={"id": "res-1", "state": "RUNNING"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    vim = VimClient("http://vim", client=http)

    result = vim.allocate_compute(image="alpine", num_cpus=1, mem_size="128m")
    assert result["id"] == "res-1"


def test_vim_client_maps_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    vim = VimClient("http://vim", client=http)

    with pytest.raises(VimClientError):
        vim.get_resource("res-1")
