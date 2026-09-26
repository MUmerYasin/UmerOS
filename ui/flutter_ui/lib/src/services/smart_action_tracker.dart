/// UmerOS — Smart Action Tracker
/// ==============================
/// Learns which context-menu actions a user picks most often and
/// reorders the menu so the top-3 actions are always the user's
/// favourites.  Persists counts across restarts via [PrefsService].
library;

import 'package:flutter/foundation.dart';

import 'prefs_service.dart';

enum MenuContext { desktop, file, folder, window, taskbar, browser }

class SmartActionTracker extends ChangeNotifier {
  static const _prefix = 'umeros.tracker';
  static const _maxTopN = 3;

  final Map<String, int> _counts = {};

  // ── public API ──────────────────────────────────────────────

  /// Record that [actionId] was invoked in [ctx].
  void track(MenuContext ctx, String actionId) {
    final key = _key(ctx, actionId);
    _counts[key] = (_counts[key] ?? 0) + 1;
    _persist(key);
    notifyListeners();
  }

  /// Return the most-used action-ids for [ctx], capped to [topN].
  List<String> topActions(MenuContext ctx, {int topN = _maxTopN}) {
    final entries = _counts.entries
        .where((e) => e.key.startsWith('$_prefix.${ctx.name}.'))
        .toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return entries.take(topN).map((e) => e.key.split('.').last).toList();
  }

  /// Raw count for a specific action in a context (0 if never used).
  int count(MenuContext ctx, String actionId) =>
      _counts[_key(ctx, actionId)] ?? 0;

  // ── persistence ─────────────────────────────────────────────

  void restore() {
    final prefs = PrefsService.instance;
    for (final key in _allKeys()) {
      _counts[key] = prefs.getInt(key) ?? 0;
    }
  }

  void _persist(String key) {
    PrefsService.instance.setInt(key, _counts[key] ?? 0);
  }

  List<String> _allKeys() {
    final prefs = PrefsService.instance;
    return prefs
        .getKeys()
        .where((key) => key.startsWith('$_prefix.'))
        .toList();
  }

  String _key(MenuContext ctx, String actionId) =>
      '$_prefix.${ctx.name}.$actionId';
}
