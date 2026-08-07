import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'app_state.dart';
import 'theme_provider.dart';
import '../widgets/dock.dart';
import '../widgets/draggable_window.dart';
import '../apps/terminal_app.dart';
import '../apps/file_manager_app.dart';
import '../apps/system_monitor_app.dart';
import '../apps/settings_app.dart';
import '../apps/text_editor_app.dart';
import '../apps/package_manager_app.dart';
import '../apps/network_manager_app.dart';
import '../apps/calendar_app.dart';
import '../apps/calculator_app.dart';
import '../apps/quantum_sim_app.dart';
import '../apps/security_app.dart';
import '../apps/boot_manager_app.dart';
import '../apps/games_app.dart';
import '../apps/docs_app.dart';

class DesktopShell extends StatefulWidget {
  const DesktopShell({super.key});

  @override
  State<DesktopShell> createState() => _DesktopShellState();
}

class _DesktopShellState extends State<DesktopShell> {
  String _currentTime = '';
  bool _showLaunchPad = false;

  @override
  void initState() {
    super.initState();
    _updateTime();
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return false;
      _updateTime();
      return true;
    });
  }

  void _updateTime() {
    final now = DateTime.now();
    setState(() {
      _currentTime = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
    });
  }

  void _openApp(String id, String title, IconData icon, Widget child) {
    context.read<AppState>().openWindow(
      id: id,
      title: title,
      icon: icon,
      child: child,
    );
    setState(() => _showLaunchPad = false);
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final themeProvider = context.watch<ThemeProvider>();

    return Scaffold(
      body: DesktopBackground(
        child: Stack(
          children: [
            // Menu Bar
            _MenuBar(
              currentTime: _currentTime,
              onToggleLaunchPad: () => setState(() => _showLaunchPad = !_showLaunchPad),
              onToggleTheme: () => themeProvider.toggleTheme(),
            ),

            // Desktop Area with Windows
            Positioned.fill(
              top: 32,
              bottom: 80,
              child: Stack(
                children: [
                  // Desktop Grid Icons
                  Positioned.fill(
                    child: _DesktopGrid(
                      onOpenApp: _openApp,
                    ),
                  ),

                  // Windows
                  ...appState.windows
                      .where((w) => !w.isMinimized)
                      .map((w) => DraggableWindow(window: w)),
                ],
              ),
            ),

            // Dock
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: Dock(
                items: _getDockItems(),
              ),
            ),

            // LaunchPad Overlay
            if (_showLaunchPad)
              _LaunchPad(
                onClose: () => setState(() => _showLaunchPad = false),
                onOpenApp: _openApp,
              ),
          ],
        ),
      ),
    );
  }

  List<DockItem> _getDockItems() {
    return [
      DockItem(
        id: 'terminal',
        label: 'Terminal',
        icon: Icons.terminal,
        color: Colors.teal,
        onTap: () => _openApp('terminal', 'Terminal', Icons.terminal, const TerminalApp()),
      ),
      DockItem(
        id: 'files',
        label: 'Files',
        icon: Icons.folder,
        color: Colors.blue,
        onTap: () => _openApp('files', 'File Manager', Icons.folder, const FileManagerApp()),
      ),
      DockItem(
        id: 'monitor',
        label: 'Monitor',
        icon: Icons.monitor,
        color: Colors.green,
        onTap: () => _openApp('monitor', 'System Monitor', Icons.monitor, const SystemMonitorApp()),
      ),
      DockItem(
        id: 'settings',
        label: 'Settings',
        icon: Icons.settings,
        color: Colors.grey,
        onTap: () => _openApp('settings', 'Settings', Icons.settings, const SettingsApp()),
      ),
      DockItem(
        id: 'editor',
        label: 'Editor',
        icon: Icons.edit_document,
        color: Colors.orange,
        onTap: () => _openApp('editor', 'Text Editor', Icons.edit_document, const TextEditorApp()),
      ),
      DockItem(
        id: 'packages',
        label: 'Packages',
        icon: Icons.inventory_2,
        color: Colors.purple,
        onTap: () => _openApp('packages', 'Package Manager', Icons.inventory_2, const PackageManagerApp()),
      ),
      DockItem(
        id: 'network',
        label: 'Network',
        icon: Icons.wifi,
        color: Colors.cyan,
        onTap: () => _openApp('network', 'Network Manager', Icons.wifi, const NetworkManagerApp()),
      ),
      DockItem(
        id: 'quantum',
        label: 'Quantum',
        icon: Icons.blur_circular,
        color: Colors.indigo,
        onTap: () => _openApp('quantum', 'Quantum Simulator', Icons.blur_circular, const QuantumSimApp()),
      ),
      DockItem(
        id: 'security',
        label: 'Security',
        icon: Icons.shield,
        color: Colors.red,
        onTap: () => _openApp('security', 'Security Manager', Icons.shield, const SecurityApp()),
      ),
      DockItem(
        id: 'games',
        label: 'Games',
        icon: Icons.sports_esports,
        color: Colors.pink,
        onTap: () => _openApp('games', 'Games', Icons.sports_esports, const GamesApp()),
      ),
      DockItem(
        id: 'docs',
        label: 'Docs',
        icon: Icons.menu_book,
        color: Colors.brown,
        onTap: () => _openApp('docs', 'Documentation', Icons.menu_book, const DocsApp()),
      ),
    ];
  }
}

