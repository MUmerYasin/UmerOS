/// UmerOS Flutter UI — AI Service client
/// ======================================
/// Typed HTTP client for the UmerOS AI backend (`ai/server.py`,
/// FastAPI on 127.0.0.1:8421). Real data only — when the backend is
/// unreachable, calls throw [AiServiceException] and the UI shows a
/// clear offline state (no simulated fallback).
///
/// Supports SSE streaming for chat so tokens render as they arrive.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

class AiServiceException implements Exception {
  AiServiceException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() =>
      'AiServiceException${statusCode != null ? ' [$statusCode]' : ''}: $message';
}

// ── models ────────────────────────────────────────────────────────────────

enum ProviderKind { local, freeOnline, paidOnline }

ProviderKind kindFromString(String s) => switch (s) {
      'free-online' => ProviderKind.freeOnline,
      'paid-online' => ProviderKind.paidOnline,
      _ => ProviderKind.local,
    };

extension ProviderKindLabel on ProviderKind {
  String get groupLabel => switch (this) {
        ProviderKind.local => 'Local',
        ProviderKind.freeOnline => 'Free Online',
        ProviderKind.paidOnline => 'Paid Online',
      };
}

class AiProviderInfo {
  AiProviderInfo({
    required this.id,
    required this.name,
    required this.kind,
    required this.available,
    required this.consentGranted,
    required this.models,
    required this.streaming,
  });

  factory AiProviderInfo.fromJson(Map<String, dynamic> j) => AiProviderInfo(
        id: j['id'] as String,
        name: j['name'] as String,
        kind: kindFromString(j['kind'] as String? ?? 'local'),
        available: j['available'] as bool? ?? false,
        consentGranted: j['consent'] as bool? ?? false,
        models: ((j['models'] as List?) ?? const [])
            .whereType<String>()
            .toList(),
        streaming: j['streaming'] as bool? ?? false,
      );

  final String id;
  final String name;
  final ProviderKind kind;
  final bool available;
  final bool consentGranted;
  final List<String> models;
  final bool streaming;

  AiProviderInfo copyWith({bool? consentGranted}) => AiProviderInfo(
        id: id,
        name: name,
        kind: kind,
        available: available,
        consentGranted: consentGranted ?? this.consentGranted,
        models: models,
        streaming: streaming,
      );
}

class ChatResult {
  ChatResult({required this.reply, required this.providerId});

  factory ChatResult.fromJson(Map<String, dynamic> j) => ChatResult(
        reply: j['reply'] as String? ?? '',
        providerId: j['provider'] as String? ?? '',
      );

  final String reply;
  final String providerId;
}

class AiStatus {
  AiStatus({
    required this.backendUp,
    this.activeProvider,
    required this.onlineReady,
    required this.localReady,
    required this.ollamaInstalled,
    required this.llamacppRuntime,
    required this.installedModels,
  });

  factory AiStatus.offline() => AiStatus(
        backendUp: false,
        onlineReady: const [],
        localReady: const [],
        ollamaInstalled: false,
        llamacppRuntime: false,
        installedModels: const [],
      );

  factory AiStatus.fromJson(Map<String, dynamic> j) => AiStatus(
        backendUp: true,
        activeProvider: j['active_provider'] as String?,
        onlineReady: ((j['online_providers_ready'] as List?) ?? const [])
            .whereType<String>()
            .toList(),
        localReady: ((j['local_providers_ready'] as List?) ?? const [])
            .whereType<String>()
            .toList(),
        ollamaInstalled: j['ollama_installed'] as bool? ?? false,
        llamacppRuntime: j['llamacpp_runtime_installed'] as bool? ?? false,
        installedModels: ((j['installed_models'] as List?) ?? const [])
            .whereType<String>()
            .toList(),
      );

  final bool backendUp;
  final String? activeProvider;
  final List<String> onlineReady;
  final List<String> localReady;
  final bool ollamaInstalled;
  final bool llamacppRuntime;
  final List<String> installedModels;
}

class CatalogModel {
  CatalogModel({
    required this.id,
    required this.filename,
    required this.title,
    required this.params,
    required this.quant,
    required this.sizeGb,
    required this.description,
    required this.installed,
  });

