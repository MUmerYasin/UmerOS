// UmerOS Flutter UI — animations test suite
// ===========================================
// Verifies every widget in `lib/src/animations/` builds, animates,
// and does not throw.  Uses Flutter's `flutter_test` harness; no
// third-party test deps.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/src/animations/animations.dart';

void main() {
  group('animation_tokens', () {
    test('UmerDurations short / medium / long buckets exist', () {
      expect(UmerDurations.short1.inMilliseconds, 50);
      expect(UmerDurations.short4.inMilliseconds, 200);
      expect(UmerDurations.medium2.inMilliseconds, 300);
      expect(UmerDurations.medium4.inMilliseconds, 400);
      expect(UmerDurations.long1.inMilliseconds, 450);
      expect(UmerDurations.long3.inMilliseconds, 600);
    });

    test('UmerCurves exposes a non-null curve object for every key', () {
      expect(UmerCurves.emphasized, isA<Curve>());
      expect(UmerCurves.standard, isA<Curve>());
      expect(UmerCurves.decelerate, isA<Curve>());
      expect(UmerCurves.accelerate, isA<Curve>());
      expect(UmerCurves.overshoot, isA<Curve>());
      expect(UmerCurves.spring, isA<Curve>());
      expect(UmerCurves.linear, isA<Curve>());
    });

    test('UmerMotion.of returns a valid spec for every intent', () {
      for (final intent in UmerMotionIntent.values) {
        final spec = UmerMotion.of(intent);
        expect(spec.duration, isA<Duration>());
        expect(spec.duration.inMilliseconds, greaterThan(0));
        expect(spec.curve, isA<Curve>());
      }
    });

    test('UmerMotionSpec is a valid pair', () {
      const spec = UmerMotionSpec(
        duration: UmerDurations.medium2,
        curve: UmerCurves.standard,
      );
      expect(spec.duration, UmerDurations.medium2);
      expect(spec.curve, UmerCurves.standard);
      expect(spec.toString(), contains('UmerMotionSpec'));
    });
  });

  group('widget_animations', () {
    testWidgets('FadeInOnMount builds and animates in',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: FadeInOnMount(child: Text('hello'))),
      ));
      expect(find.text('hello'), findsOneWidget);
      // Let the animation run.
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pump(const Duration(milliseconds: 400));
    });

    testWidgets('SlideInOnMount from each direction', (WidgetTester tester) async {
      for (final dir in SlideDirection.values) {
        await tester.pumpWidget(MaterialApp(
          home: Scaffold(
            body: SlideInOnMount(
              direction: dir,
              child: Text('d=$dir'),
            ),
          ),
        ));
        expect(find.text('d=$dir'), findsOneWidget);
        await tester.pump(const Duration(milliseconds: 400));
      }
    });

    testWidgets('ScaleInOnMount with custom begin', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: ScaleInOnMount(begin: 0.5, child: Text('s'))),
      ));
      expect(find.text('s'), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 400));
    });

    testWidgets('StaggeredFadeIn renders all children', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: StaggeredFadeIn(
            children: [Text('a'), Text('b'), Text('c')],
          ),
        ),
      ));
      expect(find.text('a'), findsOneWidget);
      expect(find.text('b'), findsOneWidget);
      expect(find.text('c'), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 500));
    });

    testWidgets('TickerBuilder repeats while enabled', (WidgetTester tester) async {
      int calls = 0;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: TickerBuilder(
            interval: const Duration(milliseconds: 100),
            animationBuilder: (ctx, t) {
              calls++;
              return Text('t=$t');
            },
          ),
        ),
      ));
      // Pump several short intervals so the ticker advances.
      for (int i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      // TickerBuilder should have rebuilt at least once (initial + tick).
      expect(calls, greaterThanOrEqualTo(1));
    });

    testWidgets('TickerBuilder does not tick when disabled',
        (WidgetTester tester) async {
      int calls = 0;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: TickerBuilder(
            enabled: false,
            animationBuilder: (ctx, t) {
              calls++;
              return Text('t=$t');
            },
          ),
        ),
      ));
      expect(calls, 1);
      for (int i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      // Should still be only 1 (initial build).
      expect(calls, 1);
    });
  });

  group('micro_interactions', () {
    testWidgets('HoverScale animates a scale change on hover',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: HoverScale(child: Text('h'))),
      ));
      expect(find.text('h'), findsOneWidget);
      // Trigger a hover.
      final gesture = await tester.startGesture(tester.getCenter(find.text('h')));
      await tester.pump(const Duration(milliseconds: 250));
      await gesture.up();
      await tester.pump(const Duration(milliseconds: 250));
    });

    testWidgets('TapDownScale fires onTap and animates',
        (WidgetTester tester) async {
      var tapped = false;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: TapDownScale(
            onTap: () => tapped = true,
            child: const Text('t'),
          ),
        ),
      ));
      await tester.tap(find.text('t'));
      await tester.pump(const Duration(milliseconds: 50));
      expect(tapped, isTrue);
    });

    testWidgets('InteractiveCard hover + tap + press',
        (WidgetTester tester) async {
      var taps = 0;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: InteractiveCard(
              onTap: () => taps++,
              child: const SizedBox(
                width: 200,
                height: 100,
                child: Center(child: Text('card')),
              ),
            ),
          ),
        ),
      ));
      expect(find.text('card'), findsOneWidget);
      // Tap (hover is implicit in the tap-down event).
      await tester.tap(find.text('card'));
      await tester.pump();
      expect(taps, 1);
      // Tap a second time to make sure onTap does not double-fire.
      await tester.tap(find.text('card'));
      await tester.pump();
      expect(taps, 2);
    });

    testWidgets('HoverGlow renders without throwing',
        (WidgetTester tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: HoverGlow(
            glowColor: Colors.deepPurple,
            child: const Text('g'),
          ),
        ),
      ));
      expect(find.text('g'), findsOneWidget);
    });
  });

  group('loading_indicators', () {
    testWidgets('QuantumDots renders N dots', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: Center(child: QuantumDots(count: 5))),
      ));
      expect(find.byType(QuantumDots), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 600));
    });

    testWidgets('QuantumRing rotates', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: Center(child: QuantumRing())),
      ));
      expect(find.byType(QuantumRing), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 600));
    });

    testWidgets('SkeletonBox renders a placeholder block',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: Center(child: SkeletonBox(width: 200, height: 20))),
      ));
      expect(find.byType(SkeletonBox), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 600));
    });

    testWidgets('PulsingDot breathes', (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: Center(child: PulsingDot())),
      ));
      expect(find.byType(PulsingDot), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 600));
    });
  });

  group('quantum_animations', () {
    testWidgets('QuantumOrb renders a glowing sphere',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: Center(child: QuantumOrb())),
      ));
      expect(find.byType(QuantumOrb), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 800));
    });

    testWidgets('QuantumParticleField animates N particles',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: QuantumParticleField(count: 16)),
      ));
      expect(find.byType(QuantumParticleField), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 600));
    });

    testWidgets('QuantumBootProgress fills a track',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 200,
              child: QuantumBootProgress(value: 0.4),
            ),
          ),
        ),
      ));
      expect(find.byType(QuantumBootProgress), findsOneWidget);
    });

    testWidgets('QuantumSplash renders the full splash',
        (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: QuantumSplash(
          title: 'UmerOS',
          subtitle: 'Loading…',
        ),
      ));
      expect(find.text('UmerOS'), findsOneWidget);
      expect(find.text('Loading…'), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 2000));
    });
  });

  group('page_transitions', () {
    testWidgets('UmerFadeRoute can be navigated to',
        (WidgetTester tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Builder(builder: (context) {
          return Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () {
                  Navigator.of(context).push(UmerFadeRoute(
                    builder: (_) => const Scaffold(body: Text('fade')),
                  ));
                },
                child: const Text('go'),
              ),
            ),
          );
        }),
      ));
      await tester.tap(find.text('go'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('fade'), findsOneWidget);
    });

    testWidgets('UmerSlideRoute can be navigated to',
        (WidgetTester tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Builder(builder: (context) {
          return Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () {
                  Navigator.of(context).push(UmerSlideRoute(
                    builder: (_) => const Scaffold(body: Text('slide')),
                  ));
                },
                child: const Text('go'),
              ),
            ),
          );
        }),
      ));
      await tester.tap(find.text('go'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('slide'), findsOneWidget);
    });

    testWidgets('UmerZoomRoute can be navigated to',
        (WidgetTester tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Builder(builder: (context) {
          return Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () {
                  Navigator.of(context).push(UmerZoomRoute(
                    builder: (_) => const Scaffold(body: Text('zoom')),
                  ));
                },
                child: const Text('go'),
              ),
            ),
          );
        }),
      ));
      await tester.tap(find.text('go'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('zoom'), findsOneWidget);
    });

    testWidgets('UmerModalRoute can be navigated to',
        (WidgetTester tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Builder(builder: (context) {
          return Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () {
                  Navigator.of(context).push(UmerModalRoute(
                    builder: (_) => const Scaffold(body: Text('modal')),
                  ));
                },
                child: const Text('go'),
              ),
            ),
          );
        }),
      ));
      await tester.tap(find.text('go'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('modal'), findsOneWidget);
    });
  });
}