class _MenuBar extends StatelessWidget {
  final String currentTime;
  final VoidCallback onToggleLaunchPad;
  final VoidCallback onToggleTheme;

  const _MenuBar({
    required this.currentTime,
    required this.onToggleLaunchPad,
    required this.onToggleTheme,
  });

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: Container(
        height: 32,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.9),
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
            ),
          ),
        ),
        child: Row(
          children: [
            // UmerOS Logo
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: GestureDetector(
                onTap: onToggleLaunchPad,
                child: Row(
                  children: [
                    Icon(
                      Icons.computer,
                      size: 18,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'UmerOS',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Menu Items
            _MenuItem(label: 'File'),
            _MenuItem(label: 'Edit'),
            _MenuItem(label: 'View'),
            _MenuItem(label: 'Go'),
            _MenuItem(label: 'Window'),
            _MenuItem(label: 'Help'),

            const Spacer(),

            // Theme Toggle
            GestureDetector(
              onTap: onToggleTheme,
              child: Icon(
                Theme.of(context).brightness == Brightness.dark
                    ? Icons.light_mode
                    : Icons.dark_mode,
                size: 16,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(width: 12),

            // System Info
            Icon(Icons.wifi, size: 14, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7)),
            const SizedBox(width: 8),
            Icon(Icons.battery_full, size: 14, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7)),
            const SizedBox(width: 8),

            // Time
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Text(
                currentTime,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
            ),
          ],
        ),
      ),
    ).animate().slideY(begin: -0.1, end: 0, duration: 300.ms);
  }
}

class _MenuItem extends StatelessWidget {
  final String label;

  const _MenuItem({required this.label});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          onTap: () {},
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.8),
            ),
          ),
        ),
      ),
    );
  }
}

class _DesktopGrid extends StatelessWidget {
  final Function(String id, String title, IconData icon, Widget child) onOpenApp;

  const _DesktopGrid({required this.onOpenApp});

