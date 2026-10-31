"""HTTP contract tests for the local UmerOS Cloud API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from cloud.compute import CloudOSManager
from cloud.server import create_app


def _client() -> TestClient:
    return TestClient(create_app(CloudOSManager.demo()))


def test_snapshot_and_catalog_describe_the_demo_cloud() -> None:
    with _client() as client:
        snapshot = client.get("/api/cloud/v1/snapshot")
        catalog = client.get("/api/cloud/v1/catalog")

    assert snapshot.status_code == 200
    assert snapshot.json()["capacity"]["vcpus"]["total"] == 72
    assert snapshot.json()["services"][0]["name"] == "notebook-api"
    assert catalog.status_code == 200
    assert catalog.json()["projects"] == [{"id": "project-demo", "name": "Research Cloud"}]
    assert {item["id"] for item in catalog.json()["flavors"]} >= {"flavor-small", "flavor-gpu"}


def test_deploy_scale_and_autoscale_return_updated_snapshot() -> None:
    with _client() as client:
        deployed = client.post(
            "/api/cloud/v1/services",
            json={
                "project_id": "project-demo",
                "name": "research-worker",
                "image_id": "img-umeros-cloud",
                "flavor_id": "flavor-small",
                "replicas": 1,
            },
        )
        assert deployed.status_code == 200
        service = next(
            item for item in deployed.json()["services"] if item["name"] == "research-worker"
        )

        scaled = client.post(
            f"/api/cloud/v1/services/{service['id']}/scale", json={"replicas": 3}
        )
        autoscaled = client.post(
            f"/api/cloud/v1/services/{service['id']}/autoscale",
            json={
                "observed_cpu_percent": 180,
                "target_cpu_percent": 60,
                "min_replicas": 1,
                "max_replicas": 5,
            },
        )

    assert scaled.status_code == 200
    assert next(item for item in scaled.json()["services"] if item["id"] == service["id"])["desired"] == 3
    assert autoscaled.status_code == 200
    assert next(item for item in autoscaled.json()["services"] if item["id"] == service["id"])["desired"] == 5


def test_unknown_service_and_bad_scale_request_fail_closed() -> None:
    with _client() as client:
        missing = client.post("/api/cloud/v1/services/missing/scale", json={"replicas": 1})
        bad_range = client.post(
            "/api/cloud/v1/services/svc-0001/autoscale",
            json={"observed_cpu_percent": 10, "min_replicas": 4, "max_replicas": 2},
        )

    assert missing.status_code == 404
    assert bad_range.status_code == 400


def test_configured_token_is_required(monkeypatch) -> None:
    monkeypatch.setenv("UMEROS_CLOUD_API_TOKEN", "local-test-token")
    with _client() as client:
        denied = client.get("/api/cloud/v1/snapshot")
        permitted = client.get(
            "/api/cloud/v1/snapshot", headers={"X-UmerOS-Token": "local-test-token"}
        )

    assert denied.status_code == 401
    assert permitted.status_code == 200
