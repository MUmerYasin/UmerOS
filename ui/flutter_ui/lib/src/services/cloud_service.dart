/// Typed client for the loopback-only UmerOS Cloud Control API.
///
/// The API describes a simulation-safe cloud control plane. It models
/// placement and lifecycle state but does not create host VMs, containers,
/// disks, or network namespaces.
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class CloudServiceException implements Exception {
  CloudServiceException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() =>
      'CloudServiceException${statusCode == null ? '' : ' [$statusCode]'}: $message';
}

class CloudService {
  CloudService({
    http.Client? client,
    Uri? baseUri,
    String? apiToken,
    Duration? timeout,
  }) : _client = client ?? http.Client(),
       _ownsClient = client == null,
       _baseUri = baseUri ?? Uri.parse(_defaultBaseUrl),
       _apiToken = apiToken ?? _defaultApiToken,
       _timeout = timeout ?? const Duration(seconds: 10);

  static const _defaultBaseUrl = String.fromEnvironment(
    'UMEROS_CLOUD_URL',
    defaultValue: 'http://127.0.0.1:8422/',
  );
  static const _defaultApiToken = String.fromEnvironment(
    'UMEROS_CLOUD_API_TOKEN',
  );

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUri;
  final String _apiToken;
  final Duration _timeout;

  Future<bool> checkHealth() async {
    try {
      final response = await _request('GET', '/health');
      return response['status'] == 'ok';
    } on CloudServiceException {
      return false;
    }
  }

  Future<CloudSnapshot> getSnapshot() async {
    return CloudSnapshot.fromJson(
      await _request('GET', '/api/cloud/v1/snapshot'),
    );
  }

  Future<CloudCatalog> getCatalog() async {
    return CloudCatalog.fromJson(
      await _request('GET', '/api/cloud/v1/catalog'),
    );
  }

  Future<CloudSnapshot> deploy(CloudDeployRequest request) async {
    return CloudSnapshot.fromJson(
      await _request('POST', '/api/cloud/v1/services', body: request.toJson()),
    );
  }

  Future<CloudSnapshot> scaleService(String serviceId, int replicas) async {
    return CloudSnapshot.fromJson(
      await _request(
        'POST',
        '/api/cloud/v1/services/$serviceId/scale',
        body: {'replicas': replicas},
      ),
    );
  }

  Future<CloudSnapshot> autoscaleService(
    String serviceId, {
    required double observedCpuPercent,
    int minReplicas = 1,
    int maxReplicas = 10,
    double targetCpuPercent = 65,
  }) async {
    return CloudSnapshot.fromJson(
      await _request(
        'POST',
        '/api/cloud/v1/services/$serviceId/autoscale',
        body: {
          'observed_cpu_percent': observedCpuPercent,
          'min_replicas': minReplicas,
          'max_replicas': maxReplicas,
          'target_cpu_percent': targetCpuPercent,
        },
      ),
    );
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final headers = <String, String>{'Accept': 'application/json'};
    if (_apiToken.isNotEmpty) {
      headers['X-UmerOS-Token'] = _apiToken;
    }
    if (body != null) {
      headers['Content-Type'] = 'application/json';
    }

    final uri = _baseUri.resolve(path);
    try {
      final response = switch (method) {
        'POST' =>
          await _client
              .post(
                uri,
                headers: headers,
                body: body == null ? null : jsonEncode(body),
              )
              .timeout(_timeout),
        _ => await _client.get(uri, headers: headers).timeout(_timeout),
      };

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw CloudServiceException(
          _errorMessage(response.body),
          statusCode: response.statusCode,
        );
      }

      final decoded = jsonDecode(response.body);
      if (decoded is! Map) {
        throw CloudServiceException('Cloud API returned an invalid response.');
      }
      return Map<String, dynamic>.from(decoded);
    } on TimeoutException {
      throw CloudServiceException('Cloud service did not respond in time.');
    } on http.ClientException catch (error) {
      throw CloudServiceException(
        'Cloud service is unavailable (${error.message}).',
      );
    } on FormatException {
      throw CloudServiceException('Cloud API returned malformed JSON.');
    }
  }

  String _errorMessage(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] != null) {
        return decoded['detail'].toString();
      }
    } on FormatException {
      // The response body is still a useful fallback message.
    }
    return body.isEmpty ? 'Cloud API request failed.' : body;
  }

  void dispose() {
    if (_ownsClient) {
      _client.close();
    }
  }
}

