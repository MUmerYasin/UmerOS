import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/main.dart';
import 'package:flutter_ui/src/core/app_state.dart';
import 'package:flutter_ui/src/core/desktop_shell.dart';
import 'package:flutter_ui/src/core/theme_provider.dart';
import 'package:flutter_ui/src/services/prefs_service.dart';
import 'package:flutter_ui/src/widgets/dock.dart';
import 'package:flutter_ui/src/widgets/data_source_badge.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('UmerOS app smoke test', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues(const {});
    await PrefsService.instance.init();

    await tester.pumpWidget(UmerOSApp(
      themeProvider: ThemeProvider()..restore(),
      appState: AppState()..restore(),
    ));

    expect(find.byType(UmerOSApp), findsOneWidget);
    await tester.pump(const Duration(seconds: 1));

    // Unmount so the shell's 1-second clock Timer is cancelled and the
    // test ends with no pending timers.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 100));
  });

  // --- Accessibility (a11y) tests ---

  group('a11y semantics', () {
    testWidgets('Dock exposes semantic label', (WidgetTester tester) async {
      final appState = AppState()..restore();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChangeNotifierProvider<AppState>.value(
              value: appState,
              child: Dock(onOpenApp: (_) {}),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.bySemanticsLabel('Application Dock'),
        findsOneWidget,
        reason: 'Dock wrapper must carry Semantics(label: \'Application Dock\')',
      );
    });

    testWidgets('DataSourceBadge Simulated exposes semantic label',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: DataSourceBadge(simulated: true)),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byWidgetPredicate(
          (widget) =>
              widget is Semantics &&
              (widget.properties as dynamic).label == 'Data source: Simulated',
        ),
        findsOneWidget,
        reason: 'Simulated badge must carry Semantics(label: \'Data source: Simulated\')',
      );
    });

    testWidgets('DataSourceBadge Live exposes semantic label',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: DataSourceBadge(simulated: false)),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byWidgetPredicate(
          (widget) =>
              widget is Semantics &&
              (widget.properties as dynamic).label == 'Data source: Live',
        ),
        findsOneWidget,
        reason: 'Live badge must carry Semantics(label: \'Data source: Live\')',
      );
    });

    testWidgets('Menu bar date/time exposes semantic label',
        (WidgetTester tester) async {
      final appState = AppState()..restore();
      final themeProvider = ThemeProvider()..restore();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MultiProvider(
              providers: [
                ChangeNotifierProvider<AppState>.value(value: appState),
                ChangeNotifierProvider<ThemeProvider>.value(value: themeProvider),
              ],
              child: const DesktopShell(),
            ),
          ),
        ),
      );
      await tester.pump(const Duration(seconds: 3));

      expect(
        find.bySemanticsLabel('Date and time \u2014 open Calendar'),
        findsOneWidget,
        reason: 'Date/time status must carry '
            'Semantics(label: \'Date and time \u2014 open Calendar\')',
      );

      // Unmount so the shell's clock Timer is cancelled.
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(milliseconds: 100));
    });
  });
}
