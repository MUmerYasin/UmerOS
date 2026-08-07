import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../core/app_state.dart';
import 'dock.dart';

class DraggableWindow extends StatefulWidget {
  final WindowData window;

  const DraggableWindow({super.key, required this.window});

  @override
  State<DraggableWindow> createState() => _DraggableWindowState();
}

class _DraggableWindowState extends State<DraggableWindow> {
  bool _isDragging = false;

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final isActive = appState.activeWindowId == widget.window.id;

    if (widget.window.isMaximized) {
      return Positioned.fill(
        child: Material(
          color: Colors.transparent,
          child: Column(
            children: [
              WindowTitleBar(
                title: widget.window.title,
                icon: widget.window.icon,
                windowId: widget.window.id,
              ),
              Expanded(
                child: Container(
                  color: Theme.of(context).colorScheme.surface,
                  child: widget.window.child,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Positioned(
      left: widget.window.position.dx,
      top: widget.window.position.dy,
      child: GestureDetector(
        onPanStart: (details) {
          _isDragging = true;
          appState.openWindow(
            id: widget.window.id,
            title: widget.window.title,
            icon: widget.window.icon,
            child: widget.window.child,
          );
        },
        onPanUpdate: (details) {
          if (_isDragging) {
            appState.moveWindow(widget.window.id, details.delta);
          }
        },
        onPanEnd: (_) {
          _isDragging = false;
        },
        child: MouseRegion(
          cursor: _isDragging ? SystemMouseCursors.move : MouseCursor.defer,
          child: Container(
            width: widget.window.size.width,
            height: widget.window.size.height,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isActive
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.outline.withValues(alpha: 0.3),
                width: isActive ? 2 : 1,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: isActive ? 0.4 : 0.2),
                  blurRadius: isActive ? 24 : 12,
                  spreadRadius: isActive ? 2 : 0,
                ),
              ],
            ),
            child: Column(
              children: [
                WindowTitleBar(
                  title: widget.window.title,
                  icon: widget.window.icon,
                  windowId: widget.window.id,
                ),
                Expanded(
                  child: ClipRRect(
                    borderRadius: const BorderRadius.vertical(
                      bottom: Radius.circular(12),
                    ),
                    child: widget.window.child,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