  factory CatalogModel.fromJson(Map<String, dynamic> j) => CatalogModel(
        id: j['id'] as String,
        filename: j['filename'] as String,
        title: j['title'] as String,
        params: j['params'] as String? ?? '',
        quant: j['quant'] as String? ?? '',
        sizeGb: (j['size_gb'] as num?)?.toDouble() ?? 0,
        description: j['description'] as String? ?? '',
        installed: j['installed'] as bool? ?? false,
      );

  final String id;
  final String filename;
  final String title;
  final String params;
  final String quant;
  final double sizeGb;
  final String description;
  final bool installed;
}

class DownloadJob {
  DownloadJob({
    required this.modelId,
    required this.filename,
    required this.title,
    required this.status,
    required this.progress,
    required this.downloadedMb,
    required this.totalMb,
    this.error = '',
  });

  factory DownloadJob.fromJson(Map<String, dynamic> j) => DownloadJob(
        modelId: j['model_id'] as String,
        filename: j['filename'] as String,
        title: j['title'] as String? ?? j['model_id'] as String,
        status: j['status'] as String? ?? 'queued',
        progress: (j['progress'] as num?)?.toDouble() ?? 0,
        downloadedMb: (j['downloaded_mb'] as num?)?.toDouble() ?? 0,
        totalMb: (j['total_mb'] as num?)?.toDouble() ?? 0,
        error: j['error'] as String? ?? '',
      );

  final String modelId;
  final String filename;
  final String title;
  final String status; // queued|downloading|done|error|cancelled
  final double progress;
  final double downloadedMb;
  final double totalMb;
  final String error;

  bool get isActive => status == 'queued' || status == 'downloading';
}

// ── service ──────────────────────────────────────────────────────────────

typedef VoidCall = void Function();

class AiService {
  AiService._();

  /// Process-wide client. Tests may swap it via [AiService.testOverride].
  static AiService instance = AiService._();

  static VoidCall testOverride(AiService fake) {
    final real = instance;
    instance = fake;
    return () => instance = real;
  }

  static const String defaultBaseUrl = 'http://127.0.0.1:8421';

  String baseUrl = defaultBaseUrl;

  static const Duration _timeout = Duration(seconds: 180);

  HttpClient? _client;
  HttpClient get _http =>
      _client ??= HttpClient()..connectionTimeout = const Duration(seconds: 8);

  // ── plumbing ────────────────────────────────────────────────────────────

  Future<dynamic> _request(String method, String path,
      {Map<String, dynamic>? body, Duration? timeout}) async {
    final uri = Uri.parse('$baseUrl$path');
    final effectiveTimeout = timeout ?? _timeout;
    try {
      final future = switch (method) {
        'POST' => _http.postUrl(uri),
        'PATCH' => _http.patchUrl(uri),
        'DELETE' => _http.deleteUrl(uri),
        _ => _http.getUrl(uri),
      };
      final rq = await future.timeout(const Duration(seconds: 10));
      if (body != null) {
        rq.headers.contentType = ContentType.json;
        rq.write(jsonEncode(body));
      }
      final rs = await rq.close().timeout(effectiveTimeout);
      return _decode(rs);
    } on SocketException catch (e) {
      throw AiServiceException('AI backend unreachable (${e.message})');
    } on HttpException catch (e) {
      throw AiServiceException('AI backend unreachable (${e.message})');
    } on TimeoutException {
      throw AiServiceException('AI backend timed out.');
    }
  }

  Future<dynamic> _decode(HttpClientResponse rs) async {
    final text = await rs.transform(utf8.decoder).join();
    Map<String, dynamic>? errBody;
    try {
      final decoded = jsonDecode(text);
      if (decoded is Map<String, dynamic>) errBody = decoded;
    } catch (_) {}

    if (rs.statusCode < 200 || rs.statusCode >= 300) {
      throw AiServiceException(
        (errBody?['detail'] as String?) ?? text.trim(),
        statusCode: rs.statusCode,
      );
    }
    try {
      return jsonDecode(text);
    } catch (_) {
      return <String, dynamic>{};
    }
  }

  Map<String, dynamic> _asMap(dynamic j) =>
      j is Map<String, dynamic> ? j : <String, dynamic>{};

  List<dynamic> _asList(dynamic j) => j is List ? j : const [];

  // ── API surface ─────────────────────────────────────────────────────────

