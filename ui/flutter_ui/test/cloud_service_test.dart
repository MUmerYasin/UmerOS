import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/src/apps/cloud_app.dart';
import 'package:flutter_ui/src/services/cloud_service.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _snapshot = <String, dynamic>{
  'deployment_model': 'private',
  'service_model': 'iaas',
  'capacity': {
    'vcpus': {'used': 2, 'total': 72},
    'memory_mb': {'used': 4096, 'total': 294912},
    'storage_gb': {'used': 40, 'total': 4500},
  },
  'nodes': [
    {
      'id': 'node-core-1',
      'host': 'core-1',
      'zone': 'core-a',
      'healthy': true,
      'enabled': true,
      'instances': 1,
      'utilization': {'cpu': 0.1, 'memory': 0.1, 'storage': 0.1},
      'traits': ['ssd'],
    },
  ],
  'projects': [
    {
      'id': 'project-demo',
      'name': 'Research Cloud',
      'owner': 'umer',
      'usage': {
        'instances': 1,
        'vcpus': 2,
        'memory_mb': 4096,
        'storage_gb': 40,
      },
      'quota': {
        'max_instances': 20,
        'max_vcpus': 64,
        'max_memory_mb': 131072,
        'max_storage_gb': 1024,
      },
      'cost': 0.18,
    },
  ],
  'services': [
    {
      'id': 'svc-0001',
      'name': 'notebook-api',
      'project_id': 'project-demo',
      'desired': 2,
      'ready': 2,
      'state': 'active',
      'endpoint': 'https://notebook-api.apps.umeros.local',
    },
  ],
  'events': ['service svc-0001 reconciled to 2 replicas'],
};

const _catalog = <String, dynamic>{
  'projects': [
    {'id': 'project-demo', 'name': 'Research Cloud'},
  ],
  'images': [
    {'id': 'img-umeros-cloud', 'name': 'UmerOS Cloud Runtime'},
  ],
  'flavors': [
    {
      'id': 'flavor-small',
      'name': 'Small',
      'vcpus': 2,
      'memory_mb': 4096,
      'disk_gb': 40,
    },
  ],
  'networks': [
    {'id': 'net-0001', 'project_id': 'project-demo', 'name': 'research-vpc'},
  ],
};

void main() {
  test('client parses a snapshot and includes a configured token', () async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/cloud/v1/snapshot');
      expect(request.headers['X-UmerOS-Token'], 'test-token');
      return http.Response(jsonEncode(_snapshot), 200);
    });
    final service = CloudService(
      client: client,
      baseUri: Uri.parse('http://127.0.0.1:8422/'),
      apiToken: 'test-token',
    );

    final snapshot = await service.getSnapshot();

    expect(snapshot.capacity.vcpus.total, 72);
    expect(snapshot.services.single.name, 'notebook-api');
    expect(snapshot.projects.single.cost, 0.18);
  });

  testWidgets('cloud screen renders a live cloud snapshot', (tester) async {
    final client = MockClient((request) async {
      return switch (request.url.path) {
        '/api/cloud/v1/snapshot' => http.Response(jsonEncode(_snapshot), 200),
        '/api/cloud/v1/catalog' => http.Response(jsonEncode(_catalog), 200),
        _ => http.Response(jsonEncode({'detail': 'not found'}), 404),
      };
    });
    final service = CloudService(
      client: client,
      baseUri: Uri.parse('http://127.0.0.1:8422/'),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CloudApp(service: service)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Private Cloud Pool'), findsOneWidget);
    expect(find.text('core-1'), findsOneWidget);
    expect(find.text('Cloud control service unavailable'), findsNothing);
  });
}
