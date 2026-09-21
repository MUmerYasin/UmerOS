import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Clipboard manager for UmerOS context menu operations.
/// Tracks copy, cut, paste, and undo actions with a lightweight history.
class ClipboardManager extends ChangeNotifier {
  final List<ClipboardEntry> _history = [];
  final int _maxHistory = 20;

  List<ClipboardEntry> get history => List.unmodifiable(_history);
  bool get hasContent => _history.isNotEmpty;
  bool get canUndo => _history.isNotEmpty;

  /// Copy text to clipboard and track in history.
  Future<void> copy(String text, {String? label}) async {
    await Clipboard.setData(ClipboardData(text: text));
    _history.insert(0, ClipboardEntry(
      text: text,
      label: label ?? 'Copy',
      action: ClipboardAction.copy,
      timestamp: DateTime.now(),
    ));
    _trimHistory();
    notifyListeners();
  }

  /// Cut text to clipboard and track in history.
  Future<void> cut(String text, {String? label}) async {
    await Clipboard.setData(ClipboardData(text: text));
    _history.insert(0, ClipboardEntry(
      text: text,
      label: label ?? 'Cut',
      action: ClipboardAction.cut,
      timestamp: DateTime.now(),
    ));
    _trimHistory();
    notifyListeners();
  }

  /// Paste from clipboard.
  Future<String?> paste() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    return data?.text;
  }

  /// Undo the last clipboard action.
  ClipboardEntry? undo() {
    if (_history.isEmpty) return null;
    final entry = _history.removeAt(0);
    notifyListeners();
    return entry;
  }

  /// Clear all clipboard history.
  void clearHistory() {
    _history.clear();
    notifyListeners();
  }

  void _trimHistory() {
    while (_history.length > _maxHistory) {
      _history.removeLast();
    }
  }
}

enum ClipboardAction { copy, cut, paste, undo }

class ClipboardEntry {
  final String text;
  final String label;
  final ClipboardAction action;
  final DateTime timestamp;

  const ClipboardEntry({
    required this.text,
    required this.label,
    required this.action,
    required this.timestamp,
  });
}
