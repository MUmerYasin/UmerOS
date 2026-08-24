/// UmerOS Flutter UI — Theme provider
/// ===================================
/// Owns appearance state (theme mode, colour scheme, wallpaper,
/// glassmorphism, UI scale) and **persists every change** through
/// [PrefsService] so the desktop looks the same after a restart.
library;

import 'package:flutter/material.dart';
import 'package:flex_color_scheme/flex_color_scheme.dart';

import '../services/prefs_service.dart';

enum WallpaperPreset {
  quantumGradient,
  deepSpace,
  auroraBoreal,
  cyberpunkNeon,
  minimalMesh,
  midnightSlate,
  customImage,
}

class ThemeProvider extends ChangeNotifier {
  static const _kMode = 'umeros.theme.mode';
  static const _kScheme = 'umeros.theme.scheme';
  static const _kWallpaper = 'umeros.theme.wallpaper';
  static const _kCustomImage = 'umeros.theme.imagePath';
  static const _kGlass = 'umeros.theme.glassmorphism';
  static const _kScale = 'umeros.theme.uiScale';

  ThemeMode _themeMode = ThemeMode.dark;
  FlexScheme _flexScheme = FlexScheme.deepPurple;
  WallpaperPreset _wallpaper = WallpaperPreset.quantumGradient;
  String? _customImagePath;
  bool _enableGlassmorphism = true;
  double _uiScale = 1.0;

  ThemeMode get themeMode => _themeMode;
  FlexScheme get flexScheme => _flexScheme;
  WallpaperPreset get wallpaper => _wallpaper;
  String? get customImagePath => _customImagePath;
  bool get enableGlassmorphism => _enableGlassmorphism;
  double get uiScale => _uiScale;

  /// Restore persisted preferences. Call once at startup, right after
  /// [PrefsService.init]. Unknown/corrupt values fall back silently to
  /// defaults (fail-safe restore).
  void restore() {
    final prefs = PrefsService.instance;

    switch (prefs.getString(_kMode)) {
      case 'light':
        _themeMode = ThemeMode.light;
      case 'system':
        _themeMode = ThemeMode.system;
      case 'dark':
        _themeMode = ThemeMode.dark;
    }

    final schemeName = prefs.getString(_kScheme);
    if (schemeName != null) {
      try {
        _flexScheme = FlexScheme.values.byName(schemeName);
      } catch (_) {
        // keep default
      }
    }

    final wallpaperName = prefs.getString(_kWallpaper);
    if (wallpaperName != null) {
      try {
        _wallpaper = WallpaperPreset.values.byName(wallpaperName);
      } catch (_) {
        // keep default
      }
    }

    final image = prefs.getString(_kCustomImage);
    if (image != null && image.isNotEmpty) _customImagePath = image;

    _enableGlassmorphism = prefs.getBool(_kGlass) ?? true;
    _uiScale = prefs.getDouble(_kScale) ?? 1.0;
  }

  void toggleTheme() {
    _themeMode =
        _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    PrefsService.instance.setString(_kMode, _themeMode.name);
    notifyListeners();
  }

  void setThemeMode(ThemeMode mode) {
    _themeMode = mode;
    PrefsService.instance.setString(_kMode, mode.name);
    notifyListeners();
  }

  void setFlexScheme(FlexScheme scheme) {
    _flexScheme = scheme;
    PrefsService.instance.setString(_kScheme, scheme.name);
    notifyListeners();
  }

  void setWallpaper(WallpaperPreset preset) {
    _wallpaper = preset;
    PrefsService.instance.setString(_kWallpaper, preset.name);
    notifyListeners();
  }

  void setCustomImagePath(String path) {
    _customImagePath = path;
    _wallpaper = WallpaperPreset.customImage;
    PrefsService.instance.setString(_kCustomImage, path);
    PrefsService.instance.setString(_kWallpaper, _wallpaper.name);
    notifyListeners();
  }

  void toggleGlassmorphism(bool value) {
    _enableGlassmorphism = value;
    PrefsService.instance.setBool(_kGlass, value);
    notifyListeners();
  }

  void setUiScale(double scale) {
    _uiScale = scale.clamp(0.75, 1.5);
    PrefsService.instance.setDouble(_kScale, _uiScale);
    notifyListeners();
  }
}
