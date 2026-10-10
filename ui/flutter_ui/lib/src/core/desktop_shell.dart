import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'app_state.dart';
import 'app_registry.dart';
import 'theme_provider.dart';
import '../widgets/dock.dart';
import '../widgets/draggable_window.dart';
import '../widgets/auto_adjust_box.dart';
import '../services/material3_theme.dart';
import '../../services/clipboard_manager.dart';
import 'package:file_picker/file_picker.dart';

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
    final timeStr =
        '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
    final dateStr =
        '${_weekdayName(now.weekday)}, ${_monthName(now.month)} ${now.day}';
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
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return months[month - 1];
  }

  /// Opens an app from the central registry (single source of truth).
  void _openApp(AppDefinition app) {
    context.read<AppState>().openWindow(
          id: app.id,
          title: app.title,
          icon: app.icon,
          child: app.builder(context),
        );
    if (_showLaunchPad) setState(() => _showLaunchPad = false);
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
          final isCtrlOrMeta = HardwareKeyboard.instance.isControlPressed ||
              HardwareKeyboard.instance.isMetaPressed;
          final isShift = HardwareKeyboard.instance.isShiftPressed;

          if (event.logicalKey == LogicalKeyboardKey.keyK && isCtrlOrMeta) {
            appState.toggleSearch();
          } else if (event.logicalKey == LogicalKeyboardKey.keyV &&
              isCtrlOrMeta &&
              isShift) {
            appState.toggleClipboard();
          } else if (event.logicalKey == LogicalKeyboardKey.keyN &&
              isCtrlOrMeta &&
              isShift) {
            appState.toggleScratchpad();
          } else if (isCtrlOrMeta && !isShift && event.logicalKey == LogicalKeyboardKey.digit1) {
            appState.switchWorkspace(1);
          } else if (isCtrlOrMeta && !isShift && event.logicalKey == LogicalKeyboardKey.digit2) {
            appState.switchWorkspace(2);
          } else if (isCtrlOrMeta && !isShift && event.logicalKey == LogicalKeyboardKey.digit3) {
            appState.switchWorkspace(3);
          } else if (isCtrlOrMeta && !isShift && event.logicalKey == LogicalKeyboardKey.digit4) {
            appState.switchWorkspace(4);
          } else if (isCtrlOrMeta && !isShift && event.logicalKey == LogicalKeyboardKey.digit5) {
            appState.switchWorkspace(5);
          } else if (isCtrlOrMeta && !isShift && event.logicalKey == LogicalKeyboardKey.digit6) {
            appState.switchWorkspace(6);
          } else if (event.logicalKey == LogicalKeyboardKey.escape) {
            if (appState.isSearchOpen) appState.toggleSearch(show: false);
            if (appState.isControlCenterOpen) {
              appState.toggleControlCenter(show: false);
            }
            if (appState.isNotificationTrayOpen) {
              appState.toggleNotificationTray(show: false);
            }
            if (appState.isClipboardOpen) {
              appState.toggleClipboard(show: false);
            }
            if (appState.isScratchpadOpen) {
              appState.toggleScratchpad(show: false);
            }
            if (_showLaunchPad) setState(() => _showLaunchPad = false);
          }
        }
      },
      child: Scaffold(
        body: DesktopBackground(
          child: Stack(
            children: [
              // Top Menu Bar
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                child: _MenuBar(
                  currentTime: _currentTime,
                  currentDate: _currentDate,
                  onToggleLaunchPad: () =>
                      setState(() => _showLaunchPad = !_showLaunchPad),
                  onToggleTheme: () => themeProvider.toggleTheme(),
                  onOpenApp: _openApp,
                ),
              ),

              // Desktop Grid Workspace with Open Windows
              Positioned.fill(
                top: 36,
                bottom: 86,
                child: Stack(
                  children: [
                    // Desktop App Icons (from central registry)
                    Positioned.fill(child: _DesktopGrid(onOpenApp: _openApp)),

                    // Open Windows Stack (Filtered to Active Virtual Workspace)
                    ...appState.visibleWindows.map(
                      (w) => DraggableWindow(key: ValueKey(w.id), window: w),
                    ),

                    // Drag-to-Edge Window Snap Preview Overlay
                    if (appState.snapPreviewRect != null)
                      Positioned.fromRect(
                        rect: appState.snapPreviewRect!,
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 150),
                          decoration: BoxDecoration(
                            color: Theme.of(context)
                                .colorScheme
                                .primary
                                .withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color:
                                  Theme.of(context).colorScheme.primary,
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
                      color: Colors.black.withValues(
                        alpha: (1.0 - appState.brightness) * 0.75,
                      ),
                    ),
                  ),
                ),

              // Universal Clipboard History Popover Modal
              if (appState.isClipboardOpen)
                const Positioned(
                  top: 40,
                  right: 90,
                  child: _ClipboardHistoryModal(),
                ),

              // Quick Notes / Scratchpad Overlay Modal
              if (appState.isScratchpadOpen)
                const Positioned(
                  top: 40,
                  right: 50,
                  child: _QuickScratchpadModal(),
                ),

              // Control Center Popover Modal
              if (appState.isControlCenterOpen)
                Positioned(
                  top: 40,
                  right: 12,
                  child: _ControlCenterPopover(),
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
  final OpenAppFn onOpenApp;

  const _MenuBar({
    required this.currentTime,
    required this.currentDate,
    required this.onToggleLaunchPad,
    required this.onToggleTheme,
    required this.onOpenApp,
  });

  Widget _entry(BuildContext context, String id) {
    final app = AppRegistry.byId(id)!;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: Semantics(
        label: app.title,
        button: true,
        child: InkWell(
        borderRadius: BorderRadius.circular(6),
        onTap: () => onOpenApp(app),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Text(
            app.title,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: M3Theme.textColor(context),
            ),
          ),
        ),
      ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      height: 36,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.9),
        border: Border(
          bottom: BorderSide(
            color: colorScheme.outlineVariant.withValues(alpha: 0.3),
          ),
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
              switch (value) {
                case 'settings':
                case 'about':
                  onOpenApp(AppRegistry.byId('settings')!);
                case 'power':
                  onOpenApp(AppRegistry.byId('power')!);
                case 'launchpad':
                  onToggleLaunchPad();
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'about',
                child: Row(children: [
                  Icon(Icons.info_outline, size: 18),
                  SizedBox(width: 8),
                  Text('About UmerOS'),
                ]),
              ),
              const PopupMenuItem(
                value: 'launchpad',
                child: Row(children: [
                  Icon(Icons.grid_view, size: 18),
                  SizedBox(width: 8),
                  Text('LaunchPad'),
                ]),
              ),
              const PopupMenuItem(
                value: 'power',
                child: Row(children: [
                  Icon(Icons.bolt, size: 18),
                  SizedBox(width: 8),
                  Text('Power & Performance'),
                ]),
              ),
              const PopupMenuItem(
                value: 'settings',
                child: Row(children: [
                  Icon(Icons.tune, size: 18),
                  SizedBox(width: 8),
                  Text('System Settings...'),
                ]),
              ),
            ],
          ),

          const SizedBox(width: 8),

          // Virtual Workspaces Switcher (Multi-Desktop Spaces)
          Container(
            height: 24,
            padding: const EdgeInsets.symmetric(horizontal: 4),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHigh.withValues(alpha: 0.7),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: colorScheme.outlineVariant.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (int ws = 1; ws <= appState.totalWorkspaces; ws++)
                  InkWell(
                    borderRadius: BorderRadius.circular(10),
                    onTap: () => appState.switchWorkspace(ws),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 150),
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: appState.currentWorkspace == ws
                            ? colorScheme.primary
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '$ws',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: appState.currentWorkspace == ws
                              ? colorScheme.onPrimary
                              : colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ),
                if (appState.totalWorkspaces < 6)
                  InkWell(
                    borderRadius: BorderRadius.circular(10),
                    onTap: () => appState.addWorkspace(),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: Icon(
                        Icons.add,
                        size: 14,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
              ],
            ),
          ),

          const SizedBox(width: 4),

          // Top Menu Items (Scrollable if narrow) — registry-driven.
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final id in ['files', 'terminal', 'monitor', 'power', 'docs'])
                    _entry(context, id),
                ],
              ),
            ),
          ),

          // Universal Clipboard History Trigger (Ctrl+Shift+V)
          IconButton(
            icon: Icon(
              Icons.content_paste_rounded,
              size: 18,
              color: appState.isClipboardOpen ? colorScheme.primary : null,
            ),
            tooltip: 'Clipboard History (Ctrl+Shift+V)',
            onPressed: () => appState.toggleClipboard(),
          ),

          // Quick Scratchpad / Notes Trigger (Ctrl+Shift+N)
          IconButton(
            icon: Icon(
              Icons.sticky_note_2_outlined,
              size: 18,
              color: appState.isScratchpadOpen ? colorScheme.primary : null,
            ),
            tooltip: 'Quick Scratchpad (Ctrl+Shift+N)',
            onPressed: () => appState.toggleScratchpad(),
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
              Theme.of(context).brightness == Brightness.dark
                  ? Icons.light_mode
                  : Icons.dark_mode,
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
                  color: appState.isNotificationTrayOpen
                      ? colorScheme.primary
                      : null,
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
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 8,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
            ],
          ),

          const SizedBox(width: 8),

          // Date & Time Status
          MouseRegion(
            cursor: SystemMouseCursors.click,
            child: Semantics(
              label: 'Date and time — open Calendar',
              button: true,
              child: GestureDetector(
              onTap: () => onOpenApp(AppRegistry.byId('calendar')!),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHigh
                      .withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Row(
                  children: [
                    Text(
                      currentDate,
                      style: TextStyle(
                        fontSize: 12,
                        color: M3Theme.subtleTextColor(context),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      currentTime,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: M3Theme.textColor(context),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DesktopGrid extends StatelessWidget {
  final OpenAppFn onOpenApp;

  const _DesktopGrid({required this.onOpenApp});

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    final desktopItems = appState.desktopItems;
    final apps = AppRegistry.apps;

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.all(28),
      child: Wrap(
        spacing: 28,
        runSpacing: 28,
        children: [
          // Regular apps from AppRegistry
          ...apps.map((app) => _buildAppIcon(context, app)),
          // Desktop items (folders, files, etc.)
          ...desktopItems.map((item) => _buildDesktopItem(context, item, appState)),
        ],
      ),
    );
  }

  Widget _buildAppIcon(BuildContext context, AppDefinition app) {
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
          child: Semantics(
            label: app.title,
            button: true,
            child: GestureDetector(
              onTap: () => onOpenApp(app),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: app.color.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: app.color.withValues(alpha: 0.3),
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: app.color.withValues(alpha: 0.15),
                          blurRadius: 12,
                          spreadRadius: 1,
                        ),
                      ],
                    ),
                    child: Icon(app.icon, size: 34, color: app.color),
                  )
                      .animate()
                      .scale(
                        begin: const Offset(0.92, 0.92),
                        end: const Offset(1, 1),
                        duration: 200.ms,
                      ),
                  const SizedBox(height: 8),
                  Text(
                    app.title,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: Theme.of(context).colorScheme.onSurface,
                      shadows: const [
                        Shadow(color: Colors.black, blurRadius: 4),
                      ],
                    ),
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDesktopItem(BuildContext context, DesktopItemData item, AppState appState) {
    final itemColor = item.color ?? Colors.grey;
    return SizedBox(
      width: 86,
      child: Draggable<String>(
        data: 'desktop:${item.id}',
        feedback: Material(
          color: Colors.transparent,
          child: Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: itemColor.withValues(alpha: 0.8),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(item.icon, size: 34, color: Colors.white),
          ),
        ),
        child: MouseRegion(
          cursor: SystemMouseCursors.click,
          child: Semantics(
            label: item.name,
            button: true,
            child: GestureDetector(
              onTap: () {
                final appId = item.appId;
                if (appId != null) {
                  final app = AppRegistry.byId(appId);
                  if (app != null) {
                    onOpenApp(app);
                  }
                }
                // Folders/files: open with Files app
              },
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: itemColor.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: itemColor.withValues(alpha: 0.3),
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: itemColor.withValues(alpha: 0.15),
                          blurRadius: 12,
                          spreadRadius: 1,
                        ),
                      ],
                    ),
                    child: Icon(item.icon, size: 34, color: itemColor),
                  )
                      .animate()
                      .scale(
                        begin: const Offset(0.92, 0.92),
                        end: const Offset(1, 1),
                        duration: 200.ms,
                      ),
                  const SizedBox(height: 8),
                  Text(
                    item.name,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: Theme.of(context).colorScheme.onSurface,
                      shadows: const [
                        Shadow(color: Colors.black, blurRadius: 4),
                      ],
                    ),
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// Material 3 Control Center Popover Widget
class _ControlCenterPopover extends StatefulWidget {
  const _ControlCenterPopover();

  @override
  State<_ControlCenterPopover> createState() => _ControlCenterPopoverState();
}

class _ControlCenterPopoverState extends State<_ControlCenterPopover> {
  final TextEditingController _customWallpaperController =
      TextEditingController();

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
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height - 120,
        ),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: colorScheme.outlineVariant.withValues(alpha: 0.4),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.35),
              blurRadius: 28,
              spreadRadius: 2,
            ),
          ],
        ),
        child: AutoAdjustColumn(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Title Header
            Row(
              children: [
                Icon(Icons.tune, size: 20, color: colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Control Center',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
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
                  icon: Theme.of(context).brightness == Brightness.dark
                      ? Icons.dark_mode
                      : Icons.light_mode,
                  label: 'Dark Mode',
                  subtitle: Theme.of(context).brightness == Brightness.dark
                      ? 'Enabled'
                      : 'Light',
                  isActive: Theme.of(context).brightness == Brightness.dark,
                  onTap: () => themeProvider.toggleTheme(),
                ),
                _QuickToggleTile(
                  icon: Icons.speed,
                  label: 'Performance',
                  subtitle:
                      appState.performanceMode ? 'High' : 'Balanced',
                  isActive: appState.performanceMode,
                  onTap: () => appState.togglePerformanceMode(),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Sliders: Volume & Brightness
            Text(
              'System Volume: ${(appState.volume * 100).round()}%',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            Row(
              children: [
                Icon(Icons.volume_down,
                    size: 18, color: colorScheme.onSurfaceVariant),
                Expanded(
                  child: Slider(
                    value: appState.volume,
                    onChanged: (val) => appState.setVolume(val),
                  ),
                ),
                Icon(Icons.volume_up, size: 18, color: colorScheme.primary),
              ],
            ),

            Text(
              'Display Brightness: ${(appState.brightness * 100).round()}%',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            Row(
              children: [
                Icon(Icons.brightness_low,
                    size: 18, color: colorScheme.onSurfaceVariant),
                Expanded(
                  child: Slider(
                    value: appState.brightness,
                    onChanged: (val) => appState.setBrightness(val),
                  ),
                ),
                Icon(Icons.brightness_high,
                    size: 18, color: colorScheme.primary),
              ],
            ),

            const Divider(),
            const SizedBox(height: 8),

            // Wallpaper Selector & Custom Background Image Input
            Text(
              'Wallpaper Preset',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
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
                      label: Text(switch (preset) {
                        WallpaperPreset.quantumGradient => 'Quantum',
                        WallpaperPreset.deepSpace => 'Deep Space',
                        WallpaperPreset.auroraBoreal => 'Aurora',
                        WallpaperPreset.cyberpunkNeon => 'Neon',
                        WallpaperPreset.minimalMesh => 'Minimal',
                        WallpaperPreset.midnightSlate => 'Slate',
                        WallpaperPreset.customImage => 'Custom',
                      }),
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
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                suffixIcon: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.folder_open, size: 18),
                      tooltip: 'Browse image file',
                      onPressed: () async {
                        final result = await FilePicker.pickFiles(
                          type: FileType.custom,
                          allowedExtensions: ['jpg', 'jpeg', 'png', 'webp', 'bmp'],
                        );
                        final path = result.firstOrNull?.path;
                        if (path != null) {
                          _customWallpaperController.text = path;
                          themeProvider.setCustomImagePath(path);
                          appState.addNotification(
                            'Wallpaper',
                            'Custom background image applied',
                            Icons.wallpaper,
                          );
                        }
                      },
                    ),
                    IconButton(
                      icon: const Icon(Icons.check, size: 18),
                      tooltip: 'Apply custom wallpaper',
                      onPressed: () {
                        if (_customWallpaperController.text.isNotEmpty) {
                          themeProvider
                              .setCustomImagePath(_customWallpaperController.text);
                          appState.addNotification(
                            'Wallpaper',
                            'Custom background image applied',
                            Icons.wallpaper,
                          );
                        }
                      },
                    ),
                  ],
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

    return Semantics(
      label: label,
      button: true,
      child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        width: 148,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: isActive
              ? colorScheme.primaryContainer
              : colorScheme.surfaceContainer,
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
                color: isActive
                    ? colorScheme.primary
                    : colorScheme.surfaceContainerHighest,
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
                      color: isActive
                          ? colorScheme.onPrimaryContainer
                          : colorScheme.onSurface,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 10,
                      color: isActive
                          ? colorScheme.onPrimaryContainer
                              .withValues(alpha: 0.8)
                          : colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
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
          border: Border.all(
            color: colorScheme.outlineVariant.withValues(alpha: 0.4),
          ),
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
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
                ),
                const Spacer(),
                if (appState.notifications.isNotEmpty)
                  TextButton(
                    onPressed: () => appState.clearAllNotifications(),
                    child: const Text('Clear All'),
                  ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () =>
                      appState.toggleNotificationTray(show: false),
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
                      Icon(Icons.notifications_off_outlined,
                          size: 42, color: colorScheme.onSurfaceVariant),
                      const SizedBox(height: 8),
                      Text('No new notifications',
                          style: TextStyle(color: colorScheme.onSurfaceVariant)),
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
                      child: Material(
                        color: Colors.transparent,
                        child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: item.color.withValues(alpha: 0.2),
                          child: Icon(item.icon, color: item.color, size: 18),
                        ),
                        title: Text(item.title,
                            style: const TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 13)),
                        subtitle: Text(item.message,
                            style: const TextStyle(fontSize: 12)),
                        trailing: IconButton(
                          icon: const Icon(Icons.close, size: 16),
                          tooltip: 'Dismiss notification',
                          onPressed: () => appState.removeNotification(item.id),
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
    ).animate().fadeIn(duration: 150.ms).slideY(begin: -0.05, end: 0);
  }
}

// Global Spotlight Search Palette
class _GlobalSearchModal extends StatefulWidget {
  final OpenAppFn onOpenApp;

  const _GlobalSearchModal({required this.onOpenApp});

  @override
  State<_GlobalSearchModal> createState() => _GlobalSearchModalState();
}

class _GlobalSearchModalState extends State<_GlobalSearchModal> {
  final TextEditingController _controller = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final colorScheme = Theme.of(context).colorScheme;

    final allApps = AppRegistry.apps;

    final filtered = allApps
        .where((a) =>
            a.title.toLowerCase().contains(_query.toLowerCase()) ||
            a.description.toLowerCase().contains(_query.toLowerCase()))
        .toList();

    final mathResult = _evaluateMath(_query);

    final actionItems = <_SearchActionItem>[];
    final qLower = _query.toLowerCase().trim();
    if (qLower.isNotEmpty) {
      if ('theme dark light appearance mode'.contains(qLower) || qLower.contains('theme')) {
        actionItems.add(_SearchActionItem(
          title: 'Toggle Theme Appearance',
          subtitle: 'Switch between Dark and Light mode',
          icon: Icons.palette_outlined,
          color: Colors.purpleAccent,
          onTap: () {
            appState.toggleSearch(show: false);
            context.read<ThemeProvider>().toggleTheme();
          },
        ));
      }
      if ('clipboard history paste copy'.contains(qLower) || qLower.contains('clip')) {
        actionItems.add(_SearchActionItem(
          title: 'Open Clipboard History',
          subtitle: 'Browse and re-copy clipboard history (Ctrl+Shift+V)',
          icon: Icons.content_paste_rounded,
          color: Colors.blueAccent,
          onTap: () {
            appState.toggleSearch(show: false);
            appState.toggleClipboard(show: true);
          },
        ));
      }
      if ('scratchpad note notes sticky write'.contains(qLower) || qLower.contains('note')) {
        actionItems.add(_SearchActionItem(
          title: 'Open Quick Scratchpad',
          subtitle: 'Floating scratchpad & thoughts (Ctrl+Shift+N)',
          icon: Icons.sticky_note_2_rounded,
          color: Colors.amber,
          onTap: () {
            appState.toggleSearch(show: false);
            appState.toggleScratchpad(show: true);
          },
        ));
      }
      if ('workspace space desktop'.contains(qLower) || qLower.contains('workspace')) {
        for (int i = 1; i <= appState.totalWorkspaces; i++) {
          actionItems.add(_SearchActionItem(
            title: 'Switch to Workspace $i',
            subtitle: 'Jump to Virtual Workspace $i',
            icon: Icons.space_dashboard_outlined,
            color: Colors.teal,
            onTap: () {
              appState.toggleSearch(show: false);
              appState.switchWorkspace(i);
            },
          ));
        }
      }
      if ('control center volume wifi bluetooth'.contains(qLower) || qLower.contains('control')) {
        actionItems.add(_SearchActionItem(
          title: 'Open Control Center',
          subtitle: 'Quick system toggles, sliders, and controls',
          icon: Icons.tune,
          color: Colors.indigoAccent,
          onTap: () {
            appState.toggleSearch(show: false);
            appState.toggleControlCenter(show: true);
          },
        ));
      }
    }

    return Semantics(
      label: 'Close search',
      button: true,
      child: GestureDetector(
      onTap: () => appState.toggleSearch(show: false),
      child: Container(
        color: Colors.black.withValues(alpha: 0.5),
        child: Align(
          alignment: const Alignment(0, -0.4),
          child: GestureDetector(
            onTap: () {},
            child: Container(
              constraints: const BoxConstraints(
                maxWidth: 580,
                maxHeight: 520,
              ),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHigh,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: colorScheme.outlineVariant.withValues(alpha: 0.4),
                ),
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
                      hintText: 'Search apps, calculate (e.g. 24*5), or run commands...',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: _query.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear),
                              tooltip: 'Clear search',
                              onPressed: () {
                                _controller.clear();
                                setState(() => _query = '');
                              },
                            )
                          : null,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    onChanged: (val) => setState(() => _query = val),
                  ),
                  const SizedBox(height: 12),

                  // Smart Arithmetic Calculation Result Card
                  if (mathResult != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: colorScheme.primaryContainer.withValues(alpha: 0.7),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: colorScheme.primary.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: colorScheme.primary,
                                shape: BoxShape.circle,
                              ),
                              child: Icon(
                                Icons.calculate_rounded,
                                size: 20,
                                color: colorScheme.onPrimary,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _formatMathResult(mathResult),
                                    style: TextStyle(
                                      fontSize: 22,
                                      fontWeight: FontWeight.bold,
                                      color: colorScheme.onPrimaryContainer,
                                    ),
                                  ),
                                  Text(
                                    '= ${_query.trim()}',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: colorScheme.onPrimaryContainer.withValues(alpha: 0.8),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.copy_rounded, size: 18),
                              tooltip: 'Copy Result',
                              onPressed: () async {
                                final res = _formatMathResult(mathResult);
                                await Clipboard.setData(ClipboardData(text: res));
                                appState.addNotification(
                                  'Calculator',
                                  'Copied $res to clipboard',
                                  Icons.calculate_rounded,
                                );
                                appState.toggleSearch(show: false);
                              },
                            ),
                          ],
                        ),
                      ),
                    ),

                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 320),
                    child: (actionItems.isEmpty && filtered.isEmpty && mathResult == null)
                        ? Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text(
                              'No matching apps, calculations, or commands found',
                              style: TextStyle(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                          )
                        : Material(
                            color: Colors.transparent,
                            child: ListView(
                              shrinkWrap: true,
                              children: [
                                for (final action in actionItems)
                                  Material(
                                    color: Colors.transparent,
                                    child: ListTile(
                                    leading: CircleAvatar(
                                      backgroundColor: (action.color ?? colorScheme.primary).withValues(alpha: 0.2),
                                      child: Icon(action.icon, color: action.color ?? colorScheme.primary),
                                    ),
                                    title: Text(action.title,
                                        style: const TextStyle(fontWeight: FontWeight.bold)),
                                    subtitle: Text(action.subtitle,
                                        maxLines: 1, overflow: TextOverflow.ellipsis),
                                    trailing: const Icon(Icons.arrow_forward_ios, size: 14),
                                    onTap: action.onTap,
                                  ),
                                ),
                                for (final app in filtered)
                                  Material(
                                    color: Colors.transparent,
                                    child: ListTile(
                                    leading: CircleAvatar(
                                      backgroundColor:
                                          app.color.withValues(alpha: 0.2),
                                      child: Icon(app.icon, color: app.color),
                                    ),
                                    title: Text(app.title,
                                        style: const TextStyle(
                                            fontWeight: FontWeight.bold)),
                                    subtitle: Text(
                                      '${app.category.label} • ${app.description}',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    trailing: const Icon(Icons.arrow_forward_ios,
                                        size: 14),
                                    onTap: () {
                                      appState.toggleSearch(show: false);
                                      widget.onOpenApp(app);
                                    },
                                  ),
                                ),
                              ],
                            ),
                          ),
                  ),
                ],
              ),
            ),
          ).animate().scale(
                begin: const Offset(0.9, 0.9),
                end: const Offset(1, 1),
                duration: 150.ms,
              ),
        ),
      ),
    ),
    ).animate().fadeIn(duration: 150.ms);
  }
}

