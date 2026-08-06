import 'package:flutter/material.dart';
import 'dart:math';

class WindowData {
  final String id;
  final String title;
  final IconData icon;
  final Widget child;
  Offset position;
  Size size;
  bool isMinimized;
  bool isMaximized;
  int zIndex;

  WindowData({
    required this.id,
    required this.title,
    required this.icon,
    required this.child,
    this.position = const Offset(100, 100),
    this.size = const Size(800, 600),
    this.isMinimized = false,
    this.isMaximized = false,
    this.zIndex = 0,
  });
}

class AppState extends ChangeNotifier {
  final List<WindowData> _windows = [];
  int _topZIndex = 0;
  String? _activeWindowId;

  List<WindowData> get windows => _windows;
  String? get activeWindowId => _activeWindowId;

  void openWindow({
    required String id,
    required String title,
    required IconData icon,
    required Widget child,
    Offset? position,
    Size? size,
  }) {
    final existing = _windows.where((w) => w.id == id).firstOrNull;
    if (existing != null) {
      _activateWindow(id);
      if (existing.isMinimized) {
        existing.isMinimized = false;
      }
      notifyListeners();
      return;
    }

    final random = Random();
    final pos = position ?? Offset(
      100 + random.nextDouble() * 200,
      50 + random.nextDouble() * 100,
    );
    final sz = size ?? const Size(800, 600);

    _topZIndex++;
    _windows.add(WindowData(
      id: id,
      title: title,
      icon: icon,
      child: child,
      position: pos,
      size: sz,
      zIndex: _topZIndex,
    ));
    _activeWindowId = id;
    notifyListeners();
  }

  void closeWindow(String id) {
    _windows.removeWhere((w) => w.id == id);
    if (_activeWindowId == id) {
      _activeWindowId = _windows.isNotEmpty ? _windows.last.id : null;
    }
    notifyListeners();
  }

  void minimizeWindow(String id) {
    final w = _windows.where((w) => w.id == id).firstOrNull;
    if (w != null) {
      w.isMinimized = true;
      if (_activeWindowId == id) {
        final visible = _windows.where((w) => !w.isMinimized).toList();
        _activeWindowId = visible.isNotEmpty ? visible.last.id : null;
      }
      notifyListeners();
    }
  }

  void maximizeWindow(String id) {
    final w = _windows.where((w) => w.id == id).firstOrNull;
    if (w != null) {
      w.isMaximized = !w.isMaximized;
      notifyListeners();
    }
  }

  void _activateWindow(String id) {
    _topZIndex++;
    final w = _windows.where((w) => w.id == id).firstOrNull;
    if (w != null) {
      w.zIndex = _topZIndex;
      _activeWindowId = id;
    }
    notifyListeners();
  }

  void moveWindow(String id, Offset delta) {
    final w = _windows.where((w) => w.id == id).firstOrNull;
    if (w != null && !w.isMaximized) {
      w.position += delta;
      notifyListeners();
    }
  }

  void resizeWindow(String id, Size newSize) {
    final w = _windows.where((w) => w.id == id).firstOrNull;
    if (w != null && !w.isMaximized) {
      w.size = newSize;
      notifyListeners();
    }
  }
}
