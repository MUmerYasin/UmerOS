/// UmerOS Flutter UI — Central Application Registry
/// ==================================================
/// **Single source of truth** for every app that can appear on the
/// desktop grid, in Spotlight search, in the LaunchPad, and on the
/// Dock. This resolves Hotspot H23 from the project review standard:
/// previously the same app list was hardcoded in four widgets and
/// drifted apart.
///
/// To add a new app:
///   1. Create `lib/src/apps/<name>_app.dart` with a const constructor.
///   2. Add ONE entry below.
///   Every surface updates automatically.
///
/// HCI rules encoded here:
///   * Nielsen #2 (match the real world): [AppDefinition.title] uses
///     plain, task-oriented language — no OS-internal jargon
///     (resolves the H24 "CPUIdle & Governor" / "Power & Idle" drift).
///   * Nielsen #6 (recognition over recall): every app carries a
///     human-readable [description] shown in search results.
library;

import 'package:flutter/material.dart';

import '../apps/ai_assistant_app.dart';
import '../apps/antivirus_app.dart';
import '../apps/bin_app.dart';
import '../apps/boot_manager_app.dart';
import '../apps/browser_app.dart';
import '../apps/calculator_app.dart';
import '../apps/calendar_app.dart';
import '../apps/docs_app.dart';
import '../apps/file_manager_app.dart';
import '../apps/games_app.dart';
import '../apps/network_manager_app.dart';
import '../apps/package_manager_app.dart';
import '../apps/power_governor_app.dart';
import '../apps/quantum_app.dart';
import '../apps/security_app.dart';
import '../apps/settings_app.dart';
import '../apps/system_monitor_app.dart';
import '../apps/terminal_app.dart';
import '../apps/text_editor_app.dart';

/// Logical groupings used by Spotlight subtitles and future LaunchPad
/// filters. Keep user-facing wording, never internal module names.
enum AppCategory { system, tools, development, security, media }

extension AppCategoryLabel on AppCategory {
  String get label => switch (this) {
        AppCategory.system => 'System',
        AppCategory.tools => 'Tools',
        AppCategory.development => 'Development',
        AppCategory.security => 'Security',
        AppCategory.media => 'Media',
      };
}

/// Signature used by every shell surface (desktop grid, Spotlight,
/// LaunchPad, Dock) to launch an app from the registry.
typedef OpenAppFn = void Function(AppDefinition app);

class AppDefinition {
  /// Stable identifier. Also used by pinned-dock persistence — do not
  /// rename without a migration.
  final String id;

  /// Plain-language name shown to users everywhere.
  final String title;

  /// One-line explanation surfaced in Spotlight/LaunchPad.
  final String description;
  final IconData icon;
  final Color color;
  final AppCategory category;
  final WidgetBuilder builder;

  const AppDefinition({
    required this.id,
    required this.title,
    required this.description,
    required this.icon,
    required this.color,
    required this.category,
    required this.builder,
  });
}

