import 'dart:async';
import 'dart:convert';
import 'dart:io';

// ---------------------------------------------------------------------------
// Custom exception
// ---------------------------------------------------------------------------

class QuantumServiceException implements Exception {
  QuantumServiceException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() {
    final code = statusCode != null ? ' [HTTP $statusCode]' : '';
    return 'QuantumServiceException$code: $message';
  }
}

// ---------------------------------------------------------------------------
// Data models
// ---------------------------------------------------------------------------

class CircuitOp {
  CircuitOp({
    required this.gate,
    this.qubit,
    this.control,
    this.target,
    this.angle,
  });

  factory CircuitOp.fromJson(Map<String, dynamic> json) => CircuitOp(
        gate: json['gate'] as String,
        qubit: json['qubit'] as int?,
        control: json['control'] as int?,
        target: json['target'] as int?,
        angle: (json['angle'] as num?)?.toDouble(),
      );

  final String gate;
  final int? qubit;
  final int? control;
  final int? target;
  final double? angle;

  Map<String, dynamic> toJson() => {
        'gate': gate,
        if (qubit != null) 'qubit': qubit,
        if (control != null) 'control': control,
        if (target != null) 'target': target,
        if (angle != null) 'angle': angle,
      };
}

class QuantumSimResponse {
  QuantumSimResponse({
    required this.counts,
    required this.backend,
    required this.shots,
    this.statevector,
    this.fidelity,
  });

  factory QuantumSimResponse.fromJson(Map<String, dynamic> json) {
    final countsRaw = json['counts'] as Map<String, dynamic>;
    final counts =
        countsRaw.map((k, v) => MapEntry(k, v as int));

    final sv = (json['statevector'] as List<dynamic>?)
        ?.map((e) => (e as num).toDouble())
        .toList();

    return QuantumSimResponse(
      counts: counts,
      backend: json['backend'] as String,
      shots: json['shots'] as int,
      statevector: sv,
      fidelity: (json['fidelity'] as num?)?.toDouble(),
    );
  }

  final Map<String, int> counts;
  final String backend;
  final int shots;
  final List<double>? statevector;
  final double? fidelity;

  Map<String, dynamic> toJson() => {
        'counts': counts,
        'backend': backend,
        'shots': shots,
        if (statevector != null) 'statevector': statevector,
        if (fidelity != null) 'fidelity': fidelity,
      };
}

class TranspileResponse {
  TranspileResponse({
    required this.nativeOps,
    required this.depth,
    required this.twoQubitCount,
    required this.fidelityEstimate,
  });

  factory TranspileResponse.fromJson(Map<String, dynamic> json) {
    final ops = (json['native_ops'] as List<dynamic>)
        .map((e) => CircuitOp.fromJson(e as Map<String, dynamic>))
        .toList();

    return TranspileResponse(
      nativeOps: ops,
      depth: json['depth'] as int,
      twoQubitCount: json['two_qubit_count'] as int,
      fidelityEstimate: (json['fidelity_estimate'] as num).toDouble(),
    );
  }

  final List<CircuitOp> nativeOps;
  final int depth;
  final int twoQubitCount;
  final double fidelityEstimate;

  Map<String, dynamic> toJson() => {
        'native_ops': nativeOps.map((e) => e.toJson()).toList(),
        'depth': depth,
        'two_qubit_count': twoQubitCount,
        'fidelity_estimate': fidelityEstimate,
      };
}

class AlgorithmResponse {
  AlgorithmResponse({
    required this.name,
    required this.result,
  });

  factory AlgorithmResponse.fromJson(Map<String, dynamic> json) =>
      AlgorithmResponse(
        name: json['name'] as String,
        result: json['result'] as Map<String, dynamic>,
      );

  final String name;
  final Map<String, dynamic> result;

  Map<String, dynamic> toJson() => {
        'name': name,
        'result': result,
      };
}

class BackendStatus {
  BackendStatus({
    required this.defaultBackend,
    required this.availableBackends,
  });

