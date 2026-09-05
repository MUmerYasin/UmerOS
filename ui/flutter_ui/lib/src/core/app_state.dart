import 'package:flutter/material.dart';
import 'dart:math';

import '../services/prefs_service.dart';

enum WindowSnapMode {
  normal,
  leftHalf,
  rightHalf,
  topLeft,
  topRight,
  bottomLeft,
  bottomRight,
  maximized,
  centered,
}

class WindowData {
  final String id;
  final String title;
  final IconData icon;
  final Widget child;
  Offset position;
  Size size;
  Offset preSnapPosition;
  Size preSnapSize;
  bool isMinimized;
  bool isMaximized;
  WindowSnapMode snapMode;
  int zIndex;

  WindowData({
    required this.id,
    required this.title,
    required this.icon,
    required this.child,
    this.position = const Offset(100, 100),
    this.size = const Size(880, 620),
    Offset? preSnapPosition,
    Size? preSnapSize,
    this.isMinimized = false,
    this.isMaximized = false,
    this.snapMode = WindowSnapMode.normal,
    this.zIndex = 0,
  })  : preSnapPosition = preSnapPosition ?? position,
        preSnapSize = preSnapSize ?? size;

  WindowData copyWith({
    String? title,
    IconData? icon,
    Offset? position,
    Size? size,
    Offset? preSnapPosition,
    Size? preSnapSize,
    bool? isMinimized,
    bool? isMaximized,
    WindowSnapMode? snapMode,
    int? zIndex,
  }) {
    return WindowData(
      id: id,
      title: title ?? this.title,
      icon: icon ?? this.icon,
      child: child,
      position: position ?? this.position,
      size: size ?? this.size,
      preSnapPosition: preSnapPosition ?? this.preSnapPosition,
      preSnapSize: preSnapSize ?? this.preSnapSize,
      isMinimized: isMinimized ?? this.isMinimized,
      isMaximized: isMaximized ?? this.isMaximized,
      snapMode: snapMode ?? this.snapMode,
      zIndex: zIndex ?? this.zIndex,
    );
  }
}

class SystemNotification {
  final String id;
  final String title;
  final String message;
  final IconData icon;
  final Color color;
  final DateTime timestamp;
  bool isRead;

  SystemNotification({
    required this.id,
    required this.title,
    required this.message,
    required this.icon,
    this.color = Colors.blue,
    DateTime? timestamp,
    this.isRead = false,
  }) : timestamp = timestamp ?? DateTime.now();
}

class AppState extends ChangeNotifier {
  static const _kVolume = 'umeros.state.volume';
  static const _kBrightness = 'umeros.state.brightness';
  static const _kWifi = 'umeros.state.wifi';
  static const _kBluetooth = 'umeros.state.bluetooth';
  static const _kNightShift = 'umeros.state.nightShift';
  static const _kDnd = 'umeros.state.dnd';
  static const _kPerformance = 'umeros.state.performance';
  static const _kDockPins = 'umeros.state.dockPins';

  final List<WindowData> _windows = [];
  int _topZIndex = 0;
  String? _activeWindowId;

  // Pinned Dock items list (defaults; may be replaced by persisted pins)
  final List<String> _pinnedDockIds = List.from(_defaultPinnedIds);

  // Overlays state
  bool _isSearchOpen = false;
  bool _isControlCenterOpen = false;
  bool _isNotificationTrayOpen = false;

  // Snap preview overlay during drag
  Rect? _snapPreviewRect;

  // System States
  double _volume = 0.75;
  double _brightness = 0.85;
  bool _wifiEnabled = true;
  bool _bluetoothEnabled = true;
  bool _nightShift = false;
  bool _dnd = false;
  bool _performanceMode = true;
  String? _volumeToastMessage;

  // Notifications list
  final List<SystemNotification> _notifications = [
    SystemNotification(
      id: '1',
      title: 'Welcome to UmerOS',
      message: 'System running with Material 3 & HCI UI enhancements.',
      icon: Icons.computer,
      color: Colors.deepPurple,
    ),
    SystemNotification(
      id: '2',
      title: 'Quantum Engine Ready',
      message: 'Quantum Simulator driver initialized successfully.',
      icon: Icons.blur_circular,
      color: Colors.indigo,
    ),
  ];

