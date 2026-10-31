"""Loopback-only HTTP API for the UmerOS cloud control plane.

The cloud manager is a user-space simulation.  This service exposes its
explicitly simulated state to the Flutter desktop shell; it never creates a
host VM, container, disk, or network namespace.

Run with ``python -m cloud.server``.  The process intentionally binds only to
``127.0.0.1``.  Set ``UMEROS_CLOUD_API_TOKEN`` to require an
``X-UmerOS-Token`` header from a local client.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cloud.compute import (
    CloudError,
    CloudNotFoundError,
    CloudOSManager,
    CloudQuotaError,
    CloudSchedulingError,
)

HOST = "127.0.0.1"
PORT = int(os.environ.get("UMEROS_CLOUD_PORT", "8422"))
API_PREFIX = "/api/cloud/v1"

log = logging.getLogger("UmerOS.Cloud.Server")


class DeployServiceRequest(BaseModel):
    """Validated input for a new elastic cloud service."""

    project_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")
    image_id: str = Field(min_length=1, max_length=80)
    flavor_id: str = Field(min_length=1, max_length=80)
    replicas: int = Field(default=1, ge=1, le=50)
    network_id: str | None = Field(default=None, max_length=80)
    zone: str | None = Field(default=None, max_length=80)


class ScaleServiceRequest(BaseModel):
    """Desired replica count for an existing service."""

    replicas: int = Field(ge=0, le=50)


class AutoscaleRequest(BaseModel):
    """Observed load sample and bounded target for a scaling decision."""

    observed_cpu_percent: float = Field(ge=0, le=10_000)
    min_replicas: int = Field(default=1, ge=0, le=50)
    max_replicas: int = Field(default=10, ge=0, le=50)
    target_cpu_percent: float = Field(default=65.0, gt=0, le=1000)


def _token_guard(
    x_umeros_token: Annotated[str | None, Header()] = None,
) -> None:
    """Enforce a configured local API token without exposing an open port."""

    expected = os.environ.get("UMEROS_CLOUD_API_TOKEN", "")
    if not expected:
        return
    if x_umeros_token is None or not hmac.compare_digest(x_umeros_token, expected):
        raise HTTPException(status_code=401, detail="invalid or missing cloud API token")


def _raise_cloud_error(exc: CloudError) -> None:
    if isinstance(exc, CloudNotFoundError):
        status = 404
    elif isinstance(exc, (CloudQuotaError, CloudSchedulingError)):
        status = 409
    else:
        status = 400
    raise HTTPException(status_code=status, detail=str(exc)) from exc


def _catalog(manager: CloudOSManager) -> dict[str, Any]:
    """Return stable deployment choices without leaking manager internals."""

    return {
        "projects": [
            {"id": project.project_id, "name": project.name}
            for project in sorted(manager.projects.values(), key=lambda item: item.project_id)
        ],
        "images": [
            {
                "id": image.image_id,
                "name": image.name,
                "traits": sorted(image.traits),
            }
            for image in sorted(manager.images.values(), key=lambda item: item.image_id)
        ],
        "flavors": [
            {
                "id": flavor.flavor_id,
                "name": flavor.name,
                "vcpus": flavor.vcpus,
                "memory_mb": flavor.memory_mb,
                "disk_gb": flavor.disk_gb,
            }
            for flavor in sorted(manager.flavors.values(), key=lambda item: item.flavor_id)
        ],
        "networks": [
            {
                "id": network.network_id,
                "project_id": network.project_id,
                "name": network.name,
            }
            for network in sorted(manager.networks.values(), key=lambda item: item.network_id)
        ],
    }


def create_app(manager: CloudOSManager | None = None) -> FastAPI:
    """Build an app around an injectable manager for production and tests."""

    app = FastAPI(
        title="UmerOS Cloud Control API",
        description="Loopback API for the simulated UmerOS cloud control plane.",
        version="1.0.0",
        dependencies=[Depends(_token_guard)],
    )
    app.state.manager = manager or CloudOSManager.demo()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8422",
            "http://localhost:8422",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-UmerOS-Token"],
    )

    def current_manager() -> CloudOSManager:
        return app.state.manager

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "umeros-cloud", "mode": "simulation"}

    @app.get(f"{API_PREFIX}/snapshot")
    def snapshot(current: CloudOSManager = Depends(current_manager)) -> dict[str, Any]:
        return current.dashboard_snapshot()

    @app.get(f"{API_PREFIX}/catalog")
    def catalog(current: CloudOSManager = Depends(current_manager)) -> dict[str, Any]:
        return _catalog(current)

    @app.post(f"{API_PREFIX}/services")
    def deploy_service(
        request: DeployServiceRequest,
        current: CloudOSManager = Depends(current_manager),
    ) -> dict[str, Any]:
        try:
            current.create_service(
                request.project_id,
                request.name,
                request.image_id,
                request.flavor_id,
                replicas=request.replicas,
                network_id=request.network_id,
                zone=request.zone,
            )
        except CloudError as exc:
            _raise_cloud_error(exc)
        return current.dashboard_snapshot()

    @app.post(f"{API_PREFIX}/services/{{service_id}}/scale")
    def scale_service(
        service_id: str,
        request: ScaleServiceRequest,
        current: CloudOSManager = Depends(current_manager),
    ) -> dict[str, Any]:
        try:
            current.reconcile_service(service_id, request.replicas)
        except CloudError as exc:
            _raise_cloud_error(exc)
        return current.dashboard_snapshot()

    @app.post(f"{API_PREFIX}/services/{{service_id}}/autoscale")
    def autoscale_service(
        service_id: str,
        request: AutoscaleRequest,
        current: CloudOSManager = Depends(current_manager),
    ) -> dict[str, Any]:
        if request.min_replicas > request.max_replicas:
            raise HTTPException(status_code=400, detail="min_replicas cannot exceed max_replicas")
        try:
            current.autoscale_service(
                service_id,
                observed_cpu_percent=request.observed_cpu_percent,
                min_replicas=request.min_replicas,
                max_replicas=request.max_replicas,
                target_cpu_percent=request.target_cpu_percent,
            )
        except CloudError as exc:
            _raise_cloud_error(exc)
        return current.dashboard_snapshot()

    return app


app = create_app()


def main() -> None:  # pragma: no cover - process entry point
    """Run the local Cloud API without ever binding to a network interface."""

    import uvicorn

    log.info("UmerOS Cloud API listening on http://%s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":  # pragma: no cover
    main()
