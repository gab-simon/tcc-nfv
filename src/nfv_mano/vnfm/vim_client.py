"""HTTP client for the ``Vi-Vnfm`` reference point.

The VNFM uses this client to allocate and release NFVI resources on the VIM.
It wraps :mod:`httpx` and converts transport/HTTP failures into
:class:`VimClientError`.
"""

from __future__ import annotations

import httpx

from nfv_mano.common.exceptions import VimClientError


class VimClient:
    """Client for the VIM resource API (``Vi-Vnfm``)."""

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
            raise VimClientError(f"VIM call {method} {path} failed: {exc}") from exc
        return response.json()

    def allocate_compute(
        self,
        *,
        image: str,
        num_cpus: int,
        mem_size: str,
        vim_id: str | None = None,
    ) -> dict:
        """Allocate a virtualised compute resource on the VIM."""
        payload = {
            "image": image,
            "num_cpus": num_cpus,
            "mem_size": mem_size,
            "vim_id": vim_id,
        }
        return self._request("POST", "/vi/resources", json=payload)

    def get_resource(self, resource_id: str) -> dict:
        """Fetch an NFVI resource by id."""
        return self._request("GET", f"/vi/resources/{resource_id}")

    def terminate_resource(self, resource_id: str) -> dict:
        """Release an NFVI resource."""
        return self._request("DELETE", f"/vi/resources/{resource_id}")

    def close(self) -> None:
        self._client.close()
