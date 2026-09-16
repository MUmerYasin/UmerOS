# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

"""UmerOS cloud operating system primitives.

The module models the operating-system side of cloud computing: pooled
compute nodes, project quotas, placement scheduling, virtual networks,
block volumes, elastic services, and measured usage. It is deliberately
simulation-safe; no hypervisor, container runtime, network namespace, or
disk image is created by this code.
"""

from __future__ import annotations

import ipaddress
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


class CloudError(RuntimeError):
    """Base class for cloud manager errors."""


class CloudQuotaError(CloudError):
    """Raised when a project would exceed quota."""


class CloudSchedulingError(CloudError):
    """Raised when no healthy host can satisfy a placement request."""


class CloudNotFoundError(CloudError):
    """Raised when a requested cloud object is missing."""


class InstanceState(str, Enum):
    BUILDING = "building"
    RUNNING = "running"
    STOPPED = "stopped"
    MIGRATING = "migrating"
    TERMINATED = "terminated"
    ERROR = "error"


class ServiceState(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    SCALING = "scaling"
    STOPPED = "stopped"


class DeploymentModel(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
    COMMUNITY = "community"
    HYBRID = "hybrid"


class ServiceModel(str, Enum):
    IAAS = "iaas"
    PAAS = "paas"
    SAAS = "saas"


@dataclass(frozen=True)
class ResourceRequest:
    """Compute, memory, storage, and networking required by a workload."""

    vcpus: int
    memory_mb: int
    storage_gb: int
    network_ports: int = 1

    def validate(self) -> None:
        if self.vcpus <= 0:
            raise ValueError("vcpus must be positive")
        if self.memory_mb <= 0:
            raise ValueError("memory_mb must be positive")
        if self.storage_gb < 0:
            raise ValueError("storage_gb cannot be negative")
        if self.network_ports < 0:
            raise ValueError("network_ports cannot be negative")


@dataclass
class CloudQuota:
    """Per-project cloud limits."""

    max_instances: int = 10
    max_vcpus: int = 32
    max_memory_mb: int = 65_536
    max_storage_gb: int = 1_024
    max_network_ports: int = 32
    max_volumes: int = 16


@dataclass
class CloudUsage:
    """Current resource usage for a project."""

    instances: int = 0
    vcpus: int = 0
    memory_mb: int = 0
    storage_gb: int = 0
    network_ports: int = 0
    volumes: int = 0

    def add(self, request: ResourceRequest) -> None:
        self.instances += 1
        self.vcpus += request.vcpus
        self.memory_mb += request.memory_mb
        self.storage_gb += request.storage_gb
        self.network_ports += request.network_ports

    def remove(self, request: ResourceRequest) -> None:
        self.instances = max(0, self.instances - 1)
        self.vcpus = max(0, self.vcpus - request.vcpus)
        self.memory_mb = max(0, self.memory_mb - request.memory_mb)
        self.storage_gb = max(0, self.storage_gb - request.storage_gb)
        self.network_ports = max(0, self.network_ports - request.network_ports)

    def to_dict(self) -> Dict[str, int]:
        return {
            "instances": self.instances,
            "vcpus": self.vcpus,
            "memory_mb": self.memory_mb,
            "storage_gb": self.storage_gb,
            "network_ports": self.network_ports,
            "volumes": self.volumes,
        }


@dataclass
class CloudProject:
    """A tenant/project boundary for identity, quotas, and metering."""

    project_id: str
    name: str
    owner: str = "admin"
    quota: CloudQuota = field(default_factory=CloudQuota)
    usage: CloudUsage = field(default_factory=CloudUsage)

    def assert_quota(self, request: ResourceRequest) -> None:
        request.validate()
        failures: List[str] = []
        if self.usage.instances + 1 > self.quota.max_instances:
            failures.append("instances")
        if self.usage.vcpus + request.vcpus > self.quota.max_vcpus:
            failures.append("vcpus")
        if self.usage.memory_mb + request.memory_mb > self.quota.max_memory_mb:
            failures.append("memory_mb")
        if self.usage.storage_gb + request.storage_gb > self.quota.max_storage_gb:
            failures.append("storage_gb")
        if self.usage.network_ports + request.network_ports > self.quota.max_network_ports:
            failures.append("network_ports")
        if failures:
            joined = ", ".join(failures)
            raise CloudQuotaError(f"project {self.project_id} quota exceeded: {joined}")


@dataclass(frozen=True)
class CloudImage:
    """Bootable image metadata."""

    image_id: str
    name: str
    os_family: str
    version: str
    min_vcpus: int = 1
    min_memory_mb: int = 512
    min_disk_gb: int = 8
    traits: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CloudFlavor:
    """A reusable sizing profile."""

    flavor_id: str
    name: str
    vcpus: int
    memory_mb: int
    disk_gb: int

    @property
    def request(self) -> ResourceRequest:
        return ResourceRequest(self.vcpus, self.memory_mb, self.disk_gb)


@dataclass
class CloudNode:
    """A host participating in the UmerOS cloud resource pool."""

    node_id: str
    hostname: str
    zone: str
    total_vcpus: int
    total_memory_mb: int
    total_storage_gb: int
    traits: Set[str] = field(default_factory=set)
    enabled: bool = True
    healthy: bool = True
    used_vcpus: int = 0
    used_memory_mb: int = 0
    used_storage_gb: int = 0
    instance_ids: Set[str] = field(default_factory=set)

    @property
    def free_vcpus(self) -> int:
        return self.total_vcpus - self.used_vcpus

    @property
    def free_memory_mb(self) -> int:
        return self.total_memory_mb - self.used_memory_mb

    @property
    def free_storage_gb(self) -> int:
        return self.total_storage_gb - self.used_storage_gb

    def can_host(self, request: ResourceRequest, required_traits: Iterable[str] = ()) -> bool:
        required = set(required_traits)
        return (
            self.enabled
            and self.healthy
            and required.issubset(self.traits)
            and self.free_vcpus >= request.vcpus
            and self.free_memory_mb >= request.memory_mb
            and self.free_storage_gb >= request.storage_gb
        )

    def allocate(self, instance_id: str, request: ResourceRequest) -> None:
        if not self.can_host(request):
            raise CloudSchedulingError(f"node {self.node_id} cannot host {instance_id}")
        self.used_vcpus += request.vcpus
        self.used_memory_mb += request.memory_mb
        self.used_storage_gb += request.storage_gb
        self.instance_ids.add(instance_id)

    def release(self, instance_id: str, request: ResourceRequest) -> None:
        self.used_vcpus = max(0, self.used_vcpus - request.vcpus)
        self.used_memory_mb = max(0, self.used_memory_mb - request.memory_mb)
        self.used_storage_gb = max(0, self.used_storage_gb - request.storage_gb)
        self.instance_ids.discard(instance_id)

    def utilization(self) -> Dict[str, float]:
        def ratio(used: int, total: int) -> float:
            return round(used / total, 4) if total else 0.0

        return {
            "cpu": ratio(self.used_vcpus, self.total_vcpus),
            "memory": ratio(self.used_memory_mb, self.total_memory_mb),
            "storage": ratio(self.used_storage_gb, self.total_storage_gb),
        }


@dataclass
class VirtualNetwork:
    """A project-scoped virtual network with simple IP allocation."""

    network_id: str
    project_id: str
    name: str
    cidr: str
    gateway: Optional[str] = None
    allocated_ips: Dict[str, str] = field(default_factory=dict)
    _next_host_offset: int = 2

    def __post_init__(self) -> None:
        network = ipaddress.ip_network(self.cidr, strict=False)
        if self.gateway is None:
            hosts = network.hosts()
            self.gateway = str(next(hosts))

    def allocate_ip(self, port_id: str) -> str:
        if port_id in self.allocated_ips:
            return self.allocated_ips[port_id]
        network = ipaddress.ip_network(self.cidr, strict=False)
        max_offset = network.num_addresses - 2
        while self._next_host_offset <= max_offset:
            ip = str(network.network_address + self._next_host_offset)
            self._next_host_offset += 1
            if ip == self.gateway or ip in self.allocated_ips.values():
                continue
            self.allocated_ips[port_id] = ip
            return ip
        raise CloudSchedulingError(f"network {self.network_id} has no free addresses")

    def release_ip(self, port_id: str) -> None:
        self.allocated_ips.pop(port_id, None)


@dataclass
class CloudVolume:
    """A virtual block volume."""

    volume_id: str
    project_id: str
    name: str
    size_gb: int
    attached_to: Optional[str] = None


@dataclass
class CloudInstance:
    """A scheduled VM/container-like unit."""

    instance_id: str
    project_id: str
    name: str
    image_id: str
    flavor_id: str
    node_id: str
    zone: str
    request: ResourceRequest
    state: InstanceState = InstanceState.RUNNING
    network_id: str = ""
    port_id: str = ""
    ip_address: str = ""
    service_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class CloudService:
    """An elastic service made of co-scheduled instance replicas."""

    service_id: str
    project_id: str
    name: str
    image_id: str
    flavor_id: str
    desired_replicas: int
    network_id: str
    zone: Optional[str] = None
    endpoint: str = ""
    instance_ids: List[str] = field(default_factory=list)
    state: ServiceState = ServiceState.ACTIVE

    @property
    def ready_replicas(self) -> int:
        return len(self.instance_ids)


@dataclass
class UsageRecord:
    """Measured-service accounting record."""

    project_id: str
    resource_id: str
    seconds: int
    vcpu_seconds: int
    memory_mb_seconds: int
    storage_gb_seconds: int
    network_gb: float = 0.0
    timestamp: float = field(default_factory=time.time)


class CloudScheduler:
    """Filter-and-weight placement scheduler for UmerOS cloud nodes."""

    def __init__(self, policy: str = "spread") -> None:
        if policy not in {"spread", "pack"}:
            raise ValueError("policy must be 'spread' or 'pack'")
        self.policy = policy

    def select_node(
        self,
        nodes: Iterable[CloudNode],
        request: ResourceRequest,
        *,
        zone: Optional[str] = None,
        required_traits: Iterable[str] = (),
        avoid_node_ids: Iterable[str] = (),
    ) -> CloudNode:
        avoid = set(avoid_node_ids)
        candidates = [
            node for node in nodes
            if (zone is None or node.zone == zone)
            and node.node_id not in avoid
            and node.can_host(request, required_traits)
        ]
        if not candidates:
            raise CloudSchedulingError("no healthy cloud node can satisfy request")
        reverse = self.policy == "spread"
        return sorted(candidates, key=lambda n: self._score(n), reverse=reverse)[0]

    @staticmethod
    def _score(node: CloudNode) -> float:
        cpu = node.free_vcpus / node.total_vcpus if node.total_vcpus else 0.0
        memory = node.free_memory_mb / node.total_memory_mb if node.total_memory_mb else 0.0
        storage = node.free_storage_gb / node.total_storage_gb if node.total_storage_gb else 0.0
        return (cpu * 0.45) + (memory * 0.40) + (storage * 0.15)


class CloudOSManager:
    """High-level cloud operating system manager for UmerOS."""

    RATES = {
        "vcpu_hour": 0.015,
        "memory_gb_hour": 0.004,
        "storage_gb_hour": 0.0008,
        "network_gb": 0.02,
    }

    def __init__(
        self,
        *,
        deployment_model: DeploymentModel = DeploymentModel.PRIVATE,
        service_model: ServiceModel = ServiceModel.IAAS,
        scheduler: Optional[CloudScheduler] = None,
        seed_defaults: bool = True,
    ) -> None:
        self.deployment_model = deployment_model
        self.service_model = service_model
        self.scheduler = scheduler or CloudScheduler()
        self.projects: Dict[str, CloudProject] = {}
        self.nodes: Dict[str, CloudNode] = {}
        self.images: Dict[str, CloudImage] = {}
        self.flavors: Dict[str, CloudFlavor] = {}
        self.networks: Dict[str, VirtualNetwork] = {}
        self.volumes: Dict[str, CloudVolume] = {}
        self.instances: Dict[str, CloudInstance] = {}
        self.services: Dict[str, CloudService] = {}
        self.usage_records: List[UsageRecord] = []
        self.events: List[str] = []
        self._counters: Dict[str, int] = {}
        if seed_defaults:
            self._seed_defaults()

    # ------------------------------------------------------------------
    # Catalog and identity
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        *,
        owner: str = "admin",
        quota: Optional[CloudQuota] = None,
        project_id: Optional[str] = None,
    ) -> CloudProject:
        pid = project_id or self._next_id("project")
        project = CloudProject(pid, name, owner=owner, quota=quota or CloudQuota())
        self.projects[pid] = project
        self._event(f"project {pid} created")
        return project

    def register_node(self, node: CloudNode) -> CloudNode:
        self.nodes[node.node_id] = node
        self._event(f"node {node.node_id} registered in {node.zone}")
        return node

    def register_image(self, image: CloudImage) -> CloudImage:
        self.images[image.image_id] = image
        return image

    def register_flavor(self, flavor: CloudFlavor) -> CloudFlavor:
        self.flavors[flavor.flavor_id] = flavor
        return flavor

    def create_network(
        self,
        project_id: str,
        name: str,
        cidr: str,
        *,
        network_id: Optional[str] = None,
    ) -> VirtualNetwork:
        self._project(project_id)
        nid = network_id or self._next_id("net")
        network = VirtualNetwork(nid, project_id, name, cidr)
        self.networks[nid] = network
        self._event(f"network {nid} created for project {project_id}")
        return network

    # ------------------------------------------------------------------
    # Compute lifecycle
    # ------------------------------------------------------------------

    def provision_instance(
        self,
        project_id: str,
        name: str,
        image_id: str,
        flavor_id: str,
        *,
        network_id: Optional[str] = None,
        zone: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        avoid_node_ids: Iterable[str] = (),
        service_id: Optional[str] = None,
    ) -> CloudInstance:
        project = self._project(project_id)
        image = self._image(image_id)
        flavor = self._flavor(flavor_id)
        self._assert_image_fits_flavor(image, flavor)
        request = flavor.request
        project.assert_quota(request)
        network = self._network_for_instance(project_id, network_id)
        required_traits = set(image.traits)

        try:
            node = self.scheduler.select_node(
                self.nodes.values(),
                request,
                zone=zone,
                required_traits=required_traits,
                avoid_node_ids=avoid_node_ids,
            )
        except CloudSchedulingError:
            if avoid_node_ids:
                node = self.scheduler.select_node(
                    self.nodes.values(),
                    request,
                    zone=zone,
                    required_traits=required_traits,
                )
            else:
                raise

        iid = self._next_id("inst")
        port_id = self._next_id("port")
        ip_address = network.allocate_ip(port_id)
        node.allocate(iid, request)
        project.usage.add(request)
        instance = CloudInstance(
            instance_id=iid,
            project_id=project_id,
            name=name,
            image_id=image_id,
            flavor_id=flavor_id,
            node_id=node.node_id,
            zone=node.zone,
            request=request,
            network_id=network.network_id,
            port_id=port_id,
            ip_address=ip_address,
            service_id=service_id,
            metadata=dict(metadata or {}),
        )
        self.instances[iid] = instance
        self._event(f"instance {iid} running on {node.node_id}")
        return instance

    def terminate_instance(self, instance_id: str) -> bool:
        instance = self._instance(instance_id)
        if instance.state == InstanceState.TERMINATED:
            return False
        project = self._project(instance.project_id)
        node = self.nodes.get(instance.node_id)
        if node is not None:
            node.release(instance_id, instance.request)
        network = self.networks.get(instance.network_id)
        if network is not None:
            network.release_ip(instance.port_id)
        project.usage.remove(instance.request)
        for volume in self.volumes.values():
            if volume.attached_to == instance_id:
                volume.attached_to = None
        instance.state = InstanceState.TERMINATED
        self._event(f"instance {instance_id} terminated")
        return True

    def migrate_instance(self, instance_id: str, *, target_zone: Optional[str] = None) -> CloudInstance:
        instance = self._instance(instance_id)
        if instance.state != InstanceState.RUNNING:
            raise CloudError(f"instance {instance_id} is not running")
        old_node = self._node(instance.node_id)
        instance.state = InstanceState.MIGRATING
        try:
            new_node = self.scheduler.select_node(
                self.nodes.values(),
                instance.request,
                zone=target_zone,
                avoid_node_ids={old_node.node_id},
            )
            old_node.release(instance_id, instance.request)
            new_node.allocate(instance_id, instance.request)
            instance.node_id = new_node.node_id
            instance.zone = new_node.zone
            self._event(f"instance {instance_id} migrated to {new_node.node_id}")
        finally:
            instance.state = InstanceState.RUNNING
        return instance

    # ------------------------------------------------------------------
    # Storage and services
    # ------------------------------------------------------------------

    def create_volume(
        self,
        project_id: str,
        name: str,
        size_gb: int,
        *,
        volume_id: Optional[str] = None,
    ) -> CloudVolume:
        if size_gb <= 0:
            raise ValueError("size_gb must be positive")
        project = self._project(project_id)
        if project.usage.volumes + 1 > project.quota.max_volumes:
            raise CloudQuotaError(f"project {project_id} volume quota exceeded")
        if project.usage.storage_gb + size_gb > project.quota.max_storage_gb:
            raise CloudQuotaError(f"project {project_id} storage quota exceeded")
        vid = volume_id or self._next_id("vol")
        volume = CloudVolume(vid, project_id, name, size_gb)
        self.volumes[vid] = volume
        project.usage.volumes += 1
        project.usage.storage_gb += size_gb
        self._event(f"volume {vid} created")
        return volume

    def attach_volume(self, volume_id: str, instance_id: str) -> CloudVolume:
        volume = self._volume(volume_id)
        instance = self._instance(instance_id)
        if volume.project_id != instance.project_id:
            raise CloudError("volume and instance must belong to the same project")
        volume.attached_to = instance_id
        self._event(f"volume {volume_id} attached to {instance_id}")
        return volume

    def create_service(
        self,
        project_id: str,
        name: str,
        image_id: str,
        flavor_id: str,
        *,
        replicas: int = 1,
        network_id: Optional[str] = None,
        zone: Optional[str] = None,
    ) -> CloudService:
        if replicas < 0:
            raise ValueError("replicas cannot be negative")
        network = self._network_for_instance(project_id, network_id)
        sid = self._next_id("svc")
        service = CloudService(
            service_id=sid,
            project_id=project_id,
            name=name,
            image_id=image_id,
            flavor_id=flavor_id,
            desired_replicas=0,
            network_id=network.network_id,
            zone=zone,
            endpoint=f"https://{name}.apps.umeros.local",
        )
        self.services[sid] = service
        self.reconcile_service(sid, replicas)
        return service

    def reconcile_service(self, service_id: str, replicas: Optional[int] = None) -> CloudService:
        service = self._service(service_id)
        target = service.desired_replicas if replicas is None else replicas
        if target < 0:
            raise ValueError("replicas cannot be negative")
        service.state = ServiceState.SCALING
        current = len(service.instance_ids)
        if target > current:
            avoid = {
                self.instances[iid].node_id
                for iid in service.instance_ids
                if iid in self.instances and self.instances[iid].state == InstanceState.RUNNING
            }
            for idx in range(current, target):
                instance = self.provision_instance(
                    service.project_id,
                    f"{service.name}-{idx + 1}",
                    service.image_id,
                    service.flavor_id,
                    network_id=service.network_id,
                    zone=service.zone,
                    metadata={"service": service.name},
                    avoid_node_ids=avoid,
                    service_id=service_id,
                )
                service.instance_ids.append(instance.instance_id)
                avoid.add(instance.node_id)
        elif target < current:
            for iid in list(reversed(service.instance_ids[target:])):
                self.terminate_instance(iid)
                service.instance_ids.remove(iid)
        service.desired_replicas = target
        service.state = (
            ServiceState.ACTIVE
            if len(service.instance_ids) == target
            else ServiceState.DEGRADED
        )
        self._event(f"service {service_id} reconciled to {target} replicas")
        return service

    def autoscale_service(
        self,
        service_id: str,
        *,
        observed_cpu_percent: float,
        min_replicas: int = 1,
        max_replicas: int = 10,
        target_cpu_percent: float = 65.0,
    ) -> CloudService:
        if target_cpu_percent <= 0:
            raise ValueError("target_cpu_percent must be positive")
        service = self._service(service_id)
        current = max(1, len(service.instance_ids))
        desired = math.ceil(current * observed_cpu_percent / target_cpu_percent)
        desired = max(min_replicas, min(max_replicas, desired))
        return self.reconcile_service(service_id, desired)

    # ------------------------------------------------------------------
    # Metering and dashboard
    # ------------------------------------------------------------------

    def record_usage(
        self,
        instance_id: str,
        *,
        seconds: int,
        network_gb: float = 0.0,
    ) -> UsageRecord:
        if seconds < 0:
            raise ValueError("seconds cannot be negative")
        instance = self._instance(instance_id)
        record = UsageRecord(
            project_id=instance.project_id,
            resource_id=instance_id,
            seconds=seconds,
            vcpu_seconds=instance.request.vcpus * seconds,
            memory_mb_seconds=instance.request.memory_mb * seconds,
            storage_gb_seconds=instance.request.storage_gb * seconds,
            network_gb=network_gb,
        )
        self.usage_records.append(record)
        return record

    def project_cost(self, project_id: str) -> float:
        self._project(project_id)
        total = 0.0
        for record in self.usage_records:
            if record.project_id != project_id:
                continue
            hours = record.seconds / 3600.0
            total += (record.vcpu_seconds / 3600.0) * self.RATES["vcpu_hour"]
            total += ((record.memory_mb_seconds / 1024.0) / 3600.0) * self.RATES["memory_gb_hour"]
            total += (record.storage_gb_seconds / 3600.0) * self.RATES["storage_gb_hour"]
            total += record.network_gb * self.RATES["network_gb"]
            if hours == 0:
                continue
        return round(total, 4)

    def dashboard_snapshot(self) -> Dict[str, Any]:
        """Return a serializable state model for UI and tests."""
        total_vcpus = sum(n.total_vcpus for n in self.nodes.values())
        used_vcpus = sum(n.used_vcpus for n in self.nodes.values())
        total_memory = sum(n.total_memory_mb for n in self.nodes.values())
        used_memory = sum(n.used_memory_mb for n in self.nodes.values())
        total_storage = sum(n.total_storage_gb for n in self.nodes.values())
        used_storage = sum(n.used_storage_gb for n in self.nodes.values())
        running = [i for i in self.instances.values() if i.state == InstanceState.RUNNING]
        return {
            "deployment_model": self.deployment_model.value,
            "service_model": self.service_model.value,
            "capacity": {
                "vcpus": {"used": used_vcpus, "total": total_vcpus},
                "memory_mb": {"used": used_memory, "total": total_memory},
                "storage_gb": {"used": used_storage, "total": total_storage},
            },
            "nodes": [
                {
                    "id": n.node_id,
                    "host": n.hostname,
                    "zone": n.zone,
                    "healthy": n.healthy,
                    "enabled": n.enabled,
                    "instances": len(n.instance_ids),
                    "utilization": n.utilization(),
                    "traits": sorted(n.traits),
                }
                for n in sorted(self.nodes.values(), key=lambda item: item.node_id)
            ],
            "projects": [
                {
                    "id": p.project_id,
                    "name": p.name,
                    "owner": p.owner,
                    "usage": p.usage.to_dict(),
                    "quota": p.quota.__dict__.copy(),
                    "cost": self.project_cost(p.project_id),
                }
                for p in sorted(self.projects.values(), key=lambda item: item.project_id)
            ],
            "instances": [
                {
                    "id": i.instance_id,
                    "name": i.name,
                    "project_id": i.project_id,
                    "node_id": i.node_id,
                    "zone": i.zone,
                    "ip": i.ip_address,
                    "state": i.state.value,
                    "vcpus": i.request.vcpus,
                    "memory_mb": i.request.memory_mb,
                    "storage_gb": i.request.storage_gb,
                    "service_id": i.service_id,
                }
                for i in sorted(running, key=lambda item: item.instance_id)
            ],
            "services": [
                {
                    "id": s.service_id,
                    "name": s.name,
                    "project_id": s.project_id,
                    "desired": s.desired_replicas,
                    "ready": s.ready_replicas,
                    "state": s.state.value,
                    "endpoint": s.endpoint,
                    "instances": list(s.instance_ids),
                }
                for s in sorted(self.services.values(), key=lambda item: item.service_id)
            ],
            "networks": [
                {
                    "id": n.network_id,
                    "project_id": n.project_id,
                    "name": n.name,
                    "cidr": n.cidr,
                    "ports": len(n.allocated_ips),
                    "gateway": n.gateway,
                }
                for n in sorted(self.networks.values(), key=lambda item: item.network_id)
            ],
            "events": list(self.events[-8:]),
        }

    def service_catalog(self) -> Dict[str, Any]:
        """Describe the cloud OS features exposed by this package."""
        return {
            "essential_characteristics": [
                "on_demand_self_service",
                "broad_network_access",
                "resource_pooling",
                "rapid_elasticity",
                "measured_service",
            ],
            "service_models": [model.value for model in ServiceModel],
            "deployment_models": [model.value for model in DeploymentModel],
            "objects": [
                "project",
                "quota",
                "node",
                "image",
                "flavor",
                "network",
                "volume",
                "instance",
                "service",
            ],
        }

    @classmethod
    def demo(cls) -> "CloudOSManager":
        cloud = cls(seed_defaults=True)
        project = cloud.create_project(
            "Research Cloud",
            owner="umer",
            quota=CloudQuota(max_instances=20, max_vcpus=64, max_memory_mb=131_072),
            project_id="project-demo",
        )
        network = cloud.create_network(project.project_id, "research-vpc", "10.42.0.0/24")
        api = cloud.create_service(
            project.project_id,
            "notebook-api",
            "img-umeros-cloud",
            "flavor-small",
            replicas=2,
            network_id=network.network_id,
        )
        cloud.record_usage(api.instance_ids[0], seconds=3600, network_gb=1.2)
        cloud.record_usage(api.instance_ids[1], seconds=3600, network_gb=0.7)
        return cloud

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        self.register_flavor(CloudFlavor("flavor-nano", "Nano", 1, 1024, 10))
        self.register_flavor(CloudFlavor("flavor-small", "Small", 2, 4096, 40))
        self.register_flavor(CloudFlavor("flavor-medium", "Medium", 4, 8192, 80))
        self.register_flavor(CloudFlavor("flavor-gpu", "GPU Worker", 8, 24_576, 160))
        self.register_image(
            CloudImage(
                "img-umeros-cloud",
                "UmerOS Cloud Runtime",
                "umeros",
                "3.0",
                min_vcpus=1,
                min_memory_mb=1024,
                min_disk_gb=10,
            )
        )
        self.register_image(
            CloudImage(
                "img-umeros-ai",
                "UmerOS AI Worker",
                "umeros",
                "3.0-ai",
                min_vcpus=4,
                min_memory_mb=8192,
                min_disk_gb=80,
                traits={"gpu"},
            )
        )
        self.register_node(
            CloudNode(
                "node-edge-1",
                "edge-1",
                "edge-a",
                total_vcpus=16,
                total_memory_mb=65_536,
                total_storage_gb=1_000,
                traits={"ssd", "edge"},
            )
        )
        self.register_node(
            CloudNode(
                "node-core-1",
                "core-1",
                "core-a",
                total_vcpus=32,
                total_memory_mb=131_072,
                total_storage_gb=2_000,
                traits={"ssd", "ha"},
            )
        )
        self.register_node(
            CloudNode(
                "node-gpu-1",
                "gpu-1",
                "core-gpu",
                total_vcpus=24,
                total_memory_mb=98_304,
                total_storage_gb=1_500,
                traits={"ssd", "gpu"},
            )
        )

    def _network_for_instance(self, project_id: str, network_id: Optional[str]) -> VirtualNetwork:
        if network_id:
            network = self._network(network_id)
            if network.project_id != project_id:
                raise CloudError("network belongs to another project")
            return network
        for network in self.networks.values():
            if network.project_id == project_id:
                return network
        return self.create_network(project_id, "default", self._next_cidr())

    def _next_cidr(self) -> str:
        offset = len(self.networks) + 10
        return f"10.{offset}.0.0/24"

    def _assert_image_fits_flavor(self, image: CloudImage, flavor: CloudFlavor) -> None:
        if flavor.vcpus < image.min_vcpus:
            raise CloudSchedulingError("flavor vcpus below image minimum")
        if flavor.memory_mb < image.min_memory_mb:
            raise CloudSchedulingError("flavor memory below image minimum")
        if flavor.disk_gb < image.min_disk_gb:
            raise CloudSchedulingError("flavor disk below image minimum")

    def _next_id(self, prefix: str) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}-{self._counters[prefix]:04d}"

    def _event(self, message: str) -> None:
        self.events.append(message)

    def _project(self, project_id: str) -> CloudProject:
        try:
            return self.projects[project_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"project not found: {project_id}") from exc

    def _node(self, node_id: str) -> CloudNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"node not found: {node_id}") from exc

    def _image(self, image_id: str) -> CloudImage:
        try:
            return self.images[image_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"image not found: {image_id}") from exc

    def _flavor(self, flavor_id: str) -> CloudFlavor:
        try:
            return self.flavors[flavor_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"flavor not found: {flavor_id}") from exc

    def _network(self, network_id: str) -> VirtualNetwork:
        try:
            return self.networks[network_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"network not found: {network_id}") from exc

    def _volume(self, volume_id: str) -> CloudVolume:
        try:
            return self.volumes[volume_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"volume not found: {volume_id}") from exc

    def _instance(self, instance_id: str) -> CloudInstance:
        try:
            return self.instances[instance_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"instance not found: {instance_id}") from exc

    def _service(self, service_id: str) -> CloudService:
        try:
            return self.services[service_id]
        except KeyError as exc:
            raise CloudNotFoundError(f"service not found: {service_id}") from exc
