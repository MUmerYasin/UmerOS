import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/src/widgets/live_view_capsule.dart';
import 'package:flutter_ui/src/widgets/atomic_card.dart';

void main() {
  group('Live Window LiveViewCapsule Tests', () {
    testWidgets('Renders empty when activeTasks is empty', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LiveViewCapsule(activeTasks: []),
          ),
        ),
      );

      expect(find.byType(LiveViewCapsule), findsOneWidget);
      expect(find.text('In progress...'), findsNothing);
    });

    testWidgets('Renders active task title, progress, and icon', (tester) async {
      final tasks = [
        LiveTaskInfo(
          taskId: 'quantum_sim_1',
          title: 'Quantum Shor Sim',
          icon: Icons.biotech,
          progress: 0.65,
          statusText: 'Factoring RSA-1024',
        ),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: LiveViewCapsule(activeTasks: tasks),
          ),
        ),
      );

      expect(find.text('Quantum Shor Sim'), findsOneWidget);
      expect(find.text('65%'), findsOneWidget);
      expect(find.byIcon(Icons.biotech), findsOneWidget);
    });

    testWidgets('Tapping expands and triggers cancel callback', (tester) async {
      String? cancelledId;
      final tasks = [
        LiveTaskInfo(
          taskId: 'task_abc',
          title: 'OTA Update',
          icon: Icons.system_update,
          progress: 0.30,
        ),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: LiveViewCapsule(
              activeTasks: tasks,
              onCancelTask: (id) => cancelledId = id,
            ),
          ),
        ),
      );

      // Tap capsule to expand
      await tester.tap(find.text('OTA Update'));
      await tester.pump(const Duration(milliseconds: 350));

      // Find close icon and tap it
      expect(find.byIcon(Icons.close), findsOneWidget);
      await tester.tap(find.byIcon(Icons.close));
      await tester.pump();

      expect(cancelledId, 'task_abc');
    });
  });

  group('Atomic Services AtomicCard Tests', () {
    testWidgets('Renders title, subtitle, and content', (tester) async {
      bool expanded = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AtomicCard(
              title: 'Quantum Vitals',
              subtitle: 'Local Simulator',
              icon: Icons.memory,
              size: AtomicCardSize.medium,
              content: const Text('Qubits: 16 | Fidelity: 99.4%'),
              onExpand: () => expanded = true,
            ),
          ),
        ),
      );

      expect(find.text('Quantum Vitals'), findsOneWidget);
      expect(find.text('Local Simulator'), findsOneWidget);
      expect(find.text('Qubits: 16 | Fidelity: 99.4%'), findsOneWidget);
      expect(find.byIcon(Icons.memory), findsOneWidget);

      // Tap expand button
      await tester.tap(find.byIcon(Icons.open_in_new));
      expect(expanded, isTrue);
    });
  });
}