  // Getters
  List<WindowData> get windows => _windows;
  String? get activeWindowId => _activeWindowId;
  List<String> get pinnedDockIds => _pinnedDockIds;
  bool get isSearchOpen => _isSearchOpen;
  bool get isControlCenterOpen => _isControlCenterOpen;
  bool get isNotificationTrayOpen => _isNotificationTrayOpen;
  Rect? get snapPreviewRect => _snapPreviewRect;

  double get volume => _volume;
  double get brightness => _brightness;
  bool get wifiEnabled => _wifiEnabled;
  bool get bluetoothEnabled => _bluetoothEnabled;
  bool get nightShift => _nightShift;
  bool get dnd => _dnd;
  bool get performanceMode => _performanceMode;
  String? get volumeToastMessage => _volumeToastMessage;
  List<SystemNotification> get notifications => _notifications;
  int get unreadNotificationCount => _notifications.where((n) => !n.isRead).length;

  /// Restore persisted system state. Call once at startup after
  /// [PrefsService.init]. Unknown dock pins are dropped via the
  /// registry so a renamed app can never wedge the dock.
  void restore() {
    final prefs = PrefsService.instance;

    _volume = prefs.getDouble(_kVolume)?.clamp(0.0, 1.0) ?? _volume;
    _brightness = prefs.getDouble(_kBrightness)?.clamp(0.0, 1.0) ?? _brightness;
    _wifiEnabled = prefs.getBool(_kWifi) ?? _wifiEnabled;
    _bluetoothEnabled = prefs.getBool(_kBluetooth) ?? _bluetoothEnabled;
    _nightShift = prefs.getBool(_kNightShift) ?? _nightShift;
    _dnd = prefs.getBool(_kDnd) ?? _dnd;
    _performanceMode = prefs.getBool(_kPerformance) ?? _performanceMode;

    final pins = prefs.getStringList(_kDockPins);
    if (pins != null && pins.isNotEmpty) {
      final known = pins.toSet();
      // Keep defaults first (stable order), then any extra persisted pins.
      _pinnedDockIds
        ..clear()
        ..addAll([
          ..._defaultPinnedIds.where(known.contains),
          ...known.where((id) => !_defaultPinnedIds.contains(id)),
        ]);
    }
  }

  static const List<String> _defaultPinnedIds = [
    'browser',
    'terminal',
    'files',
    'monitor',
    'settings',
    'editor',
    'packages',
    'quantum',
    'security',
    'games',
    'docs',
    'backup',
  ];

  void pinDockItem(String id) {
    if (!_pinnedDockIds.contains(id)) {
      _pinnedDockIds.add(id);
      PrefsService.instance.setStringList(_kDockPins, _pinnedDockIds);
      addNotification('Dock', 'App added to Dock', Icons.push_pin);
      notifyListeners();
    }
  }

  void unpinDockItem(String id) {
    _pinnedDockIds.remove(id);
    PrefsService.instance.setStringList(_kDockPins, _pinnedDockIds);
    notifyListeners();
  }

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
      _topZIndex++;
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
    final pos = position ??
        Offset(
          100 + random.nextDouble() * 140,
          50 + random.nextDouble() * 70,
        );
    final sz = size ?? const Size(880, 620);

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

