import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
import '../apps/browser_app.dart';
import '../apps/antivirus_app.dart';
import '../apps/power_governor_app.dart';

class DesktopShell extends StatefulWidget {
  const DesktopShell({super.key});

  @override
  State<DesktopShell> createState() => _DesktopShellState();
}

class _DesktopShellState extends State<DesktopShell> {
  String _currentTime = '';
  String _currentDate = '';
  Timer? _timer;
  bool _showLaunchPad = false;
  final FocusNode _keyboardFocusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _updateTime();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) _updateTime();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _keyboardFocusNode.dispose();
    super.dispose();
  }

  void _updateTime() {
    final now = DateTime.now();
    final timeStr = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
    final dateStr = '${_weekdayName(now.weekday)}, ${_monthName(now.month)} ${now.day}';
    if (timeStr != _currentTime || dateStr != _currentDate) {
      setState(() {
        _currentTime = timeStr;
        _currentDate = dateStr;
      });
    }
  }

  String _weekdayName(int day) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return days[day - 1];
  }

  String _monthName(int month) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[month - 1];
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

    return KeyboardListener(
      focusNode: _keyboardFocusNode,
      autofocus: true,
      onKeyEvent: (event) {
        if (event is KeyDownEvent) {
          if (event.logicalKey == LogicalKeyboardKey.keyK &&
              (HardwareKeyboard.instance.isControlPressed || HardwareKeyboard.instance.isMetaPressed)) {
            appState.toggleSearch();
          } else if (event.logicalKey == LogicalKeyboardKey.escape) {
            if (appState.isSearchOpen) appState.toggleSearch(show: false);
            if (appState.isControlCenterOpen) appState.toggleControlCenter(show: false);
            if (appState.isNotificationTrayOpen) appState.toggleNotificationTray(show: false);
            if (_showLaunchPad) setState(() => _showLaunchPad = false);
          }
        }
      },
      child: Scaffold(
        body: DesktopBackground(
          child: Stack(
            children: [
              // Top Menu Bar
              _MenuBar(
                currentTime: _currentTime,
                currentDate: _currentDate,
                onToggleLaunchPad: () => setState(() => _showLaunchPad = !_showLaunchPad),
                onToggleTheme: () => themeProvider.toggleTheme(),
                onOpenApp: _openApp,
              ),

              // Desktop Grid Workspace with Open Windows
              Positioned.fill(
                top: 36,
                bottom: 86,
                child: Stack(
                  children: [
                    // Desktop Grid App Icons
                    Positioned.fill(
                      child: _DesktopGrid(onOpenApp: _openApp),
                    ),

                    // Open Windows Stack
                    ...appState.windows
                        .map((w) => DraggableWindow(key: ValueKey(w.id), window: w)),

                    // Drag-to-Edge Window Snap Preview Overlay
                    if (appState.snapPreviewRect != null)
                      Positioned.fromRect(
                        rect: appState.snapPreviewRect!,
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 150),
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: Theme.of(context).colorScheme.primary,
                              width: 2,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),

              // Unified Super Dock (Integrates Taskbar Tabs & Minimization)
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: Dock(onOpenApp: _openApp),
              ),

              // Real Display Brightness Screen Dimmer Overlay
              if (appState.brightness < 1.0)
                Positioned.fill(
                  child: IgnorePointer(
                    child: Container(
                      color: Colors.black.withValues(alpha: (1.0 - appState.brightness) * 0.75),
                    ),
                  ),
                ),

              // Control Center Popover Modal
              if (appState.isControlCenterOpen)
                Positioned(
                  top: 40,
                  right: 12,
                  child: _ControlCenterPopover(onOpenApp: _openApp),
                ),

              // Notification Center Popover Modal
              if (appState.isNotificationTrayOpen)
                Positioned(
                  top: 40,
                  right: 12,
                  child: const _NotificationTrayPopover(),
                ),

              // Global Spotlight / Search Palette Modal
              if (appState.isSearchOpen)
                _GlobalSearchModal(onOpenApp: _openApp),

              // Fullscreen LaunchPad Overlay
              if (_showLaunchPad)
                _LaunchPad(
                  onClose: () => setState(() => _showLaunchPad = false),
                  onOpenApp: _openApp,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MenuBar extends StatelessWidget {
  final String currentTime;
  final String currentDate;
  final VoidCallback onToggleLaunchPad;
  final VoidCallback onToggleTheme;
  final Function(String id, String title, IconData icon, Widget child) onOpenApp;

  const _MenuBar({
    required this.currentTime,
    required this.currentDate,
    required this.onToggleLaunchPad,
    required this.onToggleTheme,
    required this.onOpenApp,
  });

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final colorScheme = Theme.of(context).colorScheme;

    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: Container(
        height: 36,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.9),
          border: Border(
            bottom: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: 0.3)),
          ),
        ),
        child: Row(
          children: [
            // UmerOS Logo Dropdown Menu
            PopupMenuButton<String>(
              tooltip: 'UmerOS System Menu',
              offset: const Offset(0, 36),
              icon: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.computer, size: 18, color: colorScheme.primary),
                  const SizedBox(width: 4),
                  Text(
                    'UmerOS',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                      color: colorScheme.primary,
                    ),
                  ),
                ],
              ),
              onSelected: (value) {
                if (value == 'settings') {
                  onOpenApp('settings', 'Settings', Icons.tune, const SettingsApp());
                } else if (value == 'power') {
                  onOpenApp('power', 'Power & Governor', Icons.bolt, const PowerGovernorApp());
                } else if (value == 'launchpad') {
                  onToggleLaunchPad();
                } else if (value == 'about') {
                  onOpenApp('settings', 'About UmerOS', Icons.info_outline, const SettingsApp());
                }
              },
              itemBuilder: (context) => [
                const PopupMenuItem(
                  value: 'about',
                  child: Row(children: [Icon(Icons.info_outline, size: 18), SizedBox(width: 8), Text('About UmerOS')]),
                ),
                const PopupMenuItem(
                  value: 'launchpad',
                  child: Row(children: [Icon(Icons.grid_view, size: 18), SizedBox(width: 8), Text('LaunchPad')]),
                ),
                const PopupMenuItem(
                  value: 'power',
                  child: Row(children: [Icon(Icons.bolt, size: 18), SizedBox(width: 8), Text('CPUIdle & Governor')]),
                ),
                const PopupMenuItem(
                  value: 'settings',
                  child: Row(children: [Icon(Icons.tune, size: 18), SizedBox(width: 8), Text('System Settings...')]),
                ),
              ],
            ),

            const SizedBox(width: 4),

            // Top Menu Items (Scrollable if narrow)
            Expanded(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _MenuBarItem(label: 'Files', onTap: () => onOpenApp('files', 'File Manager', Icons.folder, const FileManagerApp())),
                    _MenuBarItem(label: 'Terminal', onTap: () => onOpenApp('terminal', 'Terminal', Icons.terminal, const TerminalApp())),
                    _MenuBarItem(label: 'Monitor', onTap: () => onOpenApp('monitor', 'System Monitor', Icons.monitor_heart, const SystemMonitorApp())),
                    _MenuBarItem(label: 'Power', onTap: () => onOpenApp('power', 'Power & Governor', Icons.bolt, const PowerGovernorApp())),
                    _MenuBarItem(label: 'Docs', onTap: () => onOpenApp('docs', 'Documentation', Icons.menu_book, const DocsApp())),
                  ],
                ),
              ),
            ),

            // Spotlight Search Trigger
            IconButton(
              icon: const Icon(Icons.search, size: 18),
              tooltip: 'Search Apps & Commands (Ctrl+K)',
              onPressed: () => appState.toggleSearch(),
            ),

            // Theme Toggle Button
            IconButton(
              icon: Icon(
                Theme.of(context).brightness == Brightness.dark ? Icons.light_mode : Icons.dark_mode,
                size: 18,
              ),
              tooltip: 'Toggle Theme Mode',
              onPressed: onToggleTheme,
            ),

            // Control Center Trigger
            IconButton(
              icon: Icon(
                Icons.tune,
                size: 18,
                color: appState.isControlCenterOpen ? colorScheme.primary : null,
              ),
              tooltip: 'Control Center',
              onPressed: () => appState.toggleControlCenter(),
            ),

            // Notifications Trigger
            Stack(
              alignment: Alignment.center,
              children: [
                IconButton(
                  icon: Icon(
                    Icons.notifications_outlined,
                    size: 18,
                    color: appState.isNotificationTrayOpen ? colorScheme.primary : null,
                  ),
                  tooltip: 'Notification Center',
                  onPressed: () => appState.toggleNotificationTray(),
                ),
                if (appState.unreadNotificationCount > 0)
                  Positioned(
                    top: 6,
                    right: 6,
                    child: Container(
                      padding: const EdgeInsets.all(3),
                      decoration: const BoxDecoration(
                        color: Colors.redAccent,
                        shape: BoxShape.circle,
                      ),
                      child: Text(
                        '${appState.unreadNotificationCount}',
                        style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
              ],
            ),

            const SizedBox(width: 8),

            // Date & Time Status
            MouseRegion(
              cursor: SystemMouseCursors.click,
              child: GestureDetector(
                onTap: () => onOpenApp('calendar', 'Calendar', Icons.calendar_month, const CalendarApp()),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHigh.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    children: [
                      Text(
                        currentDate,
                        style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        currentTime,
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: colorScheme.onSurface),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MenuBarItem extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _MenuBarItem({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: InkWell(
        borderRadius: BorderRadius.circular(6),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Text(
            label,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Theme.of(context).colorScheme.onSurface),
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
      _DesktopApp('Browser', Icons.language, Colors.blue, 'browser', const BrowserApp()),
      _DesktopApp('Terminal', Icons.terminal, Colors.teal, 'terminal', const TerminalApp()),
      _DesktopApp('Files', Icons.folder, Colors.amber.shade700, 'files', const FileManagerApp()),
      _DesktopApp('Monitor', Icons.monitor_heart, Colors.green, 'monitor', const SystemMonitorApp()),
      _DesktopApp('Power & Idle', Icons.bolt, Colors.amber, 'power', const PowerGovernorApp()),
      _DesktopApp('Settings', Icons.tune, Colors.blueGrey, 'settings', const SettingsApp()),
      _DesktopApp('Editor', Icons.edit_note, Colors.orange, 'editor', const TextEditorApp()),
      _DesktopApp('Packages', Icons.inventory_2, Colors.purple, 'packages', const PackageManagerApp()),
      _DesktopApp('Network', Icons.wifi, Colors.cyan, 'network', const NetworkManagerApp()),
      _DesktopApp('Quantum', Icons.blur_circular, Colors.indigo, 'quantum', const QuantumSimApp()),
      _DesktopApp('Security', Icons.shield, Colors.redAccent, 'security', const SecurityApp()),
      _DesktopApp('Antivirus', Icons.health_and_safety, Colors.lightGreen, 'antivirus', const AntivirusApp()),
      _DesktopApp('Boot', Icons.power_settings_new, Colors.amber, 'boot', const BootManagerApp()),
      _DesktopApp('Games', Icons.sports_esports, Colors.pink, 'games', const GamesApp()),
      _DesktopApp('Docs', Icons.menu_book, Colors.deepOrange, 'docs', const DocsApp()),
    ];

    return Padding(
      padding: const EdgeInsets.all(28),
      child: Wrap(
        spacing: 28,
        runSpacing: 28,
        children: apps.map((app) {
          return SizedBox(
            width: 86,
            child: Draggable<String>(
              data: app.id,
              feedback: Material(
                color: Colors.transparent,
                child: Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: app.color.withValues(alpha: 0.8),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Icon(app.icon, size: 34, color: Colors.white),
                ),
              ),
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: () => onOpenApp(app.id, app.label, app.icon, app.child),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 64,
                        height: 64,
                        decoration: BoxDecoration(
                          color: app.color.withValues(alpha: 0.18),
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: app.color.withValues(alpha: 0.3)),
                          boxShadow: [
                            BoxShadow(
                              color: app.color.withValues(alpha: 0.15),
                              blurRadius: 12,
                              spreadRadius: 1,
                            ),
                          ],
                        ),
                        child: Icon(app.icon, size: 34, color: app.color),
                      ).animate().scale(begin: const Offset(0.92, 0.92), end: const Offset(1, 1), duration: 200.ms),
                      const SizedBox(height: 8),
                      Text(
                        app.label,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: Theme.of(context).colorScheme.onSurface,
                          shadows: const [Shadow(color: Colors.black, blurRadius: 4)],
                        ),
                        textAlign: TextAlign.center,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
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

// Material 3 Control Center Popover Widget
class _ControlCenterPopover extends StatefulWidget {
  final Function(String id, String title, IconData icon, Widget child) onOpenApp;

  const _ControlCenterPopover({required this.onOpenApp});

  @override
  State<_ControlCenterPopover> createState() => _ControlCenterPopoverState();
}

class _ControlCenterPopoverState extends State<_ControlCenterPopover> {
  final TextEditingController _customWallpaperController = TextEditingController();

  @override
  void dispose() {
    _customWallpaperController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final themeProvider = context.watch<ThemeProvider>();
    final colorScheme = Theme.of(context).colorScheme;

    return Material(
      color: Colors.transparent,
      child: Container(
        width: 350,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: colorScheme.outlineVariant.withValues(alpha: 0.4)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.35),
              blurRadius: 28,
              spreadRadius: 2,
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Title Header
            Row(
              children: [
                Icon(Icons.tune, size: 20, color: colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Control Center',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: colorScheme.onSurface),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () => appState.toggleControlCenter(show: false),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Toggles Grid
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                _QuickToggleTile(
                  icon: Icons.wifi,
                  label: 'Wi-Fi',
                  subtitle: appState.wifiEnabled ? 'Connected' : 'Off',
                  isActive: appState.wifiEnabled,
                  onTap: () => appState.toggleWifi(),
                ),
                _QuickToggleTile(
                  icon: Icons.bluetooth,
                  label: 'Bluetooth',
                  subtitle: appState.bluetoothEnabled ? 'On' : 'Off',
                  isActive: appState.bluetoothEnabled,
                  onTap: () => appState.toggleBluetooth(),
                ),
                _QuickToggleTile(
                  icon: Theme.of(context).brightness == Brightness.dark ? Icons.dark_mode : Icons.light_mode,
                  label: 'Dark Mode',
                  subtitle: Theme.of(context).brightness == Brightness.dark ? 'Enabled' : 'Light',
                  isActive: Theme.of(context).brightness == Brightness.dark,
                  onTap: () => themeProvider.toggleTheme(),
                ),
                _QuickToggleTile(
                  icon: Icons.speed,
                  label: 'Performance',
                  subtitle: appState.performanceMode ? 'High' : 'Balanced',
                  isActive: appState.performanceMode,
                  onTap: () => appState.togglePerformanceMode(),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Sliders: Volume & Brightness
            Text('System Volume: ${(appState.volume * 100).round()}%', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colorScheme.onSurfaceVariant)),
            Row(
              children: [
                Icon(Icons.volume_down, size: 18, color: colorScheme.onSurfaceVariant),
                Expanded(
                  child: Slider(
                    value: appState.volume,
                    onChanged: (val) => appState.setVolume(val),
                  ),
                ),
                Icon(Icons.volume_up, size: 18, color: colorScheme.primary),
              ],
            ),

            Text('Display Brightness: ${(appState.brightness * 100).round()}%', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colorScheme.onSurfaceVariant)),
            Row(
              children: [
                Icon(Icons.brightness_low, size: 18, color: colorScheme.onSurfaceVariant),
                Expanded(
                  child: Slider(
                    value: appState.brightness,
                    onChanged: (val) => appState.setBrightness(val),
                  ),
                ),
                Icon(Icons.brightness_high, size: 18, color: colorScheme.primary),
              ],
            ),

            const Divider(),
            const SizedBox(height: 8),

            // Wallpaper Selector & Custom Background Image Input
            Text('Wallpaper Preset', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colorScheme.onSurfaceVariant)),
            const SizedBox(height: 8),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: WallpaperPreset.values.map((preset) {
                  final isSelected = themeProvider.wallpaper == preset;
                  return Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: FilterChip(
                      selected: isSelected,
                      label: Text(preset.name),
                      onSelected: (_) => themeProvider.setWallpaper(preset),
                    ),
                  );
                }).toList(),
              ),
            ),
            const SizedBox(height: 10),

            // Custom Background Image Input
            TextField(
              controller: _customWallpaperController,
              decoration: InputDecoration(
                hintText: 'Enter custom image path or URL...',
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.image, size: 18),
                  onPressed: () {
                    if (_customWallpaperController.text.isNotEmpty) {
                      themeProvider.setCustomImagePath(_customWallpaperController.text);
                      appState.addNotification('Wallpaper', 'Custom background image applied', Icons.wallpaper);
                    }
                  },
                ),
                border: const OutlineInputBorder(),
              ),
            ),
          ],
        ),
      ),
    ).animate().fadeIn(duration: 150.ms).slideY(begin: -0.05, end: 0);
  }
}

class _QuickToggleTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final bool isActive;
  final VoidCallback onTap;

  const _QuickToggleTile({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        width: 148,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: isActive ? colorScheme.primaryContainer : colorScheme.surfaceContainer,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isActive ? colorScheme.primary : Colors.transparent,
            width: 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: isActive ? colorScheme.primary : colorScheme.surfaceContainerHighest,
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                size: 16,
                color: isActive ? colorScheme.onPrimary : colorScheme.onSurface,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: isActive ? colorScheme.onPrimaryContainer : colorScheme.onSurface,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 10,
                      color: isActive ? colorScheme.onPrimaryContainer.withValues(alpha: 0.8) : colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// Notification Center Popover
class _NotificationTrayPopover extends StatelessWidget {
  const _NotificationTrayPopover();

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final colorScheme = Theme.of(context).colorScheme;

    return Material(
      color: Colors.transparent,
      child: Container(
        width: 360,
        constraints: const BoxConstraints(maxHeight: 460),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: colorScheme.outlineVariant.withValues(alpha: 0.4)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.35),
              blurRadius: 28,
              spreadRadius: 2,
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.notifications, size: 20, color: colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Notifications',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: colorScheme.onSurface),
                ),
                const Spacer(),
                if (appState.notifications.isNotEmpty)
                  TextButton(
                    onPressed: () => appState.clearAllNotifications(),
                    child: const Text('Clear All'),
                  ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () => appState.toggleNotificationTray(show: false),
                ),
              ],
            ),
            const SizedBox(height: 10),

            if (appState.notifications.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 32),
                child: Center(
                  child: Column(
                    children: [
                      Icon(Icons.notifications_off_outlined, size: 42, color: colorScheme.onSurfaceVariant),
                      const SizedBox(height: 8),
                      Text('No new notifications', style: TextStyle(color: colorScheme.onSurfaceVariant)),
                    ],
                  ),
                ),
              )
            else
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: appState.notifications.length,
                  itemBuilder: (context, index) {
                    final item = appState.notifications[index];
                    return Card(
                      color: colorScheme.surfaceContainer,
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: item.color.withValues(alpha: 0.2),
                          child: Icon(item.icon, color: item.color, size: 18),
                        ),
                        title: Text(item.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                        subtitle: Text(item.message, style: const TextStyle(fontSize: 12)),
                        trailing: IconButton(
                          icon: const Icon(Icons.close, size: 16),
                          onPressed: () => appState.removeNotification(item.id),
                        ),
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    ).animate().fadeIn(duration: 150.ms).slideY(begin: -0.05, end: 0);
  }
}

// Global Spotlight Search Palette
class _GlobalSearchModal extends StatefulWidget {
  final Function(String id, String title, IconData icon, Widget child) onOpenApp;

  const _GlobalSearchModal({required this.onOpenApp});

  @override
  State<_GlobalSearchModal> createState() => _GlobalSearchModalState();
}

class _GlobalSearchModalState extends State<_GlobalSearchModal> {
  final TextEditingController _controller = TextEditingController();
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final colorScheme = Theme.of(context).colorScheme;

    final allApps = [
      _DesktopApp('Browser', Icons.language, Colors.blue, 'browser', const BrowserApp()),
      _DesktopApp('Terminal', Icons.terminal, Colors.teal, 'terminal', const TerminalApp()),
      _DesktopApp('File Manager', Icons.folder, Colors.amber.shade700, 'files', const FileManagerApp()),
      _DesktopApp('System Monitor', Icons.monitor_heart, Colors.green, 'monitor', const SystemMonitorApp()),
      _DesktopApp('Power & Governor', Icons.bolt, Colors.amber, 'power', const PowerGovernorApp()),
      _DesktopApp('Settings', Icons.tune, Colors.blueGrey, 'settings', const SettingsApp()),
      _DesktopApp('Text Editor', Icons.edit_note, Colors.orange, 'editor', const TextEditorApp()),
      _DesktopApp('Package Manager', Icons.inventory_2, Colors.purple, 'packages', const PackageManagerApp()),
      _DesktopApp('Network Manager', Icons.wifi, Colors.cyan, 'network', const NetworkManagerApp()),
      _DesktopApp('Calendar', Icons.calendar_month, Colors.indigo, 'calendar', const CalendarApp()),
      _DesktopApp('Calculator', Icons.calculate, Colors.blueGrey, 'calculator', const CalculatorApp()),
      _DesktopApp('Quantum Simulator', Icons.blur_circular, Colors.deepPurple, 'quantum', const QuantumSimApp()),
      _DesktopApp('Security Manager', Icons.shield, Colors.redAccent, 'security', const SecurityApp()),
      _DesktopApp('Antivirus', Icons.health_and_safety, Colors.lightGreen, 'antivirus', const AntivirusApp()),
      _DesktopApp('Boot Manager', Icons.power_settings_new, Colors.amber, 'boot', const BootManagerApp()),
      _DesktopApp('Games', Icons.sports_esports, Colors.pink, 'games', const GamesApp()),
      _DesktopApp('Documentation', Icons.menu_book, Colors.deepOrange, 'docs', const DocsApp()),
    ];

    final filtered = allApps
        .where((a) => a.label.toLowerCase().contains(_query.toLowerCase()))
        .toList();

    return GestureDetector(
      onTap: () => appState.toggleSearch(show: false),
      child: Container(
        color: Colors.black.withValues(alpha: 0.5),
        child: Align(
          alignment: const Alignment(0, -0.4),
          child: GestureDetector(
            onTap: () {},
            child: Container(
              width: 580,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHigh,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: colorScheme.outlineVariant.withValues(alpha: 0.4)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.4),
                    blurRadius: 36,
                    spreadRadius: 4,
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: _controller,
                    autofocus: true,
                    decoration: InputDecoration(
                      hintText: 'Search UmerOS apps, commands & tools...',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: _query.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear),
                              onPressed: () {
                                _controller.clear();
                                setState(() => _query = '');
                              },
                            )
                          : null,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                    onChanged: (val) => setState(() => _query = val),
                  ),
                  const SizedBox(height: 12),

                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 320),
                    child: filtered.isEmpty
                        ? Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text('No matching apps found', style: TextStyle(color: colorScheme.onSurfaceVariant)),
                          )
                        : ListView.builder(
                            shrinkWrap: true,
                            itemCount: filtered.length,
                            itemBuilder: (context, index) {
                              final app = filtered[index];
                              return ListTile(
                                leading: CircleAvatar(
                                  backgroundColor: app.color.withValues(alpha: 0.2),
                                  child: Icon(app.icon, color: app.color),
                                ),
                                title: Text(app.label, style: const TextStyle(fontWeight: FontWeight.bold)),
                                subtitle: Text('Application • ${app.id}'),
                                trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                                onTap: () {
                                  appState.toggleSearch(show: false);
                                  widget.onOpenApp(app.id, app.label, app.icon, app.child);
                                },
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
          ).animate().scale(begin: const Offset(0.9, 0.9), end: const Offset(1, 1), duration: 150.ms),
        ),
      ),
    ).animate().fadeIn(duration: 150.ms);
  }
}

// Fullscreen LaunchPad Overlay
class _LaunchPad extends StatelessWidget {
  final VoidCallback onClose;
  final Function(String, String, IconData, Widget) onOpenApp;

  const _LaunchPad({required this.onClose, required this.onOpenApp});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    final apps = [
      _LaunchApp('Browser', Icons.language, Colors.blue, 'browser', const BrowserApp()),
      _LaunchApp('Terminal', Icons.terminal, Colors.teal, 'terminal', const TerminalApp()),
      _LaunchApp('File Manager', Icons.folder, Colors.amber.shade700, 'files', const FileManagerApp()),
      _LaunchApp('System Monitor', Icons.monitor_heart, Colors.green, 'monitor', const SystemMonitorApp()),
      _LaunchApp('Power & Governor', Icons.bolt, Colors.amber, 'power', const PowerGovernorApp()),
      _LaunchApp('Settings', Icons.tune, Colors.blueGrey, 'settings', const SettingsApp()),
      _LaunchApp('Text Editor', Icons.edit_note, Colors.orange, 'editor', const TextEditorApp()),
      _LaunchApp('Package Manager', Icons.inventory_2, Colors.purple, 'packages', const PackageManagerApp()),
      _LaunchApp('Network Manager', Icons.wifi, Colors.cyan, 'network', const NetworkManagerApp()),
      _LaunchApp('Calendar', Icons.calendar_month, Colors.indigo, 'calendar', const CalendarApp()),
      _LaunchApp('Calculator', Icons.calculate, Colors.blueGrey, 'calculator', const CalculatorApp()),
      _LaunchApp('Quantum Simulator', Icons.blur_circular, Colors.deepPurple, 'quantum', const QuantumSimApp()),
      _LaunchApp('Security', Icons.shield, Colors.redAccent, 'security', const SecurityApp()),
      _LaunchApp('Antivirus', Icons.health_and_safety, Colors.lightGreen, 'antivirus', const AntivirusApp()),
      _LaunchApp('Boot Manager', Icons.power_settings_new, Colors.amber, 'boot', const BootManagerApp()),
      _LaunchApp('Games', Icons.sports_esports, Colors.pink, 'games', const GamesApp()),
      _LaunchApp('Documentation', Icons.menu_book, Colors.deepOrange, 'docs', const DocsApp()),
    ];

    return GestureDetector(
      onTap: onClose,
      child: Container(
        color: Colors.black.withValues(alpha: 0.65),
        child: Center(
          child: GestureDetector(
            onTap: () {},
            child: Container(
              width: MediaQuery.of(context).size.width * 0.82,
              height: MediaQuery.of(context).size.height * 0.76,
              padding: const EdgeInsets.all(32),
              decoration: BoxDecoration(
                color: colorScheme.surface.withValues(alpha: 0.95),
                borderRadius: BorderRadius.circular(28),
                border: Border.all(color: colorScheme.outlineVariant.withValues(alpha: 0.4)),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.grid_view, size: 28, color: colorScheme.primary),
                      const SizedBox(width: 10),
                      Text(
                        'LaunchPad',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  Expanded(
                    child: GridView.builder(
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 6,
                        mainAxisSpacing: 24,
                        crossAxisSpacing: 24,
                        childAspectRatio: 0.85,
                      ),
                      itemCount: apps.length,
                      itemBuilder: (context, index) {
                        final app = apps[index];
                        return Draggable<String>(
                          data: app.id,
                          feedback: Material(
                            color: Colors.transparent,
                            child: Container(
                              width: 72,
                              height: 72,
                              decoration: BoxDecoration(
                                color: app.color.withValues(alpha: 0.8),
                                borderRadius: BorderRadius.circular(22),
                              ),
                              child: Icon(app.icon, size: 38, color: Colors.white),
                            ),
                          ),
                          child: MouseRegion(
                            cursor: SystemMouseCursors.click,
                            child: GestureDetector(
                              onTap: () => onOpenApp(app.id, app.label, app.icon, app.child),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Container(
                                    width: 72,
                                    height: 72,
                                    decoration: BoxDecoration(
                                      color: app.color.withValues(alpha: 0.18),
                                      borderRadius: BorderRadius.circular(22),
                                      border: Border.all(color: app.color.withValues(alpha: 0.3)),
                                    ),
                                    child: Icon(app.icon, size: 38, color: app.color),
                                  ),
                                  const SizedBox(height: 10),
                                  Text(
                                    app.label,
                                    style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w500,
                                      color: colorScheme.onSurface,
                                    ),
                                    textAlign: TextAlign.center,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ).animate().scale(begin: const Offset(0.85, 0.85), end: const Offset(1, 1), duration: 200.ms),
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
