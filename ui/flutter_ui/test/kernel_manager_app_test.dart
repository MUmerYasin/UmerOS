import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/src/apps/kernel_manager_app.dart';
import 'package:flutter_ui/src/core/app_registry.dart';

void main() {
  group('KernelManagerApp Registration Tests', () {
    test('KernelManagerApp is registered in AppRegistry', () {
      final app = AppRegistry.byId('kernel_manager');
      expect(app, isNotNull);
      expect(app!.id, 'kernel_manager');
      expect(app.title, 'Kernel & QoS Manager');
      expect(app.category, AppCategory.system);
      expect(app.icon, Icons.developer_board);
    });
  });

  group('KernelManagerApp Widget & HCI Tests', () {
    void setupDesktopSurface(WidgetTester tester) {
      tester.view.physicalSize = const Size(1280, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });
    }

    testWidgets('Renders header and QoS Scheduler KPI metrics', (tester) async {
      setupDesktopSurface(tester);
      await tester.pumpWidget(
        const MaterialApp(
          home: KernelManagerApp(),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      // Check header title and subtitle
      expect(find.text('Kernel & QoS Manager'), findsOneWidget);
      expect(find.textContaining('HarmonyOS QoS Tiers'), findsOneWidget);

      // Check Navigation tabs
      expect(find.text('QoS Scheduler'), findsOneWidget);
      expect(find.text('Membox Pools'), findsOneWidget);
      expect(find.text('Process Controller'), findsOneWidget);
      expect(find.text('SoftBus & Tasks'), findsOneWidget);

      // Check Tab 0 KPIs
      expect(find.text('Frame Latency Telemetry'), findsOneWidget);
      expect(find.text('QoS Background Throttle'), findsOneWidget);
      expect(find.text('Priority Inheritance (PI) Mutex & Inversion Shield'), findsOneWidget);
    });

    testWidgets('Simulate frame drop triggers throttling', (tester) async {
      setupDesktopSurface(tester);
      await tester.pumpWidget(
        const MaterialApp(
          home: KernelManagerApp(),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      // Tap simulate frame drop button
      final simulateBtn = find.text('Simulate Drop');
      expect(simulateBtn, findsOneWidget);
      await tester.tap(simulateBtn);
      await tester.pump(const Duration(milliseconds: 200));

      // Should show simulated latency and throttling ACTIVE
      expect(find.text('28.5 ms'), findsOneWidget);
      expect(find.text('ACTIVE'), findsOneWidget);
    });

    testWidgets('Switch to Membox Pools tab and test block & canary interactions', (tester) async {
      setupDesktopSurface(tester);
      await tester.pumpWidget(
        const MaterialApp(
          home: KernelManagerApp(),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      // Switch to Membox Pools tab
      await tester.tap(find.text('Membox Pools'));
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.textContaining('Membox Block Allocator Pools'), findsOneWidget);
      expect(find.text('Pool: fast_packets'), findsOneWidget);
      expect(find.text('Pool: ipc_buffers'), findsOneWidget);
      expect(find.text('Pool: quantum_events'), findsOneWidget);

      // Test corruption button
      final corruptBtn = find.text('Test Corruption').first;
      await tester.tap(corruptBtn);
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.text('Heal Canary'), findsOneWidget);
    });

    testWidgets('Switch to Process Controller tab and filter processes', (tester) async {
      setupDesktopSurface(tester);
      await tester.pumpWidget(
        const MaterialApp(
          home: KernelManagerApp(),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      // Switch to Process Controller tab
      await tester.tap(find.text('Process Controller'));
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.text('umer_kernel'), findsOneWidget);
      expect(find.text('flutter_desktop_ui'), findsOneWidget);
      expect(find.text('quantum_sim_engine'), findsOneWidget);

      // Enter search text
      await tester.enterText(find.byType(TextField), 'quantum');
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.text('quantum_sim_engine'), findsOneWidget);
      expect(find.text('flutter_desktop_ui'), findsNothing);
    });

    testWidgets('Switch to SoftBus tab and inspect nodes and live tasks', (tester) async {
      setupDesktopSurface(tester);
      await tester.pumpWidget(
        const MaterialApp(
          home: KernelManagerApp(),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));

      // Switch to SoftBus & Tasks tab
      await tester.tap(find.text('SoftBus & Tasks'));
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.text('Distributed SoftBus Discovery & Mesh Nodes'), findsOneWidget);
      expect(find.text('umer-workstation-local'), findsOneWidget);
      expect(find.text('umer-quantum-rig-alpha'), findsOneWidget);
      expect(find.text('Live Window Background Tasks (实况窗 Engine)'), findsOneWidget);
    });
  });
}
