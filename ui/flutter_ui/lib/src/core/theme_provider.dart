import 'package:flutter/material.dart';
import 'package:flex_color_scheme/flex_color_scheme.dart';

enum WallpaperPreset {
  quantumGradient,
  deepSpace,
  auroraBoreal,
  cyberpunkNeon,
  minimalMesh,
  midnightSlate,
}

class ThemeProvider extends ChangeNotifier {
  ThemeMode _themeMode = ThemeMode.dark;
  FlexScheme _flexScheme = FlexScheme.deepPurple;
  WallpaperPreset _wallpaper = WallpaperPreset.quantumGradient;
  bool _enableGlassmorphism = true;
  double _uiScale = 1.0;

  ThemeMode get themeMode => _themeMode;
  FlexScheme get flexScheme => _flexScheme;
  WallpaperPreset get wallpaper => _wallpaper;
  bool get enableGlassmorphism => _enableGlassmorphism;
  double get uiScale => _uiScale;

  void toggleTheme() {
    _themeMode = _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
  }

  void setThemeMode(ThemeMode mode) {
    _themeMode = mode;
    notifyListeners();
  }

  void setFlexScheme(FlexScheme scheme) {
    _flexScheme = scheme;
    notifyListeners();
  }

  void setWallpaper(WallpaperPreset preset) {
    _wallpaper = preset;
    notifyListeners();
  }

  void toggleGlassmorphism(bool value) {
    _enableGlassmorphism = value;
    notifyListeners();
  }

  void setUiScale(double scale) {
    _uiScale = scale;
    notifyListeners();
  }
}
