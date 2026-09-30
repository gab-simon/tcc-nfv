"""Tests for the VIM block (mock driver and Vi-Vnfm API)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nfv_mano.common.lcm import ResourceState
from nfv_mano.config import Settings
from nfv_mano.vim.api import create_app
from nfv_mano.vim.drivers.mock_driver import MockDriver


@pytest.fixture
def client(tmp_path) -> TestClient:
    settings = Settings(_env_file=None, repository_backend="file", data_dir=tmp_path)
    app = create_app(settings=settings, driver=MockDriver())
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["component"] == "vim"


def test_default_vim_registered(client: TestClient) -> None:
    vims = client.get("/vi/vims").json()
    assert len(vims) == 1
    assert vims[0]["name"] == "default-vim"


def test_allocate_and_get_resource(client: TestClient) -> None:
    response = client.post(
        "/vi/resources",
        json={"image": "alpine:latest", "num_cpus": 2, "mem_size": "512m"},
    )
    assert response.status_code == 201
    resource = response.json()
    assert resource["state"] == ResourceState.RUNNING
    assert resource["ip_address"] is not None
    assert resource["external_id"].startswith("mock-")

    fetched = client.get(f"/vi/resources/{resource['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == resource["id"]


def test_list_resources(client: TestClient) -> None:
    client.post("/vi/resources", json={"image": "alpine"})
    client.post("/vi/resources", json={"image": "alpine"})

    resources = client.get("/vi/resources").json()
    assert len(resources) == 2


def test_get_missing_resource(client: TestClient) -> None:
    response = client.get("/vi/resources/res-unknown")
    assert response.status_code == 404


def test_terminate_resource(client: TestClient) -> None:
    resource = client.post("/vi/resources", json={"image": "alpine"}).json()

    response = client.delete(f"/vi/resources/{resource['id']}")
    assert response.status_code == 200
    assert response.json()["state"] == ResourceState.DELETED

    again = client.delete(f"/vi/resources/{resource['id']}")
    assert again.status_code == 409


def test_invalid_allocate_payload(client: TestClient) -> None:
    response = client.post("/vi/resources", json={"image": "alpine", "num_cpus": 0})
    assert response.status_code == 422


def test_registered_vim_by_id(client: TestClient) -> None:
    vim = client.get("/vi/vims").json()[0]
    fetched = client.get(f"/vi/vims/{vim['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == vim["id"]


def test_mock_driver_status_and_ip() -> None:
    driver = MockDriver()
    allocated = driver.allocate(image="alpine", num_cpus=1, mem_size="128m")

    assert driver.status(allocated.external_id) is ResourceState.RUNNING
    assert driver.ip_address(allocated.external_id) == allocated.ip_address

    driver.terminate(allocated.external_id)
    assert driver.status(allocated.external_id) is ResourceState.NOT_CREATED
