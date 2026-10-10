import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/main.dart';
import 'package:flutter_ui/src/core/app_state.dart';
import 'package:flutter_ui/src/core/theme_provider.dart';
import 'package:flutter_ui/src/services/prefs_service.dart';
import 'package:flutter_ui/services/clipboard_manager.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await PrefsService.instance.init();
  });

  group('Virtual Workspaces (Multi-Desktop Spaces)', () {
    test('Default workspaces state has 3 spaces and workspace 1 active', () {
      final appState = AppState();
      expect(appState.currentWorkspace, 1);
      expect(appState.totalWorkspaces, 3);
    });

    test('openWindow assigns current workspace and visibleWindows filters properly', () {
      final appState = AppState();

      // Open window on workspace 1
      appState.openWindow(
        id: 'win1',
        title: 'App 1',
        icon: Icons.apps,
        child: const SizedBox(),
      );

      expect(appState.windows.length, 1);
      expect(appState.visibleWindows.length, 1);
      expect(appState.visibleWindows.first.id, 'win1');

      // Switch to workspace 2
      appState.switchWorkspace(2);
      expect(appState.currentWorkspace, 2);
      expect(appState.visibleWindows.isEmpty, true);

      // Open window on workspace 2
      appState.openWindow(
        id: 'win2',
        title: 'App 2',
        icon: Icons.code,
        child: const SizedBox(),
      );

      expect(appState.windows.length, 2);
      expect(appState.visibleWindows.length, 1);
      expect(appState.visibleWindows.first.id, 'win2');

      // Switch back to workspace 1
      appState.switchWorkspace(1);
      expect(appState.visibleWindows.length, 1);
      expect(appState.visibleWindows.first.id, 'win1');
    });

    test('moveWindowToWorkspace moves window to target space', () {
      final appState = AppState();
      appState.openWindow(
        id: 'win1',
        title: 'App 1',
        icon: Icons.apps,
        child: const SizedBox(),
      );

      expect(appState.visibleWindows.length, 1);
      appState.moveWindowToWorkspace('win1', 3);

      // Now workspace 1 should have 0 visible windows
      expect(appState.visibleWindows.isEmpty, true);

      // Workspace 3 should show win1
      appState.switchWorkspace(3);
      expect(appState.visibleWindows.length, 1);
      expect(appState.visibleWindows.first.id, 'win1');
    });

    test('addWorkspace and removeWorkspace manage total count cleanly', () {
      final appState = AppState();
      expect(appState.totalWorkspaces, 3);

      appState.addWorkspace();
      expect(appState.totalWorkspaces, 4);
      expect(appState.currentWorkspace, 4);

      // Remove workspace 4
      appState.removeWorkspace(4);
      expect(appState.totalWorkspaces, 3);
      expect(appState.currentWorkspace, 3);
    });
  });

  group('Universal Clipboard History & Quick Scratchpad', () {
    test('ClipboardManager tracks history and can clear', () async {
      final mgr = ClipboardManager();
      expect(mgr.history.isEmpty, true);

      await mgr.copy('Hello UmerOS', label: 'Copy');
      expect(mgr.history.length, 1);
      expect(mgr.history.first.text, 'Hello UmerOS');

      await mgr.copy('Modern OS features', label: 'Copy 2');
      expect(mgr.history.length, 2);
      expect(mgr.history.first.text, 'Modern OS features');

      mgr.clearHistory();
      expect(mgr.history.isEmpty, true);
    });

    test('AppState toggles clipboard and scratchpad with mutual exclusion', () {
      final appState = AppState();
      expect(appState.isClipboardOpen, false);
      expect(appState.isScratchpadOpen, false);

      appState.toggleClipboard(show: true);
      expect(appState.isClipboardOpen, true);
      expect(appState.isScratchpadOpen, false);

      appState.toggleScratchpad(show: true);
      expect(appState.isScratchpadOpen, true);
      expect(appState.isClipboardOpen, false);

      appState.toggleSearch(show: true);
      expect(appState.isSearchOpen, true);
      expect(appState.isScratchpadOpen, false);
    });

    test('Scratchpad text updates and persists correctly', () {
      final appState = AppState();
      appState.updateScratchpad('Note 1: Finish UmerOS modern OS integration.');
      expect(appState.scratchpadText, 'Note 1: Finish UmerOS modern OS integration.');

      // Verify PrefsService holds the text
      expect(
        PrefsService.instance.getString('umeros.state.scratchpad'),
        'Note 1: Finish UmerOS modern OS integration.',
      );
    });
  });

  group('UI Integration: Workspace pills & Modal Triggers', () {
    testWidgets('Menu bar displays workspace pills, clipboard button, and scratchpad button',
        (WidgetTester tester) async {
      final themeProvider = ThemeProvider()..restore();
      final appState = AppState()..restore();

      await tester.pumpWidget(UmerOSApp(
        themeProvider: themeProvider,
        appState: appState,
      ));
      await tester.pump(const Duration(milliseconds: 300));

      // Verify workspace pills '1', '2', '3' are present
      expect(find.text('1'), findsWidgets);
      expect(find.text('2'), findsWidgets);
      expect(find.text('3'), findsWidgets);

      // Verify clipboard history button icon is present
      expect(find.byIcon(Icons.content_paste_rounded), findsOneWidget);

      // Verify scratchpad button icon is present
      expect(find.byIcon(Icons.sticky_note_2_outlined), findsOneWidget);

      // Open Clipboard History
      await tester.tap(find.byIcon(Icons.content_paste_rounded));
      await tester.pump(const Duration(milliseconds: 300));
      expect(appState.isClipboardOpen, true);
      expect(find.text('Clipboard History'), findsOneWidget);

      // Close it and open Scratchpad
      await tester.tap(find.byIcon(Icons.sticky_note_2_outlined));
      await tester.pump(const Duration(milliseconds: 300));
      expect(appState.isScratchpadOpen, true);
      expect(find.text('Quick Scratchpad'), findsOneWidget);

      // Clean up clock timer
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(milliseconds: 100));
    });

    testWidgets('Spotlight search evaluates arithmetic expressions in real time',
        (WidgetTester tester) async {
      final themeProvider = ThemeProvider()..restore();
      final appState = AppState()..restore();

      await tester.pumpWidget(UmerOSApp(
        themeProvider: themeProvider,
        appState: appState,
      ));
      await tester.pump(const Duration(milliseconds: 300));

      // Open Spotlight search
      appState.toggleSearch(show: true);
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byType(TextField), findsOneWidget);

      // Enter math calculation "25 * 4"
      await tester.enterText(find.byType(TextField), '25 * 4');
      await tester.pump(const Duration(milliseconds: 300));

      // Verify calculation card renders "100"
      expect(find.text('100'), findsOneWidget);
      expect(find.text('= 25 * 4'), findsOneWidget);

      // Clean up clock timer
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(milliseconds: 100));
    });
  });
}
