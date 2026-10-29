/// Frame Telemetry Service — Deterministic Latency Engine.
///
/// Measures each frame render duration and reports dropped frames
/// to the Python kernel scheduler for background task throttling.
library;

import 'dart:async';
import 'package:flutter/scheduler.dart';

class FrameTelemetry {
  static const double frameThresholdMs = 16.67; // 60 FPS
  static const double highFrameThresholdMs = 8.33; // 120 FPS

  final void Function(double frameDurationMs, bool dropped)? onFrameReport;
  final void Function()? onFrameDrop;

  Timer? _reportTimer;
  int _droppedFrames = 0;
  int _totalFrames = 0;
  double _avgFrameTime = 0;
  final List<double> _recentFrameTimes = [];
  static const int _maxRecentFrames = 60;

  FrameTelemetry({this.onFrameReport, this.onFrameDrop});

  void start() {
    SchedulerBinding.instance.addPersistentFrameCallback(_onFrame);
  }

  void stop() {
    // Persistent callbacks can't be easily removed; track state instead
    _reportTimer?.cancel();
  }

  void _onFrame(Duration timestamp) {
    // Frame timing is handled by the scheduler; we track via frame callbacks
    _totalFrames++;
  }

  /// Record a frame duration measurement.
  void recordFrame(double durationMs) {
    _recentFrameTimes.add(durationMs);
    if (_recentFrameTimes.length > _maxRecentFrames) {
      _recentFrameTimes.removeAt(0);
    }
    _avgFrameTime = _recentFrameTimes.reduce((a, b) => a + b) / _recentFrameTimes.length;

    final dropped = durationMs > frameThresholdMs;
    if (dropped) {
      _droppedFrames++;
      onFrameDrop?.call();
    }
    onFrameReport?.call(durationMs, dropped);
  }

  /// Get current telemetry stats.
  Map<String, dynamic> getStats() {
    return {
      'total_frames': _totalFrames,
      'dropped_frames': _droppedFrames,
      'drop_rate': _totalFrames > 0 ? _droppedFrames / _totalFrames : 0.0,
      'avg_frame_time_ms': _avgFrameTime,
      'recent_frames': List<double>.from(_recentFrameTimes),
    };
  }

  void reset() {
    _droppedFrames = 0;
    _totalFrames = 0;
    _recentFrameTimes.clear();
    _avgFrameTime = 0;
  }
}