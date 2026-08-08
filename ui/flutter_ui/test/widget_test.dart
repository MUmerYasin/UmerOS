import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/main.dart';

void main() {
  testWidgets('UmerOS app smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const UmerOSApp());
    expect(find.byType(UmerOSApp), findsOneWidget);
    await tester.pump(const Duration(seconds: 1));
  });
}