  factory BackendStatus.fromJson(Map<String, dynamic> json) =>
      BackendStatus(
        defaultBackend: json['default_backend'] as String,
        availableBackends: (json['available_backends'] as List<dynamic>)
            .map((e) => e as String)
            .toList(),
      );

  final String defaultBackend;
  final List<String> availableBackends;

  Map<String, dynamic> toJson() => {
        'default_backend': defaultBackend,
        'available_backends': availableBackends,
      };
}

class NoiseModel {
  NoiseModel({
    required this.depolarizingRate,
    required this.readoutError,
    required this.t1Us,
    required this.t2Us,
  });

  factory NoiseModel.fromJson(Map<String, dynamic> json) => NoiseModel(
        depolarizingRate: (json['depolarizing_rate'] as num).toDouble(),
        readoutError: (json['readout_error'] as num).toDouble(),
        t1Us: (json['t1_us'] as num).toDouble(),
        t2Us: (json['t2_us'] as num).toDouble(),
      );

  final double depolarizingRate;
  final double readoutError;
  final double t1Us;
  final double t2Us;

  Map<String, dynamic> toJson() => {
        'depolarizing_rate': depolarizingRate,
        'readout_error': readoutError,
        't1_us': t1Us,
        't2_us': t2Us,
      };
}

class PulseFrame {
  PulseFrame({
    required this.name,
    required this.frequency,
    required this.amplitude,
    required this.duration,
  });

  factory PulseFrame.fromJson(Map<String, dynamic> json) => PulseFrame(
        name: json['name'] as String,
        frequency: (json['frequency'] as num).toDouble(),
        amplitude: (json['amplitude'] as num).toDouble(),
        duration: (json['duration'] as num).toDouble(),
      );

  final String name;
  final double frequency;
  final double amplitude;
  final double duration;

  Map<String, dynamic> toJson() => {
        'name': name,
        'frequency': frequency,
        'amplitude': amplitude,
        'duration': duration,
      };
}

class PulseValidation {
  PulseValidation({
    required this.valid,
    required this.totalDuration,
    required this.maxAmplitude,
    required this.warnings,
  });

  factory PulseValidation.fromJson(Map<String, dynamic> json) =>
      PulseValidation(
        valid: json['valid'] as bool,
        totalDuration: (json['total_duration'] as num).toDouble(),
        maxAmplitude: (json['max_amplitude'] as num).toDouble(),
        warnings: (json['warnings'] as List<dynamic>)
            .map((e) => e as String)
            .toList(),
      );

  final bool valid;
  final double totalDuration;
  final double maxAmplitude;
  final List<String> warnings;

  Map<String, dynamic> toJson() => {
        'valid': valid,
        'total_duration': totalDuration,
        'max_amplitude': maxAmplitude,
        'warnings': warnings,
      };
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

class QuantumService {
  QuantumService._();

  static final QuantumService instance = QuantumService._();

  static const String _baseUrl = 'http://localhost:8420';
  static const Duration _defaultTimeout = Duration(seconds: 10);

  final HttpClient _client = HttpClient()
    ..connectionTimeout = _defaultTimeout;

  // -- helpers --------------------------------------------------------------

  Future<HttpClientRequest> _getRequest(
    String path, {
    Map<String, String>? queryParams,
  }) async {
    final uri = Uri.parse('$_baseUrl$path').replace(
      queryParameters: queryParams,
    );
    return await _client.getUrl(uri).timeout(_defaultTimeout);
  }

  Future<HttpClientRequest> _postRequest(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final uri = Uri.parse('$_baseUrl$path');
    final request = await _client.postUrl(uri).timeout(_defaultTimeout);
    if (body != null) {
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(body));
    }
    return request;
  }

