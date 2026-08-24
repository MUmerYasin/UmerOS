import 'package:flutter/material.dart';
import 'dart:io';
import 'package:provider/provider.dart';
import '../core/app_state.dart';
import '../core/app_registry.dart';
import '../core/theme_provider.dart';
import '../animations/animations.dart';

class Dock extends StatefulWidget {
  /// Launch callback supplied by the shell; routes through the central
  /// [AppRegistry] so there is exactly one place that knows app metadata.
  final OpenAppFn onOpenApp;

  const Dock({super.key, required this.onOpenApp});

  @override
  State<Dock> createState() => _DockState();
}

class _DockState extends State<Dock> {
  int _hoveredIndex = -1;

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
              padding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(
                color: isHoveringDrag
                    ? Theme.of(context)
                        .colorScheme
                        .primaryContainer
                        .withValues(alpha: 0.95)
                    : Theme.of(context)
                        .colorScheme
                        .surfaceContainerHighest
                        .withValues(alpha: 0.88),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: isHoveringDrag
                      ? Theme.of(context).colorScheme.primary
                      : Theme.of(context)
                          .colorScheme
                          .outlineVariant
                          .withValues(alpha: 0.3),
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
                    // Unknown ids (e.g. stale persisted pins) fall back to a
                    // neutral placeholder instead of crashing the dock.
                    final meta = AppRegistry.byId(appId);

                    final isHovered = _hoveredIndex == index;
                    final isNeighbor = (_hoveredIndex - index).abs() == 1;

                    double scale = 1.0;
                    if (isHovered) {
                      scale = 1.35;
                    } else if (isNeighbor) {
                      scale = 1.15;
                    }

                    final window =
                        appState.windows.where((w) => w.id == appId).firstOrNull;
                    final isOpen = window != null;
                    final isMinimized = window?.isMinimized ?? false;
                    final isActive =
                        appState.activeWindowId == appId && isOpen && !isMinimized;
                    final isPinned = appState.pinnedDockIds.contains(appId);

                    final label = meta?.title ?? appId;
                    final icon = meta?.icon ?? Icons.apps;
                    final color = meta?.color ?? Colors.grey;

                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: MouseRegion(
                        onEnter: (_) => setState(() => _hoveredIndex = index),
                        onExit: (_) => setState(() => _hoveredIndex = -1),
                        child: PopupMenuButton<String>(
                          tooltip: label,
                          offset: const Offset(0, -90),
                          onSelected: (value) {
                            switch (value) {
                              case 'launch':
                                _handleTap(appState, appId, window);
                              case 'minimize':
                                appState.minimizeWindow(appId);
                              case 'close':
                                appState.closeWindow(appId);
                              case 'pin':
                                appState.pinDockItem(appId);
                              case 'unpin':
                                appState.unpinDockItem(appId);
                            }
                          },
                          itemBuilder: (context) => [
                            PopupMenuItem(
                              value: 'launch',
                              child: Row(children: [
                                Icon(icon, size: 18),
                                const SizedBox(width: 8),
                                Text('Open $label'),
                              ]),
                            ),
                            if (isOpen && !isMinimized)
                              const PopupMenuItem(
                                value: 'minimize',
                                child: Row(children: [
                                  Icon(Icons.minimize, size: 18),
                                  SizedBox(width: 8),
                                  Text('Minimize Window'),
                                ]),
                              ),
                            if (isOpen)
                              const PopupMenuItem(
                                value: 'close',
                                child: Row(children: [
                                  Icon(Icons.close, size: 18),
                                  SizedBox(width: 8),
                                  Text('Close Window'),
                                ]),
                              ),
                            if (isPinned)
                              const PopupMenuItem(
                                value: 'unpin',
                                child: Row(children: [
                                  Icon(Icons.push_pin_outlined, size: 18),
                                  SizedBox(width: 8),
                                  Text('Unpin from Dock'),
                                ]),
                              )
                            else
                              const PopupMenuItem(
                                value: 'pin',
                                child: Row(children: [
                                  Icon(Icons.push_pin, size: 18),
                                  SizedBox(width: 8),
                                  Text('Pin to Dock'),
                                ]),
                              ),
                          ],
                          child: GestureDetector(
                            onTap: () => _handleTap(appState, appId, window),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              curve: UmerCurves.spring,
                              width: 50 * scale,
                              height: 50 * scale,
                              child: Stack(
                                alignment: Alignment.center,
                                children: [
                                  // Hover glow that pulses when the icon is
                                  // the active focused window.
                                  if (isActive)
                                    Positioned.fill(
                                      child: HoverGlow(
                                        glowColor: color,
                                        maxGlow: 0.45,
                                        child: const SizedBox.shrink(),
                                      ),
                                    ),
                                  Container(
                                    width: 46 * scale,
                                    height: 46 * scale,
                                    decoration: BoxDecoration(
                                      color: isActive
                                          ? color.withValues(alpha: 0.28)
                                          : (isHovered
                                              ? color.withValues(alpha: 0.18)
                                              : Colors.transparent),
                                      borderRadius:
                                          BorderRadius.circular(14 * scale),
                                    ),
                                    child: Icon(
                                      icon,
                                      color: color,
                                      size: 26 * scale,
                                    ),
                                  ),

                                  // Open / Minimized State Dot Indicator.
                                  // For the *active* (focused) icon we use a
                                  // breathing PulsingDot so the user always
                                  // knows which window is on top.
                                  if (isOpen)
                                    Positioned(
                                      bottom: 1,
                                      child: isActive
                                          ? PulsingDot(
                                              size: 4,
                                              color: color,
                                              maxOpacity: 0.9,
                                            )
                                          : AnimatedContainer(
                                              duration: const Duration(
                                                  milliseconds: 200),
                                              width: isMinimized ? 8 : 6,
                                              height: 4,
                                              decoration: BoxDecoration(
                                                color: isMinimized
                                                    ? Colors.amber
                                                    : Theme.of(context)
                                                        .colorScheme
                                                        .onSurface
                                                        .withValues(alpha: 0.6),
                                                borderRadius:
                                                    BorderRadius.circular(2),
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

  void _handleTap(AppState appState, String appId, WindowData? window) {
    final meta = AppRegistry.byId(appId);
    if (window == null) {
      if (meta == null) return; // unknown app id — nothing to launch
      widget.onOpenApp(meta);
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
                color: isActive
                    ? colorScheme.onSurface
                    : colorScheme.onSurfaceVariant,
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
            color: _isHovered
                ? Colors.white
                : Theme.of(context)
                    .colorScheme
                    .onSurface
                    .withValues(alpha: 0.7),
          ),
        ),
        onSelected: (mode) {
          if (mode == WindowSnapMode.maximized && widget.isMaximized) {
            appState.snapWindow(widget.windowId, WindowSnapMode.normal, screenSize);
          } else {
            appState.snapWindow(widget.windowId, mode, screenSize);
          }
        },
        itemBuilder: (context) => const [
          PopupMenuItem(
            value: WindowSnapMode.maximized,
            child: Row(children: [
              Icon(Icons.fullscreen, size: 18),
              SizedBox(width: 8),
              Text('Maximize / Fullscreen'),
            ]),
          ),
          PopupMenuItem(
            value: WindowSnapMode.leftHalf,
            child: Row(children: [
              Icon(Icons.align_horizontal_left, size: 18),
              SizedBox(width: 8),
              Text('Snap Left 50%'),
            ]),
          ),
          PopupMenuItem(
            value: WindowSnapMode.rightHalf,
            child: Row(children: [
              Icon(Icons.align_horizontal_right, size: 18),
              SizedBox(width: 8),
              Text('Snap Right 50%'),
            ]),
          ),
          PopupMenuItem(
            value: WindowSnapMode.topLeft,
            child: Row(children: [
              Icon(Icons.north_west, size: 18),
              SizedBox(width: 8),
              Text('Snap Top-Left 25%'),
            ]),
          ),
          PopupMenuItem(
            value: WindowSnapMode.topRight,
            child: Row(children: [
              Icon(Icons.north_east, size: 18),
              SizedBox(width: 8),
              Text('Snap Top-Right 25%'),
            ]),
          ),
          PopupMenuItem(
            value: WindowSnapMode.centered,
            child: Row(children: [
              Icon(Icons.filter_center_focus, size: 18),
              SizedBox(width: 8),
              Text('Center 80%'),
            ]),
          ),
          PopupMenuItem(
            value: WindowSnapMode.normal,
            child: Row(children: [
              Icon(Icons.refresh, size: 18),
              SizedBox(width: 8),
              Text('Restore Normal'),
            ]),
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
            color: _isHovered
                ? Colors.white
                : Theme.of(context)
                    .colorScheme
                    .onSurface
                    .withValues(alpha: 0.7),
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

    if (themeProvider.wallpaper == WallpaperPreset.customImage &&
        themeProvider.customImagePath != null) {
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
            ? [
                const Color(0xFF0D0221),
                const Color(0xFF0A1628),
                const Color(0xFF1A0A2E),
              ]
            : [
                const Color(0xFFE8EAF6),
                const Color(0xFFF3E5F5),
                const Color(0xFFE1F5FE),
              ];
      case WallpaperPreset.deepSpace:
        colors = const [
          Color(0xFF03071E),
          Color(0xFF0F172A),
          Color(0xFF1E1035),
        ];
      case WallpaperPreset.auroraBoreal:
        colors = const [
          Color(0xFF0F2027),
          Color(0xFF203A43),
          Color(0xFF2C5364),
        ];
      case WallpaperPreset.cyberpunkNeon:
        colors = const [
          Color(0xFF1A002C),
          Color(0xFF001220),
          Color(0xFF2D0036),
        ];
      case WallpaperPreset.minimalMesh:
        colors = const [
          Color(0xFF121212),
          Color(0xFF1E1E1E),
          Color(0xFF2A2A2A),
        ];
      case WallpaperPreset.midnightSlate:
        colors = const [
          Color(0xFF1A202C),
          Color(0xFF2D3748),
          Color(0xFF4A5568),
        ];
      case WallpaperPreset.customImage:
        colors = const [Color(0xFF0D0221), Color(0xFF0A1628)];
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
