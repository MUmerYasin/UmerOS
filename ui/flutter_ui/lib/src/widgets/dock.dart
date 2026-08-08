import 'package:flutter/material.dart';
import 'dart:io';
import 'package:provider/provider.dart';
import '../core/app_state.dart';
import '../core/theme_provider.dart';
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

class _AppMeta {
  final String id;
  final String label;
  final IconData icon;
  final Color color;
  final Widget child;

  const _AppMeta(this.id, this.label, this.icon, this.color, this.child);
}

class Dock extends StatefulWidget {
  final Function(String id, String title, IconData icon, Widget child) onOpenApp;

  const Dock({super.key, required this.onOpenApp});

  @override
  State<Dock> createState() => _DockState();
}

class _DockState extends State<Dock> {
  int _hoveredIndex = -1;

  final Map<String, _AppMeta> _registry = {
    'browser': const _AppMeta('browser', 'Browser', Icons.language, Colors.blue, BrowserApp()),
    'terminal': const _AppMeta('terminal', 'Terminal', Icons.terminal, Colors.teal, TerminalApp()),
    'files': const _AppMeta('files', 'File Manager', Icons.folder, Colors.amber, FileManagerApp()),
    'monitor': const _AppMeta('monitor', 'System Monitor', Icons.monitor_heart, Colors.green, SystemMonitorApp()),
    'power': const _AppMeta('power', 'Power & Governor', Icons.bolt, Colors.amber, PowerGovernorApp()),
    'settings': const _AppMeta('settings', 'Settings', Icons.tune, Colors.blueGrey, SettingsApp()),
    'editor': const _AppMeta('editor', 'Text Editor', Icons.edit_note, Colors.orange, TextEditorApp()),
    'packages': const _AppMeta('packages', 'Package Manager', Icons.inventory_2, Colors.purple, PackageManagerApp()),
    'network': const _AppMeta('network', 'Network Manager', Icons.wifi, Colors.cyan, NetworkManagerApp()),
    'calendar': const _AppMeta('calendar', 'Calendar', Icons.calendar_month, Colors.indigo, CalendarApp()),
    'calculator': const _AppMeta('calculator', 'Calculator', Icons.calculate, Colors.blueGrey, CalculatorApp()),
    'quantum': const _AppMeta('quantum', 'Quantum Sim', Icons.blur_circular, Colors.deepPurple, QuantumSimApp()),
    'security': const _AppMeta('security', 'Security', Icons.shield, Colors.redAccent, SecurityApp()),
    'antivirus': const _AppMeta('antivirus', 'Antivirus', Icons.health_and_safety, Colors.lightGreen, AntivirusApp()),
    'boot': const _AppMeta('boot', 'Boot Manager', Icons.power_settings_new, Colors.amber, BootManagerApp()),
    'games': const _AppMeta('games', 'Games', Icons.sports_esports, Colors.pink, GamesApp()),
    'docs': const _AppMeta('docs', 'Documentation', Icons.menu_book, Colors.deepOrange, DocsApp()),
  };

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();

    // Dynamic dock items = pinned items + open unpinned windows
    final dockItemIds = <String>{...appState.pinnedDockIds};
    for (var w in appState.windows) {
      dockItemIds.add(w.id);
    }
    final itemsList = dockItemIds.toList();

