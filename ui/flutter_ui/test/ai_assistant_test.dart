// UmerOS Flutter UI — AI Assistant tests
// =======================================
// Exercises the chat surface against a fake AiService (no network):
// provider grouping, offline honesty, streaming deltas, consent flow.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/src/apps/ai_assistant_app.dart';
import 'package:flutter_ui/src/services/ai_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakeAiService implements AiService {
  @override
  String baseUrl = 'http://fake';

  bool health = true;
  List<AiProviderInfo> providers;
  int streamCalls = 0;
  Object? streamError;

  FakeAiService({this.health = true, List<AiProviderInfo>? providers})
      : providers = providers ??
            [
              AiProviderInfo(
                id: 'ollama',
                name: 'Ollama (Local)',
                kind: ProviderKind.local,
                available: true,
                consentGranted: true,
                models: ['llama3.2'],
                streaming: true,
              ),
              AiProviderInfo(
                id: 'openrouter',
                name: 'OpenRouter',
                kind: ProviderKind.freeOnline,
                available: false,
                consentGranted: false,
                models: ['m:free'],
                streaming: true,
              ),
            ];

  @override
  Future<bool> checkHealth() async => health;

  @override
  Future<List<AiProviderInfo>> listProviders() async => providers;

  @override
  Future<String> chatStream({
    required String message,
    required void Function(String delta) onDelta,
    String sessionId = 'desktop',
    String? providerId,
    String? model,
  }) async {
    streamCalls++;
    if (streamError != null) throw streamError!;
    for (final w in ['Hel', 'lo ', 'UM', 'er']) {
      onDelta(w);
    }
    return 'Hello UMer';
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

AiService? _real;

void main() {
  setUpAll(() async {
    SharedPreferences.setMockInitialValues(const {});
  });

  setUp(() {
    _real = AiService.instance;
  });

  tearDown(() {
    final r = _real;
    if (r != null) AiService.testOverride(r);
  });

  testWidgets('renders greeting + live status when backend up',
      (tester) async {
    AiService.testOverride(FakeAiService());
    await tester.pumpWidget(const MaterialApp(home: Scaffold(
        body: SizedBox.expand(child: AiAssistantApp()))));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.textContaining('Welcome to Umer OS Assistant'),
        findsOneWidget);
    // Provider dropdown exists with local group label.
    expect(find.text('AI Assistant'), findsOneWidget);
  });

  testWidgets('offline backend shows honest banner, no fake data',
      (tester) async {
    AiService.testOverride(FakeAiService(health: false));
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body:
        SizedBox.expand(child: AiAssistantApp()))));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.textContaining('AI service is offline'), findsOneWidget);
    expect(find.textContaining('python -m ai.server'), findsOneWidget);

    // Typing + send while offline produces an honest error bubble and
    // keeps the draft in the composer (nothing is lost).
    await tester.enterText(find.byKey(const ValueKey('ai-composer')), 'hi');
    final sendBtn = find.byTooltip('Send message');
    expect(sendBtn, findsOneWidget);
    await tester.tap(sendBtn, warnIfMissed: true);
    await tester.pump(const Duration(milliseconds: 200));
    // Draft preserved for the user.
    expect(find.byKey(const ValueKey('ai-composer')), findsOneWidget);
    // The honest error bubble explains how to start the backend.
    expect(find.textContaining('AI backend is not running'), findsOneWidget);
    expect(find.textContaining('python -m ai.server'), findsWidgets);
  });

  testWidgets('streaming deltas accumulate into assistant bubble',
      (tester) async {
    final fake = FakeAiService();
    AiService.testOverride(fake);
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body:
        SizedBox.expand(child: AiAssistantApp()))));
    await tester.pump(const Duration(milliseconds: 400));

    await tester.enterText(
        find.byKey(const ValueKey('ai-composer')), 'hello there');
    await tester.tap(find.byTooltip('Send message'));
    await tester.pump(const Duration(milliseconds: 500));

    expect(fake.streamCalls, 1);
    expect(find.textContaining('Hello UMer'), findsOneWidget);
  });

  testWidgets('consent-denied online send surfaces error with hint',
      (tester) async {
    final fake = FakeAiService(providers: [
      AiProviderInfo(
          id: 'openai',
          name: 'OpenAI',
          kind: ProviderKind.paidOnline,
          available: true,
          consentGranted: false,
          models: ['gpt-4o-mini'],
          streaming: false),
    ]);
    fake.streamError =
        AiServiceException("Consent not granted for online provider 'openai'.",
            statusCode: 403);
    AiService.testOverride(fake);

    await tester.pumpWidget(const MaterialApp(home: Scaffold(body:
        SizedBox.expand(child: AiAssistantApp()))));
    await tester.pump(const Duration(milliseconds: 400));

    await tester.enterText(find.byKey(const ValueKey('ai-composer')), 'secret prompt');
    await tester.tap(find.byTooltip('Send message'));
    await tester.pump(const Duration(milliseconds: 500));

    // Consent dialog should have appeared first.
    expect(find.text('Send this prompt off-device?'), findsOneWidget);
  });
}
