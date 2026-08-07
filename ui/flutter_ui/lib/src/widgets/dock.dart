import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import '../core/app_state.dart';

class DockItem {
  final String id;
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const DockItem({
    required this.id,
    required this.label,
    required this.icon,
    this.color = Colors.deepPurple,
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
    return Container(
      height: 72,
      margin: const EdgeInsets.only(bottom: 8),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.85),
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.2),
                blurRadius: 20,
                spreadRadius: 2,
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(widget.items.length, (index) {
              final item = widget.items[index];
              final isHovered = _hoveredIndex == index;
              final scale = isHovered ? 1.3 : 1.0;

              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: MouseRegion(
                  onEnter: (_) => setState(() => _hoveredIndex = index),
                  onExit: (_) => setState(() => _hoveredIndex = -1),
                  child: GestureDetector(
                    onTap: item.onTap,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      curve: Curves.easeOutBack,
                      width: 52 * scale,
                      height: 52 * scale,
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            item.icon,
                            color: item.color,
                            size: 28 * scale,
                          ),
                          if (isHovered)
                            Text(
                              item.label,
                              style: TextStyle(
                                fontSize: 10,
                                color: Theme.of(context).colorScheme.onSurface,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ).animate().fadeIn(duration: 150.ms),
                        ],
                      ),
                    ),
                  ),
                ),
              ).animate(delay: (index * 30).ms).slideY(begin: 0.3, end: 0);
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
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.9),
          borderRadius: BorderRadius.circular(12),
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
              padding: const EdgeInsets.symmetric(horizontal: 3),
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: () => onTap(item.id),
                  child: Tooltip(
                    message: item.label,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: 56,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            item.icon,
                            color: item.isActive
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.8),
                            size: 24,
                          ),
                          const SizedBox(height: 3),
                          Container(
                            width: item.isActive ? 24 : 12,
                            height: 3,
                            decoration: BoxDecoration(
                              color: item.isActive
                                  ? Theme.of(context).colorScheme.primary
                                  : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4),
                              borderRadius: BorderRadius.circular(2),
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

  const WindowTitleBar({
    super.key,
    required this.title,
    required this.icon,
    required this.windowId,
    this.isMaximized = false,
  });

  @override
  Widget build(BuildContext context) {
    final appState = context.read<AppState>();

    return Container(
      height: 38,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.9),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
      ),
      child: Row(
        children: [
          const SizedBox(width: 12),
          Icon(icon, size: 16, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
          ),
          _WindowButton(
            icon: Icons.horizontal_rule,
            tooltip: 'Minimize',
            color: Colors.orange,
            onTap: () => appState.minimizeWindow(windowId),
          ),
          _WindowButton(
            icon: isMaximized ? Icons.filter_none : Icons.maximize,
            tooltip: isMaximized ? 'Restore' : 'Maximize',
            color: Colors.green,
            onTap: () => appState.maximizeWindow(windowId),
          ),
          _WindowButton(
            icon: Icons.close,
            tooltip: 'Close',
            color: Colors.red,
            onTap: () => appState.closeWindow(windowId),
          ),
          const SizedBox(width: 4),
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
            color: _isHovered ? Colors.white : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? [
                  const Color(0xFF0D0221),
                  const Color(0xFF0A1628),
                  const Color(0xFF1A0A2E),
                ]
              : [
                  const Color(0xFFE8EAF6),
                  const Color(0xFFF3E5F5),
                  const Color(0xFFE1F5FE),
                ],
        ),
      ),
      child: child,
    );
  }
}