abstract final class AppRegistry {
  static final List<AppDefinition> apps = [
    // ── System ────────────────────────────────────────────────────
    AppDefinition(
      id: 'files',
      title: 'File Manager',
      description: 'Browse, open and organise your files.',
      icon: Icons.folder,
      color: Colors.amber.shade700,
      category: AppCategory.system,
      builder: (_) => const FileManagerApp(),
    ),
    AppDefinition(
      id: 'monitor',
      title: 'System Monitor',
      description: 'See live CPU, memory and process activity.',
      icon: Icons.monitor_heart,
      color: Colors.green,
      category: AppCategory.system,
      builder: (_) => const SystemMonitorApp(),
    ),
    AppDefinition(
      id: 'power',
      title: 'Power & Performance',
      description: 'Control performance mode, idle states and power.',
      icon: Icons.bolt,
      color: Colors.amber,
      category: AppCategory.system,
      builder: (_) => const PowerGovernorApp(),
    ),
    AppDefinition(
      id: 'settings',
      title: 'Settings',
      description: 'Personalise appearance, sound, network and more.',
      icon: Icons.tune,
      color: Colors.blueGrey,
      category: AppCategory.system,
      builder: (_) => const SettingsApp(),
    ),
    AppDefinition(
      id: 'network',
      title: 'Network Manager',
      description: 'Manage Wi-Fi, connections and network settings.',
      icon: Icons.wifi,
      color: Colors.cyan,
      category: AppCategory.system,
      builder: (_) => const NetworkManagerApp(),
    ),
    AppDefinition(
      id: 'boot',
      title: 'Boot Manager',
      description: 'Inspect boot entries and startup configuration.',
      icon: Icons.power_settings_new,
      color: Colors.amber,
      category: AppCategory.system,
      builder: (_) => const BootManagerApp(),
    ),

    // ── Tools ─────────────────────────────────────────────────────
    AppDefinition(
      id: 'ai',
      title: 'AI Assistant',
      description:
          'Chat with local or cloud AI models — your keys, your consent.',
      icon: Icons.auto_awesome,
      color: Color(0xFF7C4DFF),
      category: AppCategory.tools,
      builder: (_) => const AiAssistantApp(),
    ),
    AppDefinition(
      id: 'browser',
      title: 'Browser',
      description: 'Browse the web with the built-in UmerOS browser.',
      icon: Icons.language,
      color: Colors.blue,
      category: AppCategory.tools,
      builder: (_) => const BrowserApp(),
    ),
    AppDefinition(
      id: 'editor',
      title: 'Text Editor',
      description: 'Write and edit text files with syntax help.',
      icon: Icons.edit_note,
      color: Colors.orange,
      category: AppCategory.tools,
      builder: (_) => const TextEditorApp(),
    ),
    AppDefinition(
      id: 'calendar',
      title: 'Calendar',
      description: 'View dates, plan events and check schedules.',
      icon: Icons.calendar_month,
      color: Colors.indigo,
      category: AppCategory.tools,
      builder: (_) => const CalendarApp(),
    ),
    AppDefinition(
      id: 'calculator',
      title: 'Calculator',
      description: 'Quick calculations with a scientific keypad.',
      icon: Icons.calculate,
      color: Colors.blueGrey,
      category: AppCategory.tools,
      builder: (_) => const CalculatorApp(),
    ),
    AppDefinition(
      id: 'docs',
      title: 'Documentation',
      description: 'Read UmerOS guides, manuals and tutorials.',
      icon: Icons.menu_book,
      color: Colors.deepOrange,
      category: AppCategory.tools,
      builder: (_) => const DocsApp(),
    ),

    // ── Development ───────────────────────────────────────────────
    AppDefinition(
      id: 'bin',
      title: 'Bin Manager',
      description: 'Inspect essential binaries and run built-in commands.',
      icon: Icons.terminal,
      color: Colors.lightBlue,
      category: AppCategory.development,
      builder: (_) => const BinApp(),
    ),
    AppDefinition(
      id: 'terminal',
      title: 'Terminal',
      description: 'Run shell commands on UmerOS.',
      icon: Icons.terminal,
      color: Colors.teal,
      category: AppCategory.development,
      builder: (_) => const TerminalApp(),
    ),
    AppDefinition(
      id: 'packages',
      title: 'Package Manager',
      description: 'Install, update and remove software packages.',
      icon: Icons.inventory_2,
      color: Colors.purple,
      category: AppCategory.development,
      builder: (_) => const PackageManagerApp(),
    ),
    AppDefinition(
      id: 'quantum',
      title: 'Quantum Simulator',
      description: 'Build circuits, run simulations and transpile jobs.',
      icon: Icons.blur_circular,
      color: Colors.deepPurple,
      category: AppCategory.development,
      builder: (_) => const QuantumSimApp(),
    ),

    // ── Security ──────────────────────────────────────────────────
    AppDefinition(
      id: 'security',
      title: 'Security Center',
      description: 'Zero-trust status, keys and threat overview.',
      icon: Icons.shield,
      color: Colors.redAccent,
      category: AppCategory.security,
      builder: (_) => const SecurityApp(),
    ),
    AppDefinition(
      id: 'antivirus',
      title: 'Antivirus',
      description: 'Scan for malware and manage quarantined items.',
      icon: Icons.health_and_safety,
      color: Colors.lightGreen,
      category: AppCategory.security,
      builder: (_) => const AntivirusApp(),
    ),

    // ── Media ─────────────────────────────────────────────────────
    AppDefinition(
      id: 'games',
      title: 'Games',
      description: 'Play the games bundled with UmerOS.',
      icon: Icons.sports_esports,
      color: Colors.pink,
      category: AppCategory.media,
      builder: (_) => const GamesApp(),
    ),
  ];

  static final Map<String, AppDefinition> _byId = {
    for (final app in apps) app.id: app,
  };

  /// Look up an app by its stable id; null when unknown.
  static AppDefinition? byId(String id) => _byId[id];

  /// Apps whose ids are missing from [ids] but exist in the registry —
  /// handy for repairing persisted dock lists after renames.
  static List<String> filterKnownIds(Iterable<String> ids) =>
      ids.where((id) => _byId.containsKey(id)).toList();
}
