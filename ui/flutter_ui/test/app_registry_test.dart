// UmerOS Flutter UI — App registry contract tests
// ================================================
// Guards the single-source-of-truth invariant (review Hotspot H23) and
// the plain-language naming rule (Hotspot H24 / Nielsen #2).

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_ui/src/core/app_registry.dart';

void main() {
  group('AppRegistry invariants', () {
    test('registry is non-empty', () {
      expect(AppRegistry.apps, isNotEmpty);
    });

    test('every app id is unique and non-empty', () {
      final ids = AppRegistry.apps.map((a) => a.id).toList();
      expect(ids.every((id) => id.trim().isNotEmpty), isTrue);
      expect(ids.toSet().length, ids.length, reason: 'duplicate ids: $ids');
    });

    test('every app has a plain-language title and description', () {
      for (final app in AppRegistry.apps) {
        expect(app.title.trim().isNotEmpty, isTrue,
            reason: '${app.id} has empty title');
        expect(app.description.trim().isNotEmpty, isTrue,
            reason: '${app.id} has empty description');
        // Titles must not contain OS-internal jargon (H24 guard).
        final jargon = ['cpuidle', 'governor', 'syscall', 'vfs'];
        for (final word in jargon) {
          expect(
            app.title.toLowerCase().contains(word),
            isFalse,
            reason: '${app.id} title "${app.title}" contains jargon "$word"',
          );
        }
      }
    });

    test('legacy jargon labels are retired', () {
      // H24 regression guards.
      expect(AppRegistry.byId('power')!.title, 'Power & Performance');
    });

    test('byId resolves every registered id and returns null for unknown',
        () {
      for (final app in AppRegistry.apps) {
        expect(AppRegistry.byId(app.id), same(app));
      }
      expect(AppRegistry.byId('does-not-exist'), isNull);
    });

    test('core apps exist with expected ids', () {
      const expectedIds = [
        'browser', 'terminal', 'files', 'monitor', 'power', 'settings',
        'editor', 'packages', 'network', 'calendar', 'calculator',
        'quantum', 'security', 'antivirus', 'boot', 'games', 'docs',
      ];
      for (final id in expectedIds) {
        expect(AppRegistry.byId(id), isNotNull, reason: 'missing app: $id');
      }
    });

    test('filterKnownIds drops stale persisted pins', () {
      final known = AppRegistry.filterKnownIds(['terminal', 'ghost-app']);
      expect(known, ['terminal']);
    });
  });
}
