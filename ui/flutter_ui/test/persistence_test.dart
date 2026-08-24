// UmerOS Flutter UI — Persistence round-trip tests
// =================================================
// Verifies that ThemeProvider and AppState restore what they persist,
// and that storage failures degrade to defaults instead of crashing.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/src/core/app_state.dart';
import 'package:flutter_ui/src/core/theme_provider.dart';
import 'package:flutter_ui/src/services/prefs_service.dart';
import 'package:flex_color_scheme/flex_color_scheme.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues(const {});
    return PrefsService.instance.init();
  });

  group('ThemeProvider persistence', () {
    test('defaults when nothing persisted', () {
      final theme = ThemeProvider()..restore();
      expect(theme.themeMode, ThemeMode.dark);
      expect(theme.flexScheme, FlexScheme.deepPurple);
      expect(theme.wallpaper, WallpaperPreset.quantumGradient);
      expect(theme.enableGlassmorphism, isTrue);
      expect(theme.uiScale, 1.0);
    });

    test('theme mode round-trips', () async {
      final first = ThemeProvider()..restore();
      first.toggleTheme();
      // Allow the fire-and-forget persist future to complete.
      await Future<void>.delayed(Duration.zero);

      final second = ThemeProvider()..restore();
      expect(second.themeMode, ThemeMode.light);
    });

    test('colour scheme round-trips', () async {
      final first = ThemeProvider()..restore();
      first.setFlexScheme(FlexScheme.material);
      await Future<void>.delayed(Duration.zero);

      final second = ThemeProvider()..restore();
      expect(second.flexScheme, FlexScheme.material);
    });

    test('wallpaper and custom image round-trip', () async {
      final first = ThemeProvider()..restore();
      first.setWallpaper(WallpaperPreset.cyberpunkNeon);
      first.setCustomImagePath('C:/walls/umer.png');
      await Future<void>.delayed(Duration.zero);

      final second = ThemeProvider()..restore();
      expect(second.wallpaper, WallpaperPreset.customImage);
      expect(second.customImagePath, 'C:/walls/umer.png');
    });

    test('glassmorphism and ui-scale round-trip', () async {
      final first = ThemeProvider()..restore();
      first.toggleGlassmorphism(false);
      first.setUiScale(1.25);
      await Future<void>.delayed(Duration.zero);

      final second = ThemeProvider()..restore();
      expect(second.enableGlassmorphism, isFalse);
      expect(second.uiScale, 1.25);
    });

    test('ui-scale is clamped to a sane range', () {
      final theme = ThemeProvider()..restore();
      theme.setUiScale(99);
      expect(theme.uiScale, lessThanOrEqualTo(1.5));
      theme.setUiScale(0.01);
      expect(theme.uiScale, greaterThanOrEqualTo(0.75));
    });
  });

  group('AppState persistence', () {
    test('volume / brightness / toggles round-trip', () async {
      final first = AppState()..restore();
      first.setVolume(0.42);
      first.setBrightness(0.33);
      first.toggleWifi(); // on -> off
      first.togglePerformanceMode(); // on -> off
      await Future<void>.delayed(Duration.zero);

      final second = AppState()..restore();
      expect(second.volume, closeTo(0.42, 0.0001));
      expect(second.brightness, closeTo(0.33, 0.0001));
      expect(second.wifiEnabled, isFalse);
      expect(second.performanceMode, isFalse);
    });

    test('pinned dock items round-trip and unknown pins survive', () async {
      final first = AppState()..restore();
      first.pinDockItem('calculator'); // valid registry id
      first.pinDockItem('ghost-app'); // stale id must be kept by store
      await Future<void>.delayed(Duration.zero);

      final second = AppState()..restore();
      expect(second.pinnedDockIds.contains('calculator'), isTrue);
      expect(
        second.pinnedDockIds.contains('ghost-app'),
        isTrue,
        reason:
            'persisted-but-unknown ids are preserved; the dock renders '
            'them as neutral placeholders',
      );
    });

    test('unpin removes and persists', () async {
      final first = AppState()..restore();
      first.unpinDockItem('browser');
      await Future<void>.delayed(Duration.zero);

      final second = AppState()..restore();
      expect(second.pinnedDockIds.contains('browser'), isFalse);
    });
  });
}