// Fullscreen LaunchPad Overlay
class _LaunchPad extends StatelessWidget {
  final VoidCallback onClose;
  final OpenAppFn onOpenApp;

  const _LaunchPad({required this.onClose, required this.onOpenApp});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final apps = AppRegistry.apps;

    return Semantics(
      label: 'Close LaunchPad',
      button: true,
      child: GestureDetector(
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
                border: Border.all(
                  color: colorScheme.outlineVariant.withValues(alpha: 0.4),
                ),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.grid_view,
                          size: 28, color: colorScheme.primary),
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
                      gridDelegate:
                          const SliverGridDelegateWithMaxCrossAxisExtent(
                        maxCrossAxisExtent: 140,
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
                              child: Icon(app.icon,
                                  size: 38, color: Colors.white),
                            ),
                          ),
                          child: MouseRegion(
                            cursor: SystemMouseCursors.click,
                              child: Tooltip(
                               message: app.description,
                                child: Semantics(
                                  label: app.title,
                                  child: GestureDetector(
                                  onTap: () => onOpenApp(app),
                                  child: Center(
                                   child: FittedBox(
                                     fit: BoxFit.scaleDown,
                                     child: ConstrainedBox(
                                       constraints: const BoxConstraints(maxWidth: 130),
                                       child: Column(
                                         mainAxisSize: MainAxisSize.min,
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
                                             app.title,
                                             style: TextStyle(
                                               fontSize: 13,
                                               fontWeight: FontWeight.w500,
                                               color: colorScheme.onSurface,
                                             ),
                                             textAlign: TextAlign.center,
                                             maxLines: 2,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
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
          ).animate().scale(
                begin: const Offset(0.85, 0.85),
                end: const Offset(1, 1),
                duration: 200.ms,
              ),
        ),
      ),
    ),
    ).animate().fadeIn(duration: 200.ms);
  }
}

class _SearchActionItem {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color? color;
  final VoidCallback onTap;

  const _SearchActionItem({
    required this.title,
    required this.subtitle,
    required this.icon,
    this.color,
    required this.onTap,
  });
}

double? _evaluateMath(String input) {
  final clean = input.trim().replaceFirst(RegExp(r'^='), '').trim();
  if (clean.isEmpty) return null;
  if (!RegExp(r'^[0-9\.\s\+\-\*\/\%\^\(\)]+$').hasMatch(clean)) return null;
  if (!RegExp(r'[\+\-\*\/\%\^]').hasMatch(clean)) return null;

  try {
    return _parseExpression(clean);
  } catch (_) {
    return null;
  }
}

double? _parseExpression(String expression) {
  final tokens = <String>[];
  final buffer = StringBuffer();
  for (int i = 0; i < expression.length; i++) {
    final c = expression[i];
    if (c == ' ') continue;
    if ('+-*/%^()'.contains(c)) {
      if (buffer.isNotEmpty) {
        tokens.add(buffer.toString());
        buffer.clear();
      }
      tokens.add(c);
    } else {
      buffer.write(c);
    }
  }
  if (buffer.isNotEmpty) tokens.add(buffer.toString());
  if (tokens.isEmpty) return null;

  final output = <String>[];
  final ops = <String>[];
  int precedence(String op) {
    if (op == '+' || op == '-') return 1;
    if (op == '*' || op == '/' || op == '%') return 2;
    if (op == '^') return 3;
    return 0;
  }

  for (int i = 0; i < tokens.length; i++) {
    final t = tokens[i];
    final num = double.tryParse(t);
    if (num != null) {
      output.add(t);
    } else if (t == '(') {
      ops.add(t);
    } else if (t == ')') {
      while (ops.isNotEmpty && ops.last != '(') {
        output.add(ops.removeLast());
      }
      if (ops.isNotEmpty && ops.last == '(') ops.removeLast();
    } else {
      if (t == '-' && (i == 0 || tokens[i - 1] == '(' || '+-*/%^'.contains(tokens[i - 1]))) {
        output.add('0');
      }
      while (ops.isNotEmpty && precedence(ops.last) >= precedence(t)) {
        output.add(ops.removeLast());
      }
      ops.add(t);
    }
  }
  while (ops.isNotEmpty) {
    output.add(ops.removeLast());
  }

  final stack = <double>[];
  for (final t in output) {
    final num = double.tryParse(t);
    if (num != null) {
      stack.add(num);
    } else if (stack.length >= 2) {
      final b = stack.removeLast();
      final a = stack.removeLast();
      switch (t) {
        case '+':
          stack.add(a + b);
          break;
        case '-':
          stack.add(a - b);
          break;
        case '*':
          stack.add(a * b);
          break;
        case '/':
          stack.add(b == 0 ? double.nan : a / b);
          break;
        case '%':
          stack.add(a % b);
          break;
        case '^':
          stack.add(math.pow(a, b).toDouble());
          break;
      }
    }
  }
  return stack.isNotEmpty ? stack.last : null;
}

String _formatMathResult(double val) {
  if (val.isNaN || val.isInfinite) return 'Error';
  if (val == val.roundToDouble()) return val.toInt().toString();
  return val.toStringAsFixed(4).replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '');
}

// Universal Clipboard History Popover Modal (Ctrl+Shift+V)
class _ClipboardHistoryModal extends StatefulWidget {
  const _ClipboardHistoryModal();