  Future<dynamic> _decodeResponse(HttpClientResponse response) async {
    final body = await response.transform(utf8.decoder).join();

    if (response.statusCode < 200 || response.statusCode >= 300) {
      String detail;
      try {
        final json = jsonDecode(body) as Map<String, dynamic>;
        detail = json['detail'] as String? ?? json['message'] as String? ?? body;
      } catch (_) {
        detail = body;
      }
      throw QuantumServiceException(detail, statusCode: response.statusCode);
    }

    if (body.isEmpty || body.trim().isEmpty) {
      return null;
    }

    return jsonDecode(body);
  }

  // -- public API -----------------------------------------------------------

  /// Check if the quantum backend is running.
  Future<bool> checkHealth() async {
    try {
      final request = await _getRequest('/health');
      final response = await request.close().timeout(_defaultTimeout);
      final json = await _decodeResponse(response) as Map<String, dynamic>;
      return json['status'] == 'ok' || json['status'] == 'healthy';
    } on QuantumServiceException {
      return false;
    } on SocketException {
      return false;
    } on TimeoutException {
      return false;
    }
  }

  /// Run a quantum circuit simulation.
  Future<QuantumSimResponse> simulateCircuit({
    required List<CircuitOp> circuitOps,
    int shots = 1024,
    String backend = 'numpy',
  }) async {
    final ops = circuitOps.map((e) => {
      'gate': e.gate,
      if (e.qubit != null) 'qubits': [e.qubit],
      if (e.control != null) 'control': [e.control],
      if (e.target != null) 'qubits': [e.target],
      if (e.angle != null) 'angle': e.angle,
    }).toList();

    final request = await _postRequest('/api/simulate', body: {
      'operations': ops,
      'shots': shots,
      'backend': backend,
    });
    final response = await request.close().timeout(_defaultTimeout);
    final json = await _decodeResponse(response) as Map<String, dynamic>;
    // Server returns {status, result: {counts, statevector}, backend, shots}
    final result = json['result'] as Map<String, dynamic>? ?? {};
    return QuantumSimResponse(
      counts: (result['counts'] as Map<String, dynamic>?)?.map((k, v) => MapEntry(k, v as int)) ?? {},
      backend: json['backend'] as String? ?? backend,
      shots: json['shots'] as int? ?? shots,
      statevector: (result['statevector'] as List<dynamic>?)?.map((e) => (e as num).toDouble()).toList(),
      fidelity: result['fidelity'] as double?,
    );
  }

  /// Transpile a circuit for a target backend.
  Future<TranspileResponse> transpileCircuit({
    required List<CircuitOp> circuitOps,
    int optimizationLevel = 2,
  }) async {
    final ops = circuitOps.map((e) => {
      'gate': e.gate,
      if (e.qubit != null) 'qubits': [e.qubit],
      if (e.control != null) 'control': [e.control],
      if (e.target != null) 'qubits': [e.target],
      if (e.angle != null) 'angle': e.angle,
    }).toList();

    final request = await _postRequest('/api/transpile', body: {
      'operations': ops,
      'optimization_level': optimizationLevel,
    });
    final response = await request.close().timeout(_defaultTimeout);
    final json = await _decodeResponse(response) as Map<String, dynamic>;
    // Server returns {status, circuit: [...], optimization_level}
    final circuit = json['circuit'] as List<dynamic>? ?? [];
    return TranspileResponse(
      nativeOps: circuit
          .map((e) => CircuitOp(
                gate: e['gate'] as String? ?? 'h',
                qubit: (e['qubits'] as List<dynamic>?)?.first as int?,
                control: (e['control'] as List<dynamic>?)?.first as int?,
                angle: (e['angle'] as num?)?.toDouble(),
              ))
          .toList(),
      depth: circuit.length,
      twoQubitCount: circuit.where((e) =>
          (e['control'] as List<dynamic>?)?.isNotEmpty == true).length,
      fidelityEstimate: 0.95,
    );
  }

