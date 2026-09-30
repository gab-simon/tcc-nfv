"""Tests for the VIM, VNFM and NFVO blocks."""

import httpx
import pytest
from fastapi.testclient import TestClient

from nfv_mano.common import VimClientError, VnfmClientError
from nfv_mano.config import Settings
from nfv_mano.models import InstantiationState, ResourceState
from nfv_mano.nfvo import NfvoManager, VnfmClient
from nfv_mano.nfvo import create_app as create_nfvo_app
from nfv_mano.repositories import build_repositories
from nfv_mano.vim import MockDriver
from nfv_mano.vim import create_app as create_vim_app
from nfv_mano.vnfm import VimClient, VnfmManager
from nfv_mano.vnfm import create_app as create_vnfm_app


def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, repository_backend="file", data_dir=tmp_path)


# --- VIM ------------------------------------------------------------------
@pytest.fixture
def vim_client(tmp_path) -> TestClient:
    return TestClient(create_vim_app(settings=_settings(tmp_path), driver=MockDriver()))


def test_vim_health_and_default_vim(vim_client):
    assert vim_client.get("/health").json()["component"] == "vim"
    vims = vim_client.get("/vi/vims").json()
    assert len(vims) == 1
    assert vims[0]["name"] == "default-vim"


def test_vim_allocate_get_list(vim_client):
    resource = vim_client.post("/vi/resources", json={"image": "alpine", "num_cpus": 2}).json()
    assert resource["state"] == ResourceState.RUNNING
    assert resource["external_id"].startswith("mock-")
    assert vim_client.get(f"/vi/resources/{resource['id']}").status_code == 200
    vim_client.post("/vi/resources", json={"image": "alpine"})
    assert len(vim_client.get("/vi/resources").json()) == 2


def test_vim_errors(vim_client):
    assert vim_client.get("/vi/resources/missing").status_code == 404
    assert (
        vim_client.post("/vi/resources", json={"image": "alpine", "num_cpus": 0}).status_code == 422
    )
    resource = vim_client.post("/vi/resources", json={"image": "alpine"}).json()
    assert vim_client.delete(f"/vi/resources/{resource['id']}").json()["state"] == (
        ResourceState.DELETED
    )
    assert vim_client.delete(f"/vi/resources/{resource['id']}").status_code == 409


def test_mock_driver_lifecycle():
    driver = MockDriver()
    allocated = driver.allocate(image="alpine", num_cpus=1, mem_size="128m")
    assert driver.status(allocated.external_id) is ResourceState.RUNNING
    driver.terminate(allocated.external_id)
    assert driver.status(allocated.external_id) is ResourceState.NOT_CREATED


# --- VNFM -----------------------------------------------------------------
class FakeVimClient:
    def __init__(self):
        self.allocated, self.terminated = [], []

    def allocate_compute(self, *, image, num_cpus, mem_size, vim_id=None):
        resource_id = f"res-{len(self.allocated) + 1}"
        self.allocated.append(resource_id)
        return {"id": resource_id, "state": "RUNNING"}

    def terminate_resource(self, resource_id):
        self.terminated.append(resource_id)
        return {"id": resource_id}

    def close(self):
        pass


def _vnfm_payload():
    return {
        "vnfd_id": "vnfd-1",
        "virtual_compute": {"image": "alpine", "num_cpus": 2, "mem_size": "512m"},
        "vnf_instance_name": "web",
    }


@pytest.fixture
def fake_vim():
    return FakeVimClient()


@pytest.fixture
def vnfm_client(tmp_path, fake_vim) -> TestClient:
    manager = VnfmManager(
        instances_repo=build_repositories(_settings(tmp_path)).vnf_instances,
        vim_client=fake_vim,
        vnfm_id="vnfm-test",
    )
    return TestClient(create_vnfm_app(_settings(tmp_path), manager=manager))