  Future<bool> checkHealth() async {
    try {
      final j = _asMap(await _request('GET', '/health'));
      return j['status'] == 'ok';
    } on AiServiceException {
      return false;
    }
  }

  Future<AiStatus> getStatus() async =>
      AiStatus.fromJson(_asMap(await _request('GET', '/api/ai/status')));

  Future<List<AiProviderInfo>> listProviders() async =>
      _asList(await _request('GET', '/api/ai/providers'))
          .map((e) => AiProviderInfo.fromJson(_asMap(e)))
          .toList();

  Future<ChatResult> chat({
    required String message,
    String sessionId = 'desktop',
    String? providerId,
    String? model,
  }) async {
    final j = _asMap(await _request('POST', '/api/ai/chat', body: {
      'message': message,
      'session_id': sessionId,
      'provider_id': ?providerId,
      'model': ?model,
      'stream': false,
    }));
    return ChatResult.fromJson(j);
  }

  /// Streams assistant deltas via SSE. Returns the full reply once done.
  Future<String> chatStream({
    required String message,
    required void Function(String delta) onDelta,
    String sessionId = 'desktop',
    String? providerId,
    String? model,
  }) async {
    final uri = Uri.parse('$baseUrl/api/ai/chat');
    final rq = await _http
        .postUrl(uri)
        .then((r) {
          r.headers.contentType = ContentType.json;
          r.write(jsonEncode({
            'message': message,
            'session_id': sessionId,
            'provider_id': ?providerId,
            'model': ?model,
            'stream': true,
          }));
          return r;
        })
        .timeout(const Duration(seconds: 15));
    final rs = await rq.close().timeout(_timeout);
    if (rs.statusCode != 200) {
      final text = await rs.transform(utf8.decoder).join();
      String detail = text.trim();
      try {
        detail =
            ((jsonDecode(text) as Map)['detail'] as String?) ?? detail;
      } catch (_) {}
      throw AiServiceException(detail, statusCode: rs.statusCode);
    }

    final buf = StringBuffer();
    await for (final raw in rs
        .transform(utf8.decoder)
        .transform(const LineSplitter())) {
      var line = raw.trim();
      if (!line.startsWith('data:')) continue;
      line = line.substring(5).trim();
      if (line == '[DONE]') break;
      try {
        final obj = jsonDecode(line);
        if (obj is! Map) continue;
        final delta = obj['delta'];
        if (delta is String && delta.isNotEmpty) {
          buf.write(delta);
          onDelta(delta);
        }
      } catch (_) {}
    }
    return buf.toString();
  }

  // ── config & consent ──────────────────────────────────────────────────

  Future<Map<String, dynamic>> getConfig() async =>
      _asMap(await _request('GET', '/api/ai/config'));

  Future<Map<String, dynamic>> patchConfig(
          Map<String, dynamic> updates) async =>
      _asMap(await _request('PATCH', '/api/ai/config',
          body: {'updates': updates}));

  Future<void> grantConsent(String providerId) async {
    await _request(
        'POST', '/api/ai/consent/${Uri.encodeComponent(providerId)}',
        body: {'note': 'granted from desktop UI'});
  }

  Future<void> revokeConsent(String providerId) async {
    await _request(
        'DELETE', '/api/ai/consent/${Uri.encodeComponent(providerId)}');
  }

  // ── local models ──────────────────────────────────────────────────────

  Future<List<CatalogModel>> catalog() async =>
      _asList(await _request('GET', '/api/ai/local/catalog'))
          .map((e) => CatalogModel.fromJson(_asMap(e)))
          .toList();

  Future<List<DownloadJob>> downloads() async =>
      _asList(await _request('GET', '/api/ai/local/downloads'))
          .map((e) => DownloadJob.fromJson(_asMap(e)))
          .toList();

  Future<void> startDownload(String modelId) async {
    await _request('POST', '/api/ai/local/download',
        body: {'model_id': modelId});
  }

  Future<void> cancelDownload(String modelId) async {
    await _request(
        'POST', '/api/ai/local/cancel/${Uri.encodeComponent(modelId)}');
  }

  Future<void> deleteModel(String filename) async {
    await _request(
        'DELETE', '/api/ai/local/models/${Uri.encodeComponent(filename)}');
  }
}