  @override
  State<_ClipboardHistoryModal> createState() => _ClipboardHistoryModalState();
}

class _ClipboardHistoryModalState extends State<_ClipboardHistoryModal> {
  String _filter = '';

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final clipboardMgr = context.watch<ClipboardManager>();
    final colorScheme = Theme.of(context).colorScheme;

    final history = clipboardMgr.history
        .where((e) => e.text.toLowerCase().contains(_filter.toLowerCase()))
        .toList();

    return Material(
      color: Colors.transparent,
      child: Container(
              width: 380,
              constraints: const BoxConstraints(maxHeight: 520),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHigh,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: colorScheme.outlineVariant.withValues(alpha: 0.4),
                ),
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
                      Icon(Icons.content_paste_rounded, size: 20, color: colorScheme.primary),
                      const SizedBox(width: 8),
                      Text(
                        'Clipboard History',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                      ),
                      const Spacer(),
                      if (clipboardMgr.history.isNotEmpty)
                        TextButton(
                          onPressed: () => clipboardMgr.clearHistory(),
                          child: const Text('Clear All'),
                        ),
                      IconButton(
                        icon: const Icon(Icons.close, size: 18),
                        onPressed: () => appState.toggleClipboard(show: false),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  if (clipboardMgr.history.length > 2)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: TextField(
                        decoration: InputDecoration(
                          hintText: 'Search clipboard history...',
                          isDense: true,
                          prefixIcon: const Icon(Icons.search, size: 18),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        onChanged: (v) => setState(() => _filter = v),
                      ),
                    ),

                  if (history.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 36),
                      child: Center(
                        child: Column(
                          children: [
                            Icon(
                              Icons.content_paste_off_rounded,
                              size: 40,
                              color: colorScheme.onSurfaceVariant.withValues(alpha: 0.6),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              clipboardMgr.history.isEmpty
                                  ? 'Clipboard history is empty\nCopied text will appear here'
                                  : 'No matching items found',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 13,
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                    )
                  else
                    Flexible(
                      child: ListView.separated(
                        shrinkWrap: true,
                        itemCount: history.length,
                        separatorBuilder: (context, index) => const SizedBox(height: 6),
                        itemBuilder: (context, index) {
                          final item = history[index];
                          return Card(
                            margin: EdgeInsets.zero,
                            color: colorScheme.surfaceContainer,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: InkWell(
                              borderRadius: BorderRadius.circular(12),
                              onTap: () async {
                                await Clipboard.setData(ClipboardData(text: item.text));
                                appState.addNotification(
                                  'Clipboard',
                                  'Copied to clipboard: "${item.text.length > 25 ? '${item.text.substring(0, 25)}...' : item.text}"',
                                  Icons.content_paste_rounded,
                                );
                                appState.toggleClipboard(show: false);
                              },
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: colorScheme.primary.withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Text(
                                            item.action.name.toUpperCase(),
                                            style: TextStyle(
                                              fontSize: 9,
                                              fontWeight: FontWeight.bold,
                                              color: colorScheme.primary,
                                            ),
                                          ),
                                        ),
                                        const Spacer(),
                                        Text(
                                          _formatClipboardTime(item.timestamp),
                                          style: TextStyle(
                                            fontSize: 10,
                                            color: colorScheme.onSurfaceVariant,
                                          ),
                                        ),
                                        const SizedBox(width: 4),
                                        Icon(
                                          Icons.copy_rounded,
                                          size: 14,
                                          color: colorScheme.onSurfaceVariant,
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 6),
                                    Text(
                                      item.text,
                                      maxLines: 3,
                                      overflow: TextOverflow.ellipsis,
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: colorScheme.onSurface,
                                        fontFamily: 'monospace',
                                      ),
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
    ).animate().fadeIn(duration: 150.ms).slideY(begin: -0.04, end: 0);
  }

  String _formatClipboardTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inSeconds < 60) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${time.month}/${time.day}';
  }
}

// Quick Notes / Scratchpad Overlay Modal (Ctrl+Shift+N)
class _QuickScratchpadModal extends StatefulWidget {
  const _QuickScratchpadModal();

  @override
  State<_QuickScratchpadModal> createState() => _QuickScratchpadModalState();
}

class _QuickScratchpadModalState extends State<_QuickScratchpadModal> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    final appState = context.read<AppState>();
    _controller = TextEditingController(text: appState.scratchpadText);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final colorScheme = Theme.of(context).colorScheme;

    final wordCount = _controller.text.trim().isEmpty
        ? 0
        : _controller.text.trim().split(RegExp(r'\s+')).length;
    final charCount = _controller.text.length;

    return Material(
      color: Colors.transparent,
      child: Container(
              width: 380,
              height: 420,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHigh,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(
                  color: colorScheme.outlineVariant.withValues(alpha: 0.4),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.35),
                    blurRadius: 30,
                    spreadRadius: 3,
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.sticky_note_2_rounded, size: 20, color: Colors.amber),
                      const SizedBox(width: 8),
                      Text(
                        'Quick Scratchpad',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.green.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text(
                          'Auto-saved',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.bold,
                            color: Colors.green,
                          ),
                        ),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.close, size: 18),
                        onPressed: () => appState.toggleScratchpad(show: false),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainer,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: colorScheme.outlineVariant.withValues(alpha: 0.2),
                        ),
                      ),
                      child: TextField(
                        controller: _controller,
                        maxLines: null,
                        expands: true,
                        style: TextStyle(
                          fontSize: 13,
                          height: 1.45,
                          color: colorScheme.onSurface,
                        ),
                        decoration: const InputDecoration(
                          hintText: 'Type quick thoughts, phone numbers, snippets...',
                          border: InputBorder.none,
                          isDense: true,
                          contentPadding: EdgeInsets.zero,
                        ),
                        onChanged: (text) {
                          appState.updateScratchpad(text);
                          setState(() {});
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),

                  Row(
                    children: [
                      Text(
                        '$wordCount words • $charCount chars',
                        style: TextStyle(
                          fontSize: 11,
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const Spacer(),
                      TextButton.icon(
                        icon: const Icon(Icons.copy_rounded, size: 14),
                        label: const Text('Copy All', style: TextStyle(fontSize: 11)),
                        onPressed: _controller.text.isEmpty
                            ? null
                            : () async {
                                await Clipboard.setData(ClipboardData(text: _controller.text));
                                appState.addNotification(
                                  'Scratchpad',
                                  'Notes copied to clipboard',
                                  Icons.sticky_note_2_rounded,
                                );
                              },
                      ),
                      TextButton.icon(
                        icon: const Icon(Icons.clear_rounded, size: 14),
                        label: const Text('Clear', style: TextStyle(fontSize: 11)),
                        onPressed: _controller.text.isEmpty
                            ? null
                            : () {
                                _controller.clear();
                                appState.updateScratchpad('');
                                setState(() {});
                              },
                      ),
                    ],
                  ),
                ],
              ),
            ),
    ).animate().fadeIn(duration: 150.ms).slideY(begin: -0.04, end: 0);
  }
}