    return DragTarget<String>(
      onWillAcceptWithDetails: (details) => true,
      onAcceptWithDetails: (details) {
        appState.pinDockItem(details.data);
      },
      builder: (context, candidateData, rejectedData) {
        final isHoveringDrag = candidateData.isNotEmpty;

        return Container(
          height: 76,
          margin: const EdgeInsets.only(bottom: 8),
          child: Center(
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(
                color: isHoveringDrag
                    ? Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.95)
                    : Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.88),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: isHoveringDrag
                      ? Theme.of(context).colorScheme.primary
                      : Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.3),
                  width: isHoveringDrag ? 2 : 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.3),
                    blurRadius: 24,
                    spreadRadius: 2,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: List.generate(itemsList.length, (index) {
                    final appId = itemsList[index];
                    final meta = _registry[appId] ?? _AppMeta(appId, appId, Icons.apps, Colors.grey, const SizedBox());

                    final isHovered = _hoveredIndex == index;
                    final isNeighbor = (_hoveredIndex - index).abs() == 1;

                    double scale = 1.0;
                    if (isHovered) {
                      scale = 1.35;
                    } else if (isNeighbor) {
                      scale = 1.15;
                    }

                    final window = appState.windows.where((w) => w.id == appId).firstOrNull;
                    final isOpen = window != null;
                    final isMinimized = window?.isMinimized ?? false;
                    final isActive = appState.activeWindowId == appId && isOpen && !isMinimized;
                    final isPinned = appState.pinnedDockIds.contains(appId);

                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: MouseRegion(
                        onEnter: (_) => setState(() => _hoveredIndex = index),
                        onExit: (_) => setState(() => _hoveredIndex = -1),
                        child: PopupMenuButton<String>(
                          tooltip: meta.label,
                          offset: const Offset(0, -90),
                          onSelected: (value) {
                            if (value == 'launch') {
                              _handleTap(appState, meta, window);
                            } else if (value == 'minimize') {
                              appState.minimizeWindow(appId);
                            } else if (value == 'close') {
                              appState.closeWindow(appId);
                            } else if (value == 'pin') {
                              appState.pinDockItem(appId);
                            } else if (value == 'unpin') {
                              appState.unpinDockItem(appId);
                            }
                          },
                          itemBuilder: (context) => [
                            PopupMenuItem(
                              value: 'launch',
                              child: Row(children: [Icon(meta.icon, size: 18), const SizedBox(width: 8), Text('Open ${meta.label}')]),
                            ),
                            if (isOpen && !isMinimized)
                              const PopupMenuItem(
                                value: 'minimize',
                                child: Row(children: [Icon(Icons.minimize, size: 18), SizedBox(width: 8), Text('Minimize Window')]),
                              ),
                            if (isOpen)
                              const PopupMenuItem(
                                value: 'close',
                                child: Row(children: [Icon(Icons.close, size: 18), SizedBox(width: 8), Text('Close Window')]),
                              ),
                            if (isPinned)
                              const PopupMenuItem(
                                value: 'unpin',
                                child: Row(children: [Icon(Icons.push_pin_outlined, size: 18), SizedBox(width: 8), Text('Unpin from Dock')]),
                              )
                            else
                              const PopupMenuItem(
                                value: 'pin',
                                child: Row(children: [Icon(Icons.push_pin, size: 18), SizedBox(width: 8), Text('Pin to Dock')]),
                              ),
                          ],
                          child: GestureDetector(
                            onTap: () => _handleTap(appState, meta, window),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              curve: Curves.easeOutBack,
                              width: 50 * scale,
                              height: 50 * scale,
                              child: Stack(
                                alignment: Alignment.center,
                                children: [
                                  Container(
                                    width: 46 * scale,
                                    height: 46 * scale,
                                    decoration: BoxDecoration(
                                      color: isActive
                                          ? meta.color.withValues(alpha: 0.28)
                                          : (isHovered
                                              ? meta.color.withValues(alpha: 0.18)
                                              : Colors.transparent),
                                      borderRadius: BorderRadius.circular(14 * scale),
                                    ),
                                    child: Icon(
                                      meta.icon,
                                      color: meta.color,
                                      size: 26 * scale,
                                    ),
                                  ),

                                  // Open / Minimized State Dot Indicator
                                  if (isOpen)
                                    Positioned(
                                      bottom: 1,
                                      child: AnimatedContainer(
                                        duration: const Duration(milliseconds: 200),
                                        width: isActive ? 16 : 6,
                                        height: 4,
                                        decoration: BoxDecoration(
                                          color: isActive
                                              ? Theme.of(context).colorScheme.primary
                                              : (isMinimized
                                                  ? Colors.amber
                                                  : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6)),
                                          borderRadius: BorderRadius.circular(2),
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                    );
                  }),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  void _handleTap(AppState appState, _AppMeta meta, WindowData? window) {
    if (window == null) {
      widget.onOpenApp(meta.id, meta.label, meta.icon, meta.child);
    } else if (window.isMinimized) {
      appState.restoreWindow(window.id);
    } else if (appState.activeWindowId == window.id) {
      appState.minimizeWindow(window.id);
    } else {
      appState.focusWindow(window.id);
    }
  }
}

class WindowTitleBar extends StatelessWidget {
  final String title;
  final IconData icon;
  final String windowId;
  final bool isMaximized;
  final bool isActive;

  const WindowTitleBar({
    super.key,
    required this.title,
    required this.icon,
    required this.windowId,
    this.isMaximized = false,
    this.isActive = true,
  });

  @override
  Widget build(BuildContext context) {
    final appState = context.read<AppState>();
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: isActive
            ? colorScheme.surfaceContainerHigh
            : colorScheme.surfaceContainerHighest.withValues(alpha: 0.6),
        border: Border(
          bottom: BorderSide(
            color: colorScheme.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
      ),
      child: Row(
        children: [
          Icon(
            icon,
            size: 18,
            color: isActive ? colorScheme.primary : colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                color: isActive ? colorScheme.onSurface : colorScheme.onSurfaceVariant,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          _WindowButton(
            icon: Icons.minimize,
            tooltip: 'Minimize to Dock',
            color: Colors.amber,
            onTap: () => appState.minimizeWindow(windowId),
          ),
          _SnapWindowButton(
            windowId: windowId,
            isMaximized: isMaximized,
            onMaximizeToggle: () => appState.maximizeWindow(windowId),
          ),
          _WindowButton(
            icon: Icons.close,
            tooltip: 'Close',
            color: Colors.redAccent,
            onTap: () => appState.closeWindow(windowId),
          ),
        ],
      ),
    );
  }
}

class _SnapWindowButton extends StatefulWidget {
  final String windowId;
  final bool isMaximized;
  final VoidCallback onMaximizeToggle;

  const _SnapWindowButton({
    required this.windowId,
    required this.isMaximized,
    required this.onMaximizeToggle,
  });

  @override
  State<_SnapWindowButton> createState() => _SnapWindowButtonState();
}

class _SnapWindowButtonState extends State<_SnapWindowButton> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final appState = context.read<AppState>();
    final screenSize = MediaQuery.of(context).size;

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: PopupMenuButton<WindowSnapMode>(
        tooltip: widget.isMaximized ? 'Restore Window' : 'Snap / Maximize Window',
        icon: Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: _isHovered ? Colors.green : Colors.transparent,
            shape: BoxShape.circle,
          ),
          child: Icon(
            widget.isMaximized ? Icons.crop_square : Icons.crop_din,
            size: 13,
            color: _isHovered ? Colors.white : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
        onSelected: (mode) {
          if (mode == WindowSnapMode.maximized && widget.isMaximized) {
            appState.snapWindow(widget.windowId, WindowSnapMode.normal, screenSize);
          } else {
            appState.snapWindow(widget.windowId, mode, screenSize);
          }
        },
        itemBuilder: (context) => [
          const PopupMenuItem(
            value: WindowSnapMode.maximized,
            child: Row(children: [Icon(Icons.fullscreen, size: 18), SizedBox(width: 8), Text('Maximize / Fullscreen')]),
          ),
          const PopupMenuItem(
            value: WindowSnapMode.leftHalf,
            child: Row(children: [Icon(Icons.align_horizontal_left, size: 18), SizedBox(width: 8), Text('Snap Left 50%')]),
          ),
          const PopupMenuItem(
            value: WindowSnapMode.rightHalf,
            child: Row(children: [Icon(Icons.align_horizontal_right, size: 18), SizedBox(width: 8), Text('Snap Right 50%')]),
          ),
          const PopupMenuItem(
            value: WindowSnapMode.topLeft,
            child: Row(children: [Icon(Icons.north_west, size: 18), SizedBox(width: 8), Text('Snap Top-Left 25%')]),
          ),
          const PopupMenuItem(
            value: WindowSnapMode.topRight,
            child: Row(children: [Icon(Icons.north_east, size: 18), SizedBox(width: 8), Text('Snap Top-Right 25%')]),
          ),
          const PopupMenuItem(
            value: WindowSnapMode.centered,
            child: Row(children: [Icon(Icons.filter_center_focus, size: 18), SizedBox(width: 8), Text('Center 80%')]),
          ),
          const PopupMenuItem(
            value: WindowSnapMode.normal,
            child: Row(children: [Icon(Icons.refresh, size: 18), SizedBox(width: 8), Text('Restore Normal')]),
          ),
        ],
      ),
    );
  }
}

class _WindowButton extends StatefulWidget {
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  final String? tooltip;

  const _WindowButton({
    required this.icon,
    required this.color,
    required this.onTap,
    this.tooltip,
  });

  @override
  State<_WindowButton> createState() => _WindowButtonState();
}

class _WindowButtonState extends State<_WindowButton> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final btn = MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          width: 24,
          height: 24,
          margin: const EdgeInsets.symmetric(horizontal: 2),
          decoration: BoxDecoration(
            color: _isHovered ? widget.color : Colors.transparent,
            shape: BoxShape.circle,
          ),
          child: Icon(
            widget.icon,
            size: 12,
            color: _isHovered ? Colors.white : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ),
    );

    if (widget.tooltip != null) {
      return Tooltip(message: widget.tooltip!, child: btn);
    }
    return btn;
  }
}

class DesktopBackground extends StatelessWidget {
  final Widget child;

  const DesktopBackground({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final themeProvider = context.watch<ThemeProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    if (themeProvider.wallpaper == WallpaperPreset.customImage && themeProvider.customImagePath != null) {
      return Container(
        decoration: BoxDecoration(
          image: DecorationImage(
            image: FileImage(File(themeProvider.customImagePath!)),
            fit: BoxFit.cover,
          ),
        ),
        child: child,
      );
    }

    List<Color> colors;
    switch (themeProvider.wallpaper) {
      case WallpaperPreset.quantumGradient:
        colors = isDark
            ? [const Color(0xFF0D0221), const Color(0xFF0A1628), const Color(0xFF1A0A2E)]
            : [const Color(0xFFE8EAF6), const Color(0xFFF3E5F5), const Color(0xFFE1F5FE)];
        break;
      case WallpaperPreset.deepSpace:
        colors = [const Color(0xFF03071E), const Color(0xFF0F172A), const Color(0xFF1E1035)];
        break;
      case WallpaperPreset.auroraBoreal:
        colors = [const Color(0xFF0F2027), const Color(0xFF203A43), const Color(0xFF2C5364)];
        break;
      case WallpaperPreset.cyberpunkNeon:
        colors = [const Color(0xFF1A002C), const Color(0xFF001220), const Color(0xFF2D0036)];
        break;
      case WallpaperPreset.minimalMesh:
        colors = [const Color(0xFF121212), const Color(0xFF1E1E1E), const Color(0xFF2A2A2A)];
        break;
      case WallpaperPreset.midnightSlate:
        colors = [const Color(0xFF1A202C), const Color(0xFF2D3748), const Color(0xFF4A5568)];
        break;
      case WallpaperPreset.customImage:
        colors = [const Color(0xFF0D0221), const Color(0xFF0A1628)];
        break;
    }

    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: colors,
        ),
      ),
      child: child,
    );
  }
}
