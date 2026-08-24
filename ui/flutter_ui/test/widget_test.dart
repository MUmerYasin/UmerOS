import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/main.dart';
import 'package:flutter_ui/src/core/app_state.dart';
import 'package:flutter_ui/src/core/theme_provider.dart';
import 'package:flutter_ui/src/services/prefs_service.dart';
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
}