  @override
  Widget build(BuildContext context) {
    final apps = [
      _DesktopApp('Terminal', Icons.terminal, Colors.teal, 'terminal', const TerminalApp()),
      _DesktopApp('Files', Icons.folder, Colors.blue, 'files', const FileManagerApp()),
      _DesktopApp('Monitor', Icons.monitor, Colors.green, 'monitor', const SystemMonitorApp()),
      _DesktopApp('Settings', Icons.settings, Colors.grey, 'settings', const SettingsApp()),
      _DesktopApp('Editor', Icons.edit_document, Colors.orange, 'editor', const TextEditorApp()),
      _DesktopApp('Packages', Icons.inventory_2, Colors.purple, 'packages', const PackageManagerApp()),
      _DesktopApp('Network', Icons.wifi, Colors.cyan, 'network', const NetworkManagerApp()),
      _DesktopApp('Quantum', Icons.blur_circular, Colors.indigo, 'quantum', const QuantumSimApp()),
      _DesktopApp('Security', Icons.shield, Colors.red, 'security', const SecurityApp()),
      _DesktopApp('Boot', Icons.power_settings_new, Colors.amber, 'boot', const BootManagerApp()),
      _DesktopApp('Games', Icons.sports_esports, Colors.pink, 'games', const GamesApp()),
      _DesktopApp('Docs', Icons.menu_book, Colors.brown, 'docs', const DocsApp()),
    ];

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Wrap(
        spacing: 24,
        runSpacing: 24,
        children: apps.map((app) {
          return SizedBox(
            width: 80,
            child: GestureDetector(
              onTap: () => onOpenApp(app.id, app.label, app.icon, app.child),
              child: Column(
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: app.color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Icon(
                      app.icon,
                      size: 32,
                      color: app.color,
                    ),
                  ).animate().scale(
                    begin: const Offset(0.9, 0.9),
                    end: const Offset(1, 1),
                    duration: 200.ms,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    app.label,
                    style: TextStyle(
                      fontSize: 11,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _DesktopApp {
  final String label;
  final IconData icon;
  final Color color;
  final String id;
  final Widget child;

  const _DesktopApp(this.label, this.icon, this.color, this.id, this.child);
}

class _LaunchPad extends StatelessWidget {
  final VoidCallback onClose;
  final Function(String, String, IconData, Widget) onOpenApp;

  const _LaunchPad({required this.onClose, required this.onOpenApp});

  @override
  Widget build(BuildContext context) {
    final apps = [
      _LaunchApp('Terminal', Icons.terminal, Colors.teal, 'terminal', const TerminalApp()),
      _LaunchApp('File Manager', Icons.folder, Colors.blue, 'files', const FileManagerApp()),
      _LaunchApp('System Monitor', Icons.monitor, Colors.green, 'monitor', const SystemMonitorApp()),
      _LaunchApp('Settings', Icons.settings, Colors.grey, 'settings', const SettingsApp()),
      _LaunchApp('Text Editor', Icons.edit_document, Colors.orange, 'editor', const TextEditorApp()),
      _LaunchApp('Package Manager', Icons.inventory_2, Colors.purple, 'packages', const PackageManagerApp()),
      _LaunchApp('Network Manager', Icons.wifi, Colors.cyan, 'network', const NetworkManagerApp()),
      _LaunchApp('Calendar', Icons.calendar_today, Colors.indigo, 'calendar', const CalendarApp()),
      _LaunchApp('Calculator', Icons.calculate, Colors.blueGrey, 'calculator', const CalculatorApp()),
      _LaunchApp('Quantum Simulator', Icons.blur_circular, Colors.deepPurple, 'quantum', const QuantumSimApp()),
      _LaunchApp('Security', Icons.shield, Colors.red, 'security', const SecurityApp()),
      _LaunchApp('Boot Manager', Icons.power_settings_new, Colors.amber, 'boot', const BootManagerApp()),
      _LaunchApp('Games', Icons.sports_esports, Colors.pink, 'games', const GamesApp()),
      _LaunchApp('Documentation', Icons.menu_book, Colors.brown, 'docs', const DocsApp()),
    ];

    return GestureDetector(
      onTap: onClose,
      child: Container(
        color: Colors.black.withValues(alpha: 0.6),
        child: Center(
          child: GestureDetector(
            onTap: () {},
            child: Container(
              width: MediaQuery.of(context).size.width * 0.8,
              height: MediaQuery.of(context).size.height * 0.7,
              padding: const EdgeInsets.all(32),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.95),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Column(
                children: [
                  Text(
                    'LaunchPad',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 24),
                  Expanded(
                    child: GridView.builder(
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 5,
                        mainAxisSpacing: 24,
                        crossAxisSpacing: 24,
                        childAspectRatio: 0.8,
                      ),
                      itemCount: apps.length,
                      itemBuilder: (context, index) {
                        final app = apps[index];
                        return GestureDetector(
                          onTap: () => onOpenApp(app.id, app.label, app.icon, app.child),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                width: 72,
                                height: 72,
                                decoration: BoxDecoration(
                                  color: app.color.withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Icon(
                                  app.icon,
                                  size: 36,
                                  color: app.color,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                app.label,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Theme.of(context).colorScheme.onSurface,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ).animate().scale(begin: const Offset(0.8, 0.8), end: const Offset(1, 1)),
        ),
      ),
    ).animate().fadeIn(duration: 200.ms);
  }
}

class _LaunchApp {
  final String label;
  final IconData icon;
  final Color color;
  final String id;
  final Widget child;

  const _LaunchApp(this.label, this.icon, this.color, this.id, this.child);
}