def test_vnfm_instantiate_list_get(vnfm_client, fake_vim):
    created = vnfm_client.post("/or/vnf_instances", json=_vnfm_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["instantiation_state"] == InstantiationState.INSTANTIATED
    assert fake_vim.allocated == body["vim_resource_ids"]
    assert len(vnfm_client.get("/or/vnf_instances").json()) == 1
    assert vnfm_client.get(f"/or/vnf_instances/{body['id']}").status_code == 200


def test_vnfm_terminate_and_errors(vnfm_client, fake_vim):
    created = vnfm_client.post("/or/vnf_instances", json=_vnfm_payload()).json()
    terminated = vnfm_client.delete(f"/or/vnf_instances/{created['id']}")
    assert terminated.json()["instantiation_state"] == InstantiationState.NOT_INSTANTIATED
    assert fake_vim.terminated == created["vim_resource_ids"]
    assert vnfm_client.delete(f"/or/vnf_instances/{created['id']}").status_code == 409
    assert vnfm_client.get("/or/vnf_instances/missing").status_code == 404


def test_vim_http_client():
    def handler(request):
        assert request.url.path == "/vi/resources"
        return httpx.Response(201, json={"id": "res-1"})

    vim = VimClient("http://vim", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert vim.allocate_compute(image="alpine", num_cpus=1, mem_size="128m")["id"] == "res-1"

    def fail(request):
        return httpx.Response(500, json={"detail": "boom"})

    vim = VimClient("http://vim", client=httpx.Client(transport=httpx.MockTransport(fail)))
    with pytest.raises(VimClientError):
        vim.get_resource("res-1")


# --- NFVO -----------------------------------------------------------------
class FakeVnfmClient:
    def __init__(self):
        self.instances, self.terminated = {}, []

    def instantiate_vnf(self, *, vnfd_id, virtual_compute, vnf_instance_name="", vim_id=None):
        instance_id = f"vnf-{len(self.instances) + 1}"
        self.instances[instance_id] = {"id": instance_id, "vnfd_id": vnfd_id}
        return self.instances[instance_id]

    def terminate_vnf(self, instance_id):
        self.terminated.append(instance_id)
        return {"id": instance_id}

    def close(self):
        pass


class FailingVnfmClient(FakeVnfmClient):
    def instantiate_vnf(self, **kwargs):
        if self.instances:
            raise VnfmClientError("simulated failure")
        return super().instantiate_vnf(**kwargs)


@pytest.fixture
def fake_vnfm():
    return FakeVnfmClient()


def _nfvo_client(tmp_path, fake_vnfm) -> TestClient:
    repos = build_repositories(_settings(tmp_path))
    manager = NfvoManager(
        vnf_catalog=repos.vnf_catalog,
        ns_catalog=repos.ns_catalog,
        ns_instances_repo=repos.ns_instances,
        vnfm_client=fake_vnfm,
    )
    return TestClient(create_nfvo_app(_settings(tmp_path), manager=manager))


@pytest.fixture
def nfvo_client(tmp_path, fake_vnfm) -> TestClient:
    return _nfvo_client(tmp_path, fake_vnfm)


def _register_vnfd(client):
    return client.post(
        "/os/vnfds",
        json={"name": "fw", "virtual_compute": {"image": "alpine", "num_cpus": 1}},
    ).json()["id"]


def test_nfvo_catalogs(nfvo_client):
    vnfd_id = _register_vnfd(nfvo_client)
    assert len(nfvo_client.get("/os/vnfds").json()) == 1
    nsd = nfvo_client.post("/os/nsds", json={"name": "chain", "vnfd_ids": [vnfd_id]})
    assert nsd.status_code == 201
    assert nfvo_client.post("/os/nsds", json={"name": "bad", "vnfd_ids": ["x"]}).status_code == 404


def test_nfvo_instantiate_and_terminate(nfvo_client, fake_vnfm):
    vnfd_id = _register_vnfd(nfvo_client)
    nsd_id = nfvo_client.post(
        "/os/nsds", json={"name": "chain", "vnfd_ids": [vnfd_id, vnfd_id]}
    ).json()["id"]

    ns = nfvo_client.post("/os/ns_instances", json={"nsd_id": nsd_id}).json()
    assert ns["instantiation_state"] == InstantiationState.INSTANTIATED
    assert len(ns["vnf_instance_ids"]) == 2

    terminated = nfvo_client.delete(f"/os/ns_instances/{ns['id']}")
    assert terminated.json()["instantiation_state"] == InstantiationState.NOT_INSTANTIATED
    assert fake_vnfm.terminated == ns["vnf_instance_ids"]
    assert nfvo_client.delete(f"/os/ns_instances/{ns['id']}").status_code == 409
    assert nfvo_client.get("/os/ns_instances/missing").status_code == 404


def test_nfvo_rolls_back_on_failure(tmp_path):
    fake = FailingVnfmClient()
    client = _nfvo_client(tmp_path, fake)
    vnfd_id = _register_vnfd(client)
    nsd_id = client.post("/os/nsds", json={"name": "chain", "vnfd_ids": [vnfd_id, vnfd_id]}).json()[
        "id"
    ]

    assert client.post("/os/ns_instances", json={"nsd_id": nsd_id}).status_code == 502
    assert fake.terminated == ["vnf-1"]
    instances = client.get("/os/ns_instances").json()
    assert instances[0]["instantiation_state"] == InstantiationState.NOT_INSTANTIATED


def test_vnfm_http_client():
    def handler(request):
        assert request.url.path == "/or/vnf_instances"
        return httpx.Response(201, json={"id": "vnf-1"})

    vnfm = VnfmClient("http://vnfm", client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = vnfm.instantiate_vnf(vnfd_id="vnfd-1", virtual_compute={"image": "alpine"})
    assert result["id"] == "vnf-1"

    def fail(request):
        return httpx.Response(502, json={"detail": "down"})

    vnfm = VnfmClient("http://vnfm", client=httpx.Client(transport=httpx.MockTransport(fail)))
    with pytest.raises(VnfmClientError):
        vnfm.get_vnf("vnf-1")