  /// Run a named quantum algorithm.
  Future<AlgorithmResponse> runAlgorithm(
    String name,
    Map<String, dynamic> params,
  ) async {
    final numQubits = params['num_qubits'] as int? ?? 4;
    final request = await _postRequest('/api/algorithms/$name/run', body: {
      'num_qubits': numQubits,
      'parameters': params,
      'shots': params['shots'] as int? ?? 1024,
    });
    final response = await request.close().timeout(_defaultTimeout);
    final json = await _decodeResponse(response) as Map<String, dynamic>;
    // Server returns {status, algorithm, result}
    return AlgorithmResponse(
      name: json['algorithm'] as String? ?? name,
      result: json['result'] as Map<String, dynamic>? ?? {},
    );
  }

  /// Get backend status and available backends.
  Future<BackendStatus> getStatus() async {
    final request = await _getRequest('/api/status');
    final response = await request.close().timeout(_defaultTimeout);
    final json = await _decodeResponse(response) as Map<String, dynamic>;
    // Server returns {status, system, version, backends, components, timestamp}
    return BackendStatus(
      defaultBackend: json['backends'] is List && (json['backends'] as List).isNotEmpty
          ? (json['backends'] as List).first as String
          : 'numpy',
      availableBackends: (json['backends'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          ['numpy'],
    );
  }

  /// Get/create a noise model with specified parameters.
  Future<NoiseModel> getNoiseModel({
    double depolarizingRate = 0.01,
    double readoutError = 0.01,
    double t1Us = 50.0,
    double t2Us = 70.0,
  }) async {
    final request = await _postRequest('/api/noise-model', body: {
      'depolarizing_prob': depolarizingRate,
      'amplitude_damping_prob': 0.01,
      'phase_damping_prob': 0.01,
      'readout_error_prob': readoutError,
    });
    final response = await request.close().timeout(_defaultTimeout);
    final json = await _decodeResponse(response) as Map<String, dynamic>;
    // Server returns {status, noise_model: {depolarizing_prob, ...}}
    final nm = json['noise_model'] as Map<String, dynamic>? ?? {};
    return NoiseModel(
      depolarizingRate: (nm['depolarizing_prob'] as num?)?.toDouble() ?? depolarizingRate,
      readoutError: (nm['readout_error_prob'] as num?)?.toDouble() ?? readoutError,
      t1Us: t1Us,
      t2Us: t2Us,
    );
  }

  /// Validate pulse frames for hardware execution.
  Future<PulseValidation> validatePulse(List<PulseFrame> frames) async {
    final request = await _postRequest('/api/pulse/validate', body: {
      'frames': frames.map((e) => e.toJson()).toList(),
    });
    final response = await request.close().timeout(_defaultTimeout);
    final json = await _decodeResponse(response) as Map<String, dynamic>;
    // Server returns {status, valid, warnings, frame_count}
    return PulseValidation(
      valid: json['valid'] as bool? ?? false,
      totalDuration: frames.fold(0.0, (sum, f) => sum + f.duration),
      maxAmplitude: frames.fold(0.0, (sum, f) => f.amplitude > sum ? f.amplitude : sum),
      warnings: (json['warnings'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }

  /// Export circuit to OpenQASM string.
  Future<String> exportQasm(List<CircuitOp> circuitOps, int nQubits) async {
    final ops = circuitOps.map((e) => {
      'gate': e.gate,
      if (e.qubit != null) 'qubits': [e.qubit],
      if (e.control != null) 'control': [e.control],
      if (e.target != null) 'qubits': [e.target],
      if (e.angle != null) 'angle': e.angle,
    }).toList();

    final request = await _postRequest('/api/qasm/export', body: {
      'operations': ops,
    });
    final response = await request.close().timeout(_defaultTimeout);
    final json = await _decodeResponse(response) as Map<String, dynamic>;
    // Server returns {status, qasm, num_qubits, num_gates}
    return json['qasm'] as String? ?? '// QASM export failed';
  }

  /// Release the underlying HTTP client.
  void dispose() {
    _client.close();
  }
}
