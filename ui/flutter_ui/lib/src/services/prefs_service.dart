/// UmerOS Flutter UI — Preferences service
/// ========================================
/// Fail-safe wrapper around `shared_preferences` used by every part of
/// the UI that needs to remember user choices across restarts
/// (theme, wallpaper, system toggles, pinned dock items, ...).
///
/// Design rules honoured here (per `MainTask/Raw Data/Code Review
/// Standards and Process.md`):
///
///  * **Fail-open storage, fail-closed behaviour** — if the platform
///    channel is unavailable (tests, headless runs, corrupted store)
///    every getter returns a safe default and every setter silently
///    no-ops instead of crashing the desktop shell.
///  * Single instance so all providers share one backing store.
library;

import 'package:shared_preferences/shared_preferences.dart';

class PrefsService {
  PrefsService._();

  static final PrefsService instance = PrefsService._();

  SharedPreferences? _prefs;

  /// Initialise the underlying platform store. Safe to call once from
  /// `main()` before any provider reads values. Never throws.
  Future<void> init() async {
    try {
      _prefs = await SharedPreferences.getInstance();
    } catch (_) {
      // Platform channel unavailable (pure Dart tests / restricted host).
      // Keep running with in-memory defaults.
      _prefs = null;
    }
  }

  /// Whether a real persistent backend is attached. Useful for tests
  /// and for surfacing "settings will not be saved" states in debug.
  bool get isAvailable => _prefs != null;

  String? getString(String key) => _read<String>(key, (p) => p.getString(key));

  bool? getBool(String key) => _read<bool>(key, (p) => p.getBool(key));

  double? getDouble(String key) => _read<double>(key, (p) => p.getDouble(key));

  int? getInt(String key) => _read<int>(key, (p) => p.getInt(key));

  List<String>? getStringList(String key) =>
      _read<List<String>>(key, (p) => p.getStringList(key));

  Future<void> setString(String key, String value) =>
      _write(() => _prefs!.setString(key, value));

  Future<void> setBool(String key, bool value) =>
      _write(() => _prefs!.setBool(key, value));

  Future<void> setDouble(String key, double value) =>
      _write(() => _prefs!.setDouble(key, value));

  Future<void> setInt(String key, int value) =>
      _write(() => _prefs!.setInt(key, value));

  Future<void> setStringList(String key, List<String> value) =>
      _write(() => _prefs!.setStringList(key, value));

  Future<void> remove(String key) => _write(() => _prefs!.remove(key));

  // -- internals ------------------------------------------------------------

  /// Reads [key] with the typed getter and returns `null` on any
  /// failure (missing store, wrong runtime type, platform error).
  T? _read<T>(String key, Object? Function(SharedPreferences p) fetch) {
    final prefs = _prefs;
    if (prefs == null) return null;
    try {
      final value = fetch(prefs);
      if (value == null) return null;
      if (value is! T) return null; // type mismatch → treat as absent
      return value as T;
    } catch (_) {
      return null;
    }
  }

  Future<void> _write(Future<Object?> Function() write) async {
    final prefs = _prefs;
    if (prefs == null) return;
    try {
      await write();
    } catch (_) {
      // Persistence failure must never break the UI thread.
    }
  }
}
