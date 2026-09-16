"""
Tests for the UmerOS cloud compute/orchestration subsystem.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cloud import (
    CloudFlavor,
    CloudImage,
    CloudNode,
    CloudOSManager,
    CloudQuota,
    CloudQuotaError,
    CloudSchedulingError,
    InstanceState,
)


class TestCloudCompute(unittest.TestCase):
    def setUp(self) -> None:
        self.cloud = CloudOSManager(seed_defaults=False)
        self.cloud.register_node(
            CloudNode(
                "node-a",
                "compute-a",
                "zone-a",
                total_vcpus=8,
                total_memory_mb=16_384,
                total_storage_gb=500,
                traits={"ssd"},
            )
        )
        self.cloud.register_node(
            CloudNode(
                "node-b",
                "compute-b",
                "zone-b",
                total_vcpus=16,
                total_memory_mb=32_768,
                total_storage_gb=1_000,
                traits={"ssd", "gpu"},
            )
        )
        self.cloud.register_image(
            CloudImage(
                "img-base",
                "UmerOS Base",
                "umeros",
                "3.0",
                min_vcpus=1,
                min_memory_mb=512,
                min_disk_gb=5,
            )
        )
        self.cloud.register_image(
            CloudImage(
                "img-gpu",
                "UmerOS GPU",
                "umeros",
                "3.0-gpu",
                min_vcpus=2,
                min_memory_mb=2048,
                min_disk_gb=20,
                traits={"gpu"},
            )
        )
        self.cloud.register_flavor(CloudFlavor("tiny", "Tiny", 1, 1024, 10))
        self.cloud.register_flavor(CloudFlavor("gpu", "GPU", 4, 8192, 80))
        self.project = self.cloud.create_project(
            "Main",
            quota=CloudQuota(
                max_instances=6,
                max_vcpus=16,
                max_memory_mb=32_768,
                max_storage_gb=500,
                max_network_ports=8,
            ),
            project_id="project-main",
        )
        self.network = self.cloud.create_network(
            self.project.project_id,
            "main-net",
            "10.55.0.0/24",
        )

    def test_provision_instance_updates_node_project_and_network(self) -> None:
        instance = self.cloud.provision_instance(
            self.project.project_id,
            "api-1",
            "img-base",
            "tiny",
            network_id=self.network.network_id,
        )

        self.assertEqual(instance.state, InstanceState.RUNNING)
        self.assertEqual(instance.ip_address, "10.55.0.2")
        self.assertEqual(self.project.usage.instances, 1)
        self.assertEqual(self.project.usage.vcpus, 1)
        self.assertEqual(len(self.network.allocated_ips), 1)
        self.assertIn(instance.instance_id, self.cloud.nodes[instance.node_id].instance_ids)

    def test_quota_is_fail_closed_before_scheduling(self) -> None:
        small_quota = CloudQuota(max_instances=1, max_vcpus=1, max_memory_mb=1024, max_storage_gb=10)
        project = self.cloud.create_project("Limited", quota=small_quota, project_id="project-limited")
        net = self.cloud.create_network(project.project_id, "limited-net", "10.77.0.0/24")
        self.cloud.provision_instance(project.project_id, "one", "img-base", "tiny", network_id=net.network_id)

        with self.assertRaises(CloudQuotaError):
            self.cloud.provision_instance(project.project_id, "two", "img-base", "tiny", network_id=net.network_id)

    def test_image_traits_filter_to_gpu_node(self) -> None:
        instance = self.cloud.provision_instance(
            self.project.project_id,
            "worker-gpu",
            "img-gpu",
            "gpu",
            network_id=self.network.network_id,
        )

        self.assertEqual(instance.node_id, "node-b")

    def test_service_reconcile_and_autoscale(self) -> None:
        service = self.cloud.create_service(
            self.project.project_id,
            "web",
            "img-base",
            "tiny",
            replicas=2,
            network_id=self.network.network_id,
        )

        self.assertEqual(service.ready_replicas, 2)
        self.cloud.autoscale_service(
            service.service_id,
            observed_cpu_percent=150,
            target_cpu_percent=75,
            max_replicas=4,
        )
        self.assertEqual(service.desired_replicas, 4)
        self.assertEqual(service.ready_replicas, 4)

        self.cloud.reconcile_service(service.service_id, 1)
        self.assertEqual(service.ready_replicas, 1)

    def test_migration_moves_instance_and_releases_old_node(self) -> None:
        instance = self.cloud.provision_instance(
            self.project.project_id,
            "migrating",
            "img-base",
            "tiny",
            network_id=self.network.network_id,
            zone="zone-a",
        )
        self.assertEqual(instance.node_id, "node-a")

        migrated = self.cloud.migrate_instance(instance.instance_id, target_zone="zone-b")

        self.assertEqual(migrated.node_id, "node-b")
        self.assertNotIn(instance.instance_id, self.cloud.nodes["node-a"].instance_ids)
        self.assertIn(instance.instance_id, self.cloud.nodes["node-b"].instance_ids)

    def test_volume_metering_and_dashboard_snapshot(self) -> None:
        instance = self.cloud.provision_instance(
            self.project.project_id,
            "db",
            "img-base",
            "tiny",
            network_id=self.network.network_id,
        )
        volume = self.cloud.create_volume(self.project.project_id, "db-data", 50)
        self.cloud.attach_volume(volume.volume_id, instance.instance_id)
        self.cloud.record_usage(instance.instance_id, seconds=3600, network_gb=2.5)

        snapshot = self.cloud.dashboard_snapshot()

        self.assertGreater(self.cloud.project_cost(self.project.project_id), 0)
        self.assertEqual(volume.attached_to, instance.instance_id)
        self.assertEqual(snapshot["capacity"]["vcpus"]["used"], 1)
        self.assertEqual(snapshot["projects"][0]["usage"]["volumes"], 1)
        self.assertEqual(snapshot["networks"][0]["ports"], 1)

    def test_scheduler_reports_when_no_host_can_fit(self) -> None:
        project = self.cloud.create_project(
            "Large",
            quota=CloudQuota(max_instances=2, max_vcpus=256, max_memory_mb=262_144, max_storage_gb=262_144),
            project_id="project-large",
        )
        network = self.cloud.create_network(project.project_id, "large-net", "10.88.0.0/24")
        self.cloud.register_flavor(CloudFlavor("huge", "Huge", 99, 99_999, 99_999))
        with self.assertRaises(CloudSchedulingError):
            self.cloud.provision_instance(
                project.project_id,
                "too-large",
                "img-base",
                "huge",
                network_id=network.network_id,
            )


if __name__ == "__main__":
    unittest.main()
