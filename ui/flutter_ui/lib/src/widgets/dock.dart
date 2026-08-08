import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../core/app_state.dart';
import '../core/theme_provider.dart';

class DockItem {
  final String id;
  final String label;
  final IconData icon;
  final Color color;
  final int badgeCount;
  final VoidCallback onTap;

  const DockItem({
    required this.id,
    required this.label,
    required this.icon,
    this.color = Colors.deepPurple,
    this.badgeCount = 0,
    required this.onTap,
  });
}

class Dock extends StatefulWidget {
  final List<DockItem> items;

  const Dock({super.key, required this.items});

  @override
  State<Dock> createState() => _DockState();
}

class _DockState extends State<Dock> {
  int _hoveredIndex = -1;

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();

    return Container(
      height: 76,
      margin: const EdgeInsets.only(bottom: 10),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.85),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.3),
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
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(widget.items.length, (index) {
              final item = widget.items[index];
              final isHovered = _hoveredIndex == index;
              final isNeighbor = (_hoveredIndex - index).abs() == 1;

              double scale = 1.0;
              if (isHovered) {
                scale = 1.35;
              } else if (isNeighbor) {
                scale = 1.15;
              }

              final isOpen = appState.windows.any((w) => w.id == item.id);
              final isActive = appState.activeWindowId == item.id && isOpen;

              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 5),
                child: MouseRegion(
                  onEnter: (_) => setState(() => _hoveredIndex = index),
                  onExit: (_) => setState(() => _hoveredIndex = -1),
                  child: GestureDetector(
                    onTap: item.onTap,
                    child: Tooltip(
                      message: item.label,
                      preferBelow: false,
                      verticalOffset: 36,
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        curve: Curves.easeOutBack,
                        width: 52 * scale,
                        height: 52 * scale,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            Container(
                              width: 48 * scale,
                              height: 48 * scale,
                              decoration: BoxDecoration(
                                color: isActive
                                    ? item.color.withValues(alpha: 0.25)
                                    : (isHovered
                                        ? item.color.withValues(alpha: 0.15)
                                        : Colors.transparent),
                                borderRadius: BorderRadius.circular(14 * scale),
                              ),
                              child: Icon(
                                item.icon,
                                color: item.color,
                                size: 26 * scale,
                              ),
                            ),

                            // Open App Indicator Dot
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
                                        : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                                    borderRadius: BorderRadius.circular(2),
                                  ),
                                ),
                              ),

                            // Notification Badge
                            if (item.badgeCount > 0)
                              Positioned(
                                top: 2,
                                right: 2,
                                child: Container(
                                  padding: const EdgeInsets.all(4),
                                  decoration: const BoxDecoration(
                                    color: Colors.redAccent,
                                    shape: BoxShape.circle,
                                  ),
                                  child: Text(
                                    '${item.badgeCount}',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 9,
                                      fontWeight: FontWeight.bold,
                                    ),
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
    );
  }
}

class TaskbarItem {
  final String id;
  final String label;
  final IconData icon;
  final Color color;
  final bool isMinimized;
  final bool isActive;

  const TaskbarItem({
    required this.id,
    required this.label,
    required this.icon,
    this.color = Colors.deepPurple,
    this.isMinimized = false,
    this.isActive = false,
  });
}

class Taskbar extends StatelessWidget {
  final List<TaskbarItem> items;
  final Function(String id) onTap;

  const Taskbar({super.key, required this.items, required this.onTap});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();

    return Center(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.9),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.3),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.25),
              blurRadius: 16,
              spreadRadius: 1,
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: items.map((item) {
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: () => onTap(item.id),
                  child: Tooltip(
                    message: item.label,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: item.isActive
                            ? Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.8)
                            : (item.isMinimized
                                ? Theme.of(context).colorScheme.surfaceContainer.withValues(alpha: 0.4)
                                : Theme.of(context).colorScheme.surfaceContainerHigh.withValues(alpha: 0.6)),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: item.isActive
                              ? Theme.of(context).colorScheme.primary
                              : Colors.transparent,
                          width: 1,
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            item.icon,
                            color: item.isActive
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.8),
                            size: 18,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            item.label,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: item.isActive ? FontWeight.w600 : FontWeight.normal,
                              color: item.isActive
                                  ? Theme.of(context).colorScheme.onPrimaryContainer
                                  : Theme.of(context).colorScheme.onSurface,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
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
            tooltip: 'Minimize',
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