  void focusWindow(String id) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    _topZIndex++;
    _windows[idx] = _windows[idx].copyWith(zIndex: _topZIndex, isMinimized: false);
    _activeWindowId = id;
    notifyListeners();
  }

  void closeWindow(String id) {
    _windows.removeWhere((w) => w.id == id);
    if (_activeWindowId == id) {
      final visible = _windows.where((w) => !w.isMinimized).toList();
      visible.sort((a, b) => a.zIndex.compareTo(b.zIndex));
      _activeWindowId = visible.isNotEmpty ? visible.last.id : null;
    }
    notifyListeners();
  }

  /// Restores a minimized window without recreating it.
  void restoreWindow(String id) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final win = _windows[idx];
    if (!win.isMinimized) return;
    _windows[idx] = win.copyWith(isMinimized: false);
    _activeWindowId = id;
    _topZIndex++;
    _windows[idx] = _windows[idx].copyWith(zIndex: _topZIndex);
    notifyListeners();
  }

  /// Minimizes a window to the dock.
  void minimizeWindow(String id) {
      final idx = _windows.indexWhere((w) => w.id == id);
      if (idx == -1) return;
      final old = _windows[idx];
      _windows[idx] = old.copyWith(isMinimized: true);
      if (_activeWindowId == id) {
        final visible = _windows.where((w) => !w.isMinimized).toList();
        visible.sort((a, b) => a.zIndex.compareTo(b.zIndex));
        _activeWindowId = visible.isNotEmpty ? visible.last.id : null;
      }
      notifyListeners();
    }


  void maximizeWindow(String id) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];
    final willMaximize = !old.isMaximized;
    _windows[idx] = old.copyWith(
      isMaximized: willMaximize,
      snapMode: willMaximize ? WindowSnapMode.maximized : WindowSnapMode.normal,
      preSnapPosition:
          old.snapMode == WindowSnapMode.normal ? old.position : old.preSnapPosition,
      preSnapSize: old.snapMode == WindowSnapMode.normal ? old.size : old.preSnapSize,
    );
    focusWindow(id);
  }

  void moveWindow(String id, Offset delta) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];
    if (old.isMaximized) return;

    Offset newPos = old.position + delta;
    _windows[idx] = old.copyWith(
      position: newPos,
      snapMode: WindowSnapMode.normal,
    );
    notifyListeners();
  }

  void resizeWindow(String id, {Size? newSize, Offset? newPos}) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];
    if (old.isMaximized) return;

    const minW = 400.0;
    const minH = 300.0;
    final finalSize = Size(
      max(minW, newSize?.width ?? old.size.width),
      max(minH, newSize?.height ?? old.size.height),
    );

    _windows[idx] = old.copyWith(
      size: finalSize,
      position: newPos ?? old.position,
      snapMode: WindowSnapMode.normal,
    );
    notifyListeners();
  }

  void snapWindow(String id, WindowSnapMode mode, Size screenSize) {
    final idx = _windows.indexWhere((w) => w.id == id);
    if (idx == -1) return;
    final old = _windows[idx];

    if (mode == WindowSnapMode.normal) {
      _windows[idx] = old.copyWith(
        position: old.preSnapPosition,
        size: old.preSnapSize,
        isMaximized: false,
        snapMode: WindowSnapMode.normal,
      );
      focusWindow(id);
      return;
    }

    final topOffset = 36.0;
    final bottomOffset = 86.0;
    final availH = screenSize.height - topOffset - bottomOffset;
    final availW = screenSize.width;

    Offset pos = old.position;
    Size sz = old.size;

    switch (mode) {
      case WindowSnapMode.leftHalf:
        pos = Offset(0, topOffset);
        sz = Size(availW * 0.5, availH);
        break;
      case WindowSnapMode.rightHalf:
        pos = Offset(availW * 0.5, topOffset);
        sz = Size(availW * 0.5, availH);
        break;
      case WindowSnapMode.topLeft:
        pos = Offset(0, topOffset);
        sz = Size(availW * 0.5, availH * 0.5);
        break;
      case WindowSnapMode.topRight:
        pos = Offset(availW * 0.5, topOffset);
        sz = Size(availW * 0.5, availH * 0.5);
        break;
      case WindowSnapMode.bottomLeft:
        pos = Offset(0, topOffset + availH * 0.5);
        sz = Size(availW * 0.5, availH * 0.5);
        break;
      case WindowSnapMode.bottomRight:
        pos = Offset(availW * 0.5, topOffset + availH * 0.5);
        sz = Size(availW * 0.5, availH * 0.5);
        break;
      case WindowSnapMode.maximized:
        pos = Offset(0, topOffset);
        sz = Size(availW, availH);
        break;
      case WindowSnapMode.centered:
        sz = Size(availW * 0.8, availH * 0.8);
        pos = Offset((availW - sz.width) / 2, topOffset + (availH - sz.height) / 2);
        break;
      case WindowSnapMode.normal:
        break;
    }

    _windows[idx] = old.copyWith(
      position: pos,
      size: sz,
      preSnapPosition: old.snapMode == WindowSnapMode.normal ? old.position : old.preSnapPosition,
      preSnapSize: old.snapMode == WindowSnapMode.normal ? old.size : old.preSnapSize,
      isMaximized: mode == WindowSnapMode.maximized,
      snapMode: mode,
    );
    focusWindow(id);
  }

  void setSnapPreview(Rect? rect) {
    if (_snapPreviewRect != rect) {
      _snapPreviewRect = rect;
      notifyListeners();
    }
  }

  // System Toggles & Setters
  void toggleSearch({bool? show}) {
    _isSearchOpen = show ?? !_isSearchOpen;
    if (_isSearchOpen) {
      _isControlCenterOpen = false;
      _isNotificationTrayOpen = false;
    }
    notifyListeners();
  }

  void toggleControlCenter({bool? show}) {
    _isControlCenterOpen = show ?? !_isControlCenterOpen;
    if (_isControlCenterOpen) {
      _isSearchOpen = false;
      _isNotificationTrayOpen = false;
    }
    notifyListeners();
  }

  void toggleNotificationTray({bool? show}) {
    _isNotificationTrayOpen = show ?? !_isNotificationTrayOpen;
    if (_isNotificationTrayOpen) {
      _isSearchOpen = false;
      _isControlCenterOpen = false;
      for (var n in _notifications) {
        n.isRead = true;
      }
    }
    notifyListeners();
  }

  void setVolume(double val) {
    _volume = val.clamp(0.0, 1.0);
    _volumeToastMessage = 'Volume: ${(_volume * 100).round()}%';
    PrefsService.instance.setDouble(_kVolume, _volume);
    notifyListeners();
  }

  void setBrightness(double val) {
    _brightness = val.clamp(0.0, 1.0);
    PrefsService.instance.setDouble(_kBrightness, _brightness);
    notifyListeners();
  }

  void toggleWifi() {
    _wifiEnabled = !_wifiEnabled;
    PrefsService.instance.setBool(_kWifi, _wifiEnabled);
    addNotification('Network', _wifiEnabled ? 'Wi-Fi turned ON' : 'Wi-Fi turned OFF', Icons.wifi);
    notifyListeners();
  }

  void toggleBluetooth() {
    _bluetoothEnabled = !_bluetoothEnabled;
    PrefsService.instance.setBool(_kBluetooth, _bluetoothEnabled);
    addNotification('Bluetooth', _bluetoothEnabled ? 'Bluetooth turned ON' : 'Bluetooth turned OFF', Icons.bluetooth);
    notifyListeners();
  }

  void toggleNightShift() {
    _nightShift = !_nightShift;
    PrefsService.instance.setBool(_kNightShift, _nightShift);
    notifyListeners();
  }

  void toggleDnd() {
    _dnd = !_dnd;
    PrefsService.instance.setBool(_kDnd, _dnd);
    addNotification('Do Not Disturb', _dnd ? 'DND Mode Activated' : 'DND Mode Deactivated', Icons.do_not_disturb_on);
    notifyListeners();
  }

  void togglePerformanceMode() {
    _performanceMode = !_performanceMode;
    PrefsService.instance.setBool(_kPerformance, _performanceMode);
    addNotification('Performance', _performanceMode ? 'High Performance Mode Active' : 'Balanced Power Mode Active', Icons.speed);
    notifyListeners();
  }

  void addNotification(String title, String message, IconData icon, [Color color = Colors.blue]) {
    _notifications.insert(
      0,
      SystemNotification(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        title: title,
        message: message,
        icon: icon,
        color: color,
      ),
    );
    notifyListeners();
  }

  void removeNotification(String id) {
    _notifications.removeWhere((n) => n.id == id);
    notifyListeners();
  }

  void clearAllNotifications() {
    _notifications.clear();
    notifyListeners();
  }
}
