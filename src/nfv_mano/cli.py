"""Command-line interface for the NFV-MANO base.

Two entry points:

* ``serve`` runs one component's reference point with uvicorn.
* ``demo`` boots the three components over HTTP and drives a full
  Network Service lifecycle, useful to validate the base end to end.
"""

from __future__ import annotations

import threading
import time

import httpx
import typer
import uvicorn

from nfv_mano.config import Settings, get_settings

app = typer.Typer(help="NFV-MANO base (ETSI NFV architectural framework)")

_COMPONENTS = {
    "vnfm": ("vnfm_host", "vnfm_port"),
    "nfvo": ("nfvo_host", "nfvo_port"),
    "vim": ("vim_host", "vim_port"),
}

_BASE_URL_ATTR = {
    "vnfm": "vnfm_base_url",
    "nfvo": "nfvo_base_url",
    "vim": "vim_base_url",
}


def _load_app(component: str, settings: Settings):
    """Instantiate the FastAPI app for a component name."""
    if component == "vnfm":
        from nfv_mano.vnfm import create_app
    elif component == "nfvo":
        from nfv_mano.nfvo import create_app
    elif component == "vim":
        from nfv_mano.vim import create_app
    else:
        raise typer.BadParameter(f"unknown component {component!r}")
    return create_app(settings)


@app.command()
def serve(
    component: str = typer.Argument(..., help="One of: nfvo, vnfm, vim"),
    host: str | None = typer.Option(None, help="Override bind host"),
    port: int | None = typer.Option(None, help="Override bind port"),
) -> None:
    """Run a single NFV-MANO component."""
    if component not in _COMPONENTS:
        raise typer.BadParameter(f"component must be one of {sorted(_COMPONENTS)}")

    settings = get_settings()
    if host is None:
        host = getattr(settings, _COMPONENTS[component][0])
    if port is None:
        port = getattr(settings, _COMPONENTS[component][1])

    typer.echo(f"starting {component} on http://{host}:{port}")
    uvicorn.run(_load_app(component, settings), host=host, port=port)


class _ServerThread(threading.Thread):
    """Run a uvicorn server in a background thread."""

    def __init__(self, fastapi_app, host: str, port: int) -> None:
        super().__init__(daemon=True)
        config = uvicorn.Config(fastapi_app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


def _wait_for_health(url: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{url}/health", timeout=1.0).status_code == 200:
                return True
        except httpx.HTTPError:
            time.sleep(0.2)
    return False


@app.command()
def demo() -> None:
    """Boot the components and run a full Network Service lifecycle."""
    # In-memory state and the mock driver on purpose: the demo should just
    # run, with no Docker and no leftover files.
    settings = Settings(repository_backend="memory", vim_driver="mock")
    servers = [
        _ServerThread(
            _load_app(name, settings),
            getattr(settings, spec[0]),
            getattr(settings, spec[1]),
        )
        for name, spec in _COMPONENTS.items()
    ]

    for server in servers:
        server.start()

    try:
        for name in _COMPONENTS:
            base = getattr(settings, _BASE_URL_ATTR[name])
            if not _wait_for_health(base):
                typer.echo(f"error: {name} did not become healthy", err=True)
                raise typer.Exit(code=1)
        _run_demo_flow(settings)
    finally:
        for server in servers:
            server.stop()
    typer.echo("\ndemo finished, shutting down")


def _run_demo_flow(settings: Settings) -> None:
    nfvo = settings.nfvo_base_url
    client = httpx.Client(timeout=5.0)

    vnfd = client.post(
        f"{nfvo}/os/vnfds",
        json={
            "name": "firewall",
            "description": "demo VNF",
            "virtual_compute": {"image": "alpine:latest", "num_cpus": 1, "mem_size": "256m"},
        },
    ).json()
    typer.echo(f"registered VNFD {vnfd['id']}")

    second = client.post(
        f"{nfvo}/os/vnfds",
        json={
            "name": "ids",
            "virtual_compute": {"image": "alpine:latest", "num_cpus": 2, "mem_size": "512m"},
        },
    ).json()
    typer.echo(f"registered VNFD {second['id']}")

    nsd = client.post(
        f"{nfvo}/os/nsds",
        json={"name": "security-chain", "vnfd_ids": [vnfd["id"], second["id"]]},
    ).json()
    typer.echo(f"registered NSD {nsd['id']}")

    ns = client.post(
        f"{nfvo}/os/ns_instances",
        json={"nsd_id": nsd["id"], "ns_instance_name": "demo-ns"},
    ).json()
    typer.echo(
        f"instantiated NS {ns['id']} state={ns['instantiation_state']} "
        f"vnfs={len(ns['vnf_instance_ids'])}"
    )

    resources = httpx.get(f"{settings.vim_base_url}/vi/resources", timeout=5.0).json()
    typer.echo(f"VIM allocated {len(resources)} resource(s)")
    for resource in resources:
        typer.echo(
            f"  - {resource['id']} external={resource['external_id']} "
            f"ip={resource['ip_address']} state={resource['state']}"
        )

    terminated = client.delete(f"{nfvo}/os/ns_instances/{ns['id']}").json()
    typer.echo(f"terminated NS state={terminated['instantiation_state']}")


if __name__ == "__main__":
    app()
