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
  bool _isDraggingHeader = false;
  Offset _dragStartGlobal = Offset.zero;
  Offset _windowStartPos = Offset.zero;

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final isActive = appState.activeWindowId == widget.window.id;
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final screenSize = MediaQuery.of(context).size;

    if (widget.window.isMinimized) {
      return Offstage(
        offstage: true,
        child: widget.window.child,
      );
    }

    // Maximized state — stretches over the entire desktop.
    if (widget.window.isMaximized) {
      return Positioned.fill(
        child: GestureDetector(
          onTapDown: (_) => appState.focusWindow(widget.window.id),
          onDoubleTap: () => appState.maximizeWindow(widget.window.id),
          child: Material(
            elevation: 12,
            color: colorScheme.surface,
            borderRadius: BorderRadius.zero,
            child: Column(
              children: [
                WindowTitleBar(
                  title: widget.window.title,
                  icon: widget.window.icon,
                  windowId: widget.window.id,
                  isMaximized: true,
                  isActive: isActive,
                ),
                Expanded(
                  child: Container(
                    color: colorScheme.surface,
                    child: widget.window.child,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Positioned(
      left: widget.window.position.dx,
      top: widget.window.position.dy,
      child: GestureDetector(
        onTapDown: (_) => appState.focusWindow(widget.window.id),
        child: AnimatedContainer(
          duration: _isDraggingHeader ? Duration.zero : const Duration(milliseconds: 150),
          curve: Curves.easeOutCubic,
          width: widget.window.size.width,
          height: widget.window.size.height,
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isActive
                  ? colorScheme.primary
                  : colorScheme.outlineVariant.withValues(alpha: 0.5),
              width: isActive ? 2.0 : 1.0,
            ),
            boxShadow: [
              BoxShadow(
                color: isActive
                    ? colorScheme.primary.withValues(alpha: 0.25)
                    : Colors.black.withValues(alpha: 0.2),
                blurRadius: isActive ? 32 : 16,
                spreadRadius: isActive ? 2 : 0,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(15),
            child: Stack(
              children: [
                // Window Main Layout
                Column(
                  children: [
                    // Header Drag Zone ONLY
                    GestureDetector(
                      onDoubleTap: () => appState.maximizeWindow(widget.window.id),
                      onPanStart: (details) {
                        _isDraggingHeader = true;
                        _dragStartGlobal = details.globalPosition;
                        _windowStartPos = widget.window.position;
                        appState.focusWindow(widget.window.id);
                      },
                      onPanUpdate: (details) {
                        if (!_isDraggingHeader) return;
                        final delta = details.globalPosition - _dragStartGlobal;
                        appState.moveWindow(widget.window.id, delta - (widget.window.position - _windowStartPos));

                        // Check Edge Snap Preview
                        final pos = details.globalPosition;
                        final topOffset = 32.0;
                        final bottomOffset = 80.0;
                        final availH = screenSize.height - topOffset - bottomOffset;

                        if (pos.dx < 30) {
                          if (pos.dy < topOffset + availH * 0.3) {
                            appState.setSnapPreview(Rect.fromLTWH(0, topOffset, screenSize.width * 0.5, availH * 0.5));
                          } else if (pos.dy > screenSize.height - bottomOffset - availH * 0.3) {
                            appState.setSnapPreview(Rect.fromLTWH(0, topOffset + availH * 0.5, screenSize.width * 0.5, availH * 0.5));
                          } else {
                            appState.setSnapPreview(Rect.fromLTWH(0, topOffset, screenSize.width * 0.5, availH));
                          }
                        } else if (pos.dx > screenSize.width - 30) {
                          if (pos.dy < topOffset + availH * 0.3) {
                            appState.setSnapPreview(Rect.fromLTWH(screenSize.width * 0.5, topOffset, screenSize.width * 0.5, availH * 0.5));
                          } else if (pos.dy > screenSize.height - bottomOffset - availH * 0.3) {
                            appState.setSnapPreview(Rect.fromLTWH(screenSize.width * 0.5, topOffset + availH * 0.5, screenSize.width * 0.5, availH * 0.5));
                          } else {
                            appState.setSnapPreview(Rect.fromLTWH(screenSize.width * 0.5, topOffset, screenSize.width * 0.5, availH));
                          }
                        } else if (pos.dy < topOffset + 15) {
                          appState.setSnapPreview(Rect.fromLTWH(0, topOffset, screenSize.width, availH));
                        } else {
                          appState.setSnapPreview(null);
                        }
                      },
                      onPanEnd: (details) {
                        _isDraggingHeader = false;
                        final preview = appState.snapPreviewRect;
                        if (preview != null) {
                          appState.setSnapPreview(null);
                          final topOffset = 32.0;
                          final bottomOffset = 80.0;
                          final availH = screenSize.height - topOffset - bottomOffset;

                          if (preview.width == screenSize.width) {
                            appState.snapWindow(widget.window.id, WindowSnapMode.maximized, screenSize);
                          } else if (preview.left == 0 && preview.height == availH) {
                            appState.snapWindow(widget.window.id, WindowSnapMode.leftHalf, screenSize);
                          } else if (preview.left > 0 && preview.height == availH) {
                            appState.snapWindow(widget.window.id, WindowSnapMode.rightHalf, screenSize);
                          } else if (preview.left == 0 && preview.top == topOffset) {
                            appState.snapWindow(widget.window.id, WindowSnapMode.topLeft, screenSize);
                          } else if (preview.left > 0 && preview.top == topOffset) {
                            appState.snapWindow(widget.window.id, WindowSnapMode.topRight, screenSize);
                          } else if (preview.left == 0 && preview.top > topOffset) {
                            appState.snapWindow(widget.window.id, WindowSnapMode.bottomLeft, screenSize);
                          } else if (preview.left > 0 && preview.top > topOffset) {
                            appState.snapWindow(widget.window.id, WindowSnapMode.bottomRight, screenSize);
                          }
                        }
                      },
                      child: WindowTitleBar(
                        title: widget.window.title,
                        icon: widget.window.icon,
                        windowId: widget.window.id,
                        isActive: isActive,
                      ),
                    ),

                    // Window Body (Fully Interactive)
                    Expanded(
                      child: Container(
                        color: colorScheme.surface,
                        child: widget.window.child,
                      ),
                    ),
                  ],
                ),

                // 8-Point Interactive Resizing Border Handles
                _buildResizeHandles(appState),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildResizeHandles(AppState appState) {
    const handleSize = 8.0;

    return Stack(
      children: [
        // Right Edge
        Positioned(
          top: handleSize,
          bottom: handleSize,
          right: 0,
          width: handleSize,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeLeftRight,
            onDrag: (dx, dy) {
              appState.resizeWindow(
                widget.window.id,
                newSize: Size(widget.window.size.width + dx, widget.window.size.height),
              );
            },
          ),
        ),
        // Bottom Edge
        Positioned(
          left: handleSize,
          right: handleSize,
          bottom: 0,
          height: handleSize,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeUpDown,
            onDrag: (dx, dy) {
              appState.resizeWindow(
                widget.window.id,
                newSize: Size(widget.window.size.width, widget.window.size.height + dy),
              );
            },
          ),
        ),
        // Left Edge
        Positioned(
          top: handleSize,
          bottom: handleSize,
          left: 0,
          width: handleSize,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeLeftRight,
            onDrag: (dx, dy) {
              final newW = widget.window.size.width - dx;
              if (newW >= 400) {
                appState.resizeWindow(
                  widget.window.id,
                  newSize: Size(newW, widget.window.size.height),
                  newPos: widget.window.position + Offset(dx, 0),
                );
              }
            },
          ),
        ),
        // Top Edge
        Positioned(
          left: handleSize,
          right: handleSize,
          top: 0,
          height: handleSize,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeUpDown,
            onDrag: (dx, dy) {
              final newH = widget.window.size.height - dy;
              if (newH >= 300) {
                appState.resizeWindow(
                  widget.window.id,
                  newSize: Size(widget.window.size.width, newH),
                  newPos: widget.window.position + Offset(0, dy),
                );
              }
            },
          ),
        ),
        // Bottom-Right Corner
        Positioned(
          right: 0,
          bottom: 0,
          width: handleSize * 2,
          height: handleSize * 2,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeUpLeftDownRight,
            onDrag: (dx, dy) {
              appState.resizeWindow(
                widget.window.id,
                newSize: Size(widget.window.size.width + dx, widget.window.size.height + dy),
              );
            },
          ),
        ),
        // Bottom-Left Corner
        Positioned(
          left: 0,
          bottom: 0,
          width: handleSize * 2,
          height: handleSize * 2,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeUpRightDownLeft,
            onDrag: (dx, dy) {
              final newW = widget.window.size.width - dx;
              if (newW >= 400) {
                appState.resizeWindow(
                  widget.window.id,
                  newSize: Size(newW, widget.window.size.height + dy),
                  newPos: widget.window.position + Offset(dx, 0),
                );
              }
            },
          ),
        ),
        // Top-Right Corner
        Positioned(
          right: 0,
          top: 0,
          width: handleSize * 2,
          height: handleSize * 2,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeUpRightDownLeft,
            onDrag: (dx, dy) {
              final newH = widget.window.size.height - dy;
              if (newH >= 300) {
                appState.resizeWindow(
                  widget.window.id,
                  newSize: Size(widget.window.size.width + dx, newH),
                  newPos: widget.window.position + Offset(0, dy),
                );
              }
            },
          ),
        ),
        // Top-Left Corner
        Positioned(
          left: 0,
          top: 0,
          width: handleSize * 2,
          height: handleSize * 2,
          child: _ResizeHandle(
            cursor: SystemMouseCursors.resizeUpLeftDownRight,
            onDrag: (dx, dy) {
              final newW = widget.window.size.width - dx;
              final newH = widget.window.size.height - dy;
              if (newW >= 400 && newH >= 300) {
                appState.resizeWindow(
                  widget.window.id,
                  newSize: Size(newW, newH),
                  newPos: widget.window.position + Offset(dx, dy),
                );
              }
            },
          ),
        ),
      ],
    );
  }
}

class _ResizeHandle extends StatelessWidget {
  final MouseCursor cursor;
  final Function(double dx, double dy) onDrag;

  const _ResizeHandle({required this.cursor, required this.onDrag});

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: cursor,
      child: GestureDetector(
        onPanUpdate: (details) => onDrag(details.delta.dx, details.delta.dy),
        child: Container(color: Colors.transparent),
      ),
    );
  }
}
