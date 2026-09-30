"""HTTP client for the ``Or-Vnfm`` reference point.

The NFVO uses this client to ask the VNFM for VNF lifecycle operations.
"""

from __future__ import annotations

import httpx

from nfv_mano.common.exceptions import VnfmClientError


class VnfmClient:
    """Client for the VNFM VNF lifecycle API (``Or-Vnfm``)."""

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VnfmClientError(f"VNFM call {method} {path} failed: {exc}") from exc
        return response.json()

    def instantiate_vnf(
        self,
        *,
        vnfd_id: str,
        virtual_compute: dict,
        vnf_instance_name: str = "",
        vim_id: str | None = None,
    ) -> dict:
        """Create and instantiate a VNF instance on the VNFM."""
        payload = {
            "vnfd_id": vnfd_id,
            "virtual_compute": virtual_compute,
            "vnf_instance_name": vnf_instance_name,
            "vim_id": vim_id,
        }
        return self._request("POST", "/or/vnf_instances", json=payload)

    def get_vnf(self, instance_id: str) -> dict:
        """Fetch a VNF instance by id."""
        return self._request("GET", f"/or/vnf_instances/{instance_id}")

    def terminate_vnf(self, instance_id: str) -> dict:
        """Terminate a VNF instance."""
        return self._request("DELETE", f"/or/vnf_instances/{instance_id}")

    def close(self) -> None:
        self._client.close()
