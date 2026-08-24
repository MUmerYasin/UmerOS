/// UmerOS Flutter UI — Service result contract
/// ============================================
/// The shared pattern every feature service (quantum, drivers, kernel
/// telemetry, ...) returns so apps can honour the project's honesty
/// mandate: **never present simulated data as real.**
///
/// Usage:
///
/// ```dart
/// final r = await QuantumService.instance.simulateCircuit(...);
/// if (r.fromBackend) { /* render live numbers */ }
/// else              { /* render data + DataSourceBadge(simulated: true) */ }
/// ```
library;

/// Where a [ServiceResult]'s payload came from.
enum DataSource {
  /// Fetched from a live UmerOS backend endpoint.
  backend,

  /// Generated locally because the backend was unreachable — must be
  /// visibly labelled in the UI.
  simulated,
}

class ServiceResult<T> {
  final T? data;

  /// Non-null when the call failed outright (network, decode, ...).
  final Object? error;
  final DataSource source;

  const ServiceResult._(this.data, this.source, this.error);

  /// Successful live response from the backend.
  factory ServiceResult.live(T data) =>
      ServiceResult._(data, DataSource.backend, null);

  /// Graceful fallback: locally generated placeholder data.
  factory ServiceResult.simulated(T data) =>
      ServiceResult._(data, DataSource.simulated, null);

  /// The operation failed; `data` is null.
  factory ServiceResult.failure(Object error) =>
      ServiceResult._(null, DataSource.backend, error);

  bool get isFailure => error != null;

  bool get isLive => source == DataSource.backend && !isFailure;

  @override
  String toString() =>
      'ServiceResult(source: $source, ok: ${!isFailure}, error: $error)';
}
