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

  WindowData copyWith({
    String? title,
    IconData? icon,
    Offset? position,
    Size? size,
    bool? isMinimized,
    bool? isMaximized,
    int? zIndex,
  }) {
    return WindowData(
      id: id,
      title: title ?? this.title,
      icon: icon ?? this.icon,
      child: child,
      position: position ?? this.position,
      size: size ?? this.size,
      isMinimized: isMinimized ?? this.isMinimized,
      isMaximized: isMaximized ?? this.isMaximized,
      zIndex: zIndex ?? this.zIndex,
    );
  }
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
      // Bring to front
      _topZIndex++;
      // Restore if minimized, update title/icon, keep existing child, promote z-index — all in one atomic replace
      final index = _windows.indexOf(existing);
      _windows[index] = existing.copyWith(
        title: title,
        icon: icon,
        isMinimized: false,
        zIndex: _topZIndex,
      );
      _activeWindowId = id;
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
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];
    _windows[idx] = old.copyWith(isMinimized: true);
    if (_activeWindowId == id) {
      final visible = _windows.where((w) => !w.isMinimized).toList();
      _activeWindowId = visible.isNotEmpty ? visible.last.id : null;
    }
    notifyListeners();
  }

  void maximizeWindow(String id) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];
    _windows[idx] = old.copyWith(isMaximized: !old.isMaximized);
    notifyListeners();
  }

  void moveWindow(String id, Offset delta) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];
    if (old.isMaximized) return;
    _windows[idx] = old.copyWith(position: old.position + delta);
    notifyListeners();
  }

  void resizeWindow(String id, Size newSize) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];
    if (old.isMaximized) return;
    _windows[idx] = old.copyWith(size: newSize);
    notifyListeners();
  }
}