class CloudDeployRequest {
  const CloudDeployRequest({
    required this.projectId,
    required this.name,
    required this.imageId,
    required this.flavorId,
    required this.replicas,
    this.networkId,
    this.zone,
  });

  final String projectId;
  final String name;
  final String imageId;
  final String flavorId;
  final int replicas;
  final String? networkId;
  final String? zone;

  Map<String, dynamic> toJson() => {
    'project_id': projectId,
    'name': name,
    'image_id': imageId,
    'flavor_id': flavorId,
    'replicas': replicas,
    if (networkId != null) 'network_id': networkId,
    if (zone != null) 'zone': zone,
  };
}

class CloudSnapshot {
  const CloudSnapshot({
    required this.deploymentModel,
    required this.serviceModel,
    required this.capacity,
    required this.nodes,
    required this.projects,
    required this.services,
    required this.events,
  });

  factory CloudSnapshot.fromJson(Map<String, dynamic> json) => CloudSnapshot(
    deploymentModel: json['deployment_model'] as String? ?? 'private',
    serviceModel: json['service_model'] as String? ?? 'iaas',
    capacity: CloudCapacity.fromJson(_map(json['capacity'])),
    nodes: _maps(json['nodes']).map(CloudNodeStatus.fromJson).toList(),
    projects: _maps(json['projects']).map(CloudProjectStatus.fromJson).toList(),
    services: _maps(json['services']).map(CloudWorkload.fromJson).toList(),
    events: ((json['events'] as List?) ?? const [])
        .map((item) => item.toString())
        .toList(),
  );

  final String deploymentModel;
  final String serviceModel;
  final CloudCapacity capacity;
  final List<CloudNodeStatus> nodes;
  final List<CloudProjectStatus> projects;
  final List<CloudWorkload> services;
  final List<String> events;

  int get runningReplicas =>
      services.fold(0, (total, service) => total + service.ready);
}

class CloudCapacity {
  const CloudCapacity({
    required this.vcpus,
    required this.memoryMb,
    required this.storageGb,
  });

  factory CloudCapacity.fromJson(Map<String, dynamic> json) => CloudCapacity(
    vcpus: CloudResource.fromJson(_map(json['vcpus'])),
    memoryMb: CloudResource.fromJson(_map(json['memory_mb'])),
    storageGb: CloudResource.fromJson(_map(json['storage_gb'])),
  );

  final CloudResource vcpus;
  final CloudResource memoryMb;
  final CloudResource storageGb;
}

class CloudResource {
  const CloudResource({required this.used, required this.total});

  factory CloudResource.fromJson(Map<String, dynamic> json) => CloudResource(
    used: (json['used'] as num?)?.toInt() ?? 0,
    total: (json['total'] as num?)?.toInt() ?? 0,
  );

  final int used;
  final int total;

  double get ratio => total == 0 ? 0 : used / total;
}

class CloudNodeStatus {
  const CloudNodeStatus({
    required this.id,
    required this.host,
    required this.zone,
    required this.healthy,
    required this.enabled,
    required this.instances,
    required this.cpu,
    required this.memory,
    required this.storage,
    required this.traits,
  });

  factory CloudNodeStatus.fromJson(Map<String, dynamic> json) {
    final utilization = _map(json['utilization']);
    return CloudNodeStatus(
      id: json['id'] as String? ?? '',
      host: json['host'] as String? ?? '',
      zone: json['zone'] as String? ?? '',
      healthy: json['healthy'] as bool? ?? false,
      enabled: json['enabled'] as bool? ?? false,
      instances: (json['instances'] as num?)?.toInt() ?? 0,
      cpu: (utilization['cpu'] as num?)?.toDouble() ?? 0,
      memory: (utilization['memory'] as num?)?.toDouble() ?? 0,
      storage: (utilization['storage'] as num?)?.toDouble() ?? 0,
      traits: ((json['traits'] as List?) ?? const [])
          .map((item) => item.toString())
          .toList(),
    );
  }

  final String id;
  final String host;
  final String zone;
  final bool healthy;
  final bool enabled;
  final int instances;
  final double cpu;
  final double memory;
  final double storage;
  final List<String> traits;
}

class CloudProjectStatus {
  const CloudProjectStatus({
    required this.id,
    required this.name,
    required this.owner,
    required this.usage,
    required this.quota,
    required this.cost,
  });

  factory CloudProjectStatus.fromJson(Map<String, dynamic> json) =>
      CloudProjectStatus(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        owner: json['owner'] as String? ?? '',
        usage: _map(json['usage']),
        quota: _map(json['quota']),
        cost: (json['cost'] as num?)?.toDouble() ?? 0,
      );

  final String id;
  final String name;
  final String owner;
  final Map<String, dynamic> usage;
  final Map<String, dynamic> quota;
  final double cost;

  double ratioFor(String name) {
    final used = (usage[name] as num?)?.toDouble() ?? 0;
    final total = (quota['max_$name'] as num?)?.toDouble() ?? 0;
    return total == 0 ? 0 : used / total;
  }
}

class CloudWorkload {
  const CloudWorkload({
    required this.id,
    required this.name,
    required this.projectId,
    required this.desired,
    required this.ready,
    required this.state,
    required this.endpoint,
  });

  factory CloudWorkload.fromJson(Map<String, dynamic> json) => CloudWorkload(
    id: json['id'] as String? ?? '',
    name: json['name'] as String? ?? '',
    projectId: json['project_id'] as String? ?? '',
    desired: (json['desired'] as num?)?.toInt() ?? 0,
    ready: (json['ready'] as num?)?.toInt() ?? 0,
    state: json['state'] as String? ?? 'unknown',
    endpoint: json['endpoint'] as String? ?? '',
  );

  final String id;
  final String name;
  final String projectId;
  final int desired;
  final int ready;
  final String state;
  final String endpoint;
}

class CloudCatalog {
  const CloudCatalog({
    required this.projects,
    required this.images,
    required this.flavors,
    required this.networks,
  });

  factory CloudCatalog.fromJson(Map<String, dynamic> json) => CloudCatalog(
    projects: _maps(
      json['projects'],
    ).map(CloudCatalogProject.fromJson).toList(),
    images: _maps(json['images']).map(CloudCatalogImage.fromJson).toList(),
    flavors: _maps(json['flavors']).map(CloudCatalogFlavor.fromJson).toList(),
    networks: _maps(
      json['networks'],
    ).map(CloudCatalogNetwork.fromJson).toList(),
  );

  final List<CloudCatalogProject> projects;
  final List<CloudCatalogImage> images;
  final List<CloudCatalogFlavor> flavors;
  final List<CloudCatalogNetwork> networks;
}

class CloudCatalogProject {
  const CloudCatalogProject({required this.id, required this.name});

  factory CloudCatalogProject.fromJson(Map<String, dynamic> json) =>
      CloudCatalogProject(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
      );

  final String id;
  final String name;
}

class CloudCatalogImage {
  const CloudCatalogImage({required this.id, required this.name});

  factory CloudCatalogImage.fromJson(Map<String, dynamic> json) =>
      CloudCatalogImage(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
      );

  final String id;
  final String name;
}

class CloudCatalogFlavor {
  const CloudCatalogFlavor({
    required this.id,
    required this.name,
    required this.vcpus,
    required this.memoryMb,
    required this.diskGb,
  });

  factory CloudCatalogFlavor.fromJson(Map<String, dynamic> json) =>
      CloudCatalogFlavor(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        vcpus: (json['vcpus'] as num?)?.toInt() ?? 0,
        memoryMb: (json['memory_mb'] as num?)?.toInt() ?? 0,
        diskGb: (json['disk_gb'] as num?)?.toInt() ?? 0,
      );

  final String id;
  final String name;
  final int vcpus;
  final int memoryMb;
  final int diskGb;
}

class CloudCatalogNetwork {
  const CloudCatalogNetwork({
    required this.id,
    required this.projectId,
    required this.name,
  });

  factory CloudCatalogNetwork.fromJson(Map<String, dynamic> json) =>
      CloudCatalogNetwork(
        id: json['id'] as String? ?? '',
        projectId: json['project_id'] as String? ?? '',
        name: json['name'] as String? ?? '',
      );

  final String id;
  final String projectId;
  final String name;
}

Map<String, dynamic> _map(Object? value) {
  return value is Map ? Map<String, dynamic>.from(value) : const {};
}

List<Map<String, dynamic>> _maps(Object? value) {
  return value is List
      ? value
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList()
      : const [];
}
