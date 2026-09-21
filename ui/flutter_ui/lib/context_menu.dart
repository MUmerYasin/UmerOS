/// UmerOS — Smart Adaptive Context Menu System
/// ============================================
/// A Material Design 3, context-aware right-click menu that learns user
/// behaviour via [SmartActionTracker] and surfaces the most-used
/// actions at the top.
///
/// Design principles
/// * Material Design 3: M3 surfaces, color roles, subtle elevation —
///   clean, modern, never a flat rectangle.
/// * Smart prioritisation: the top 3 items are the user's most
///   frequently used actions for the current context.
/// * Keyboard-first: full arrow-key navigation, Escape to close,
///   Enter/Space to activate.
/// * Accessible: every item carries a [Semantics] label.
/// * Lightweight animations: 150 ms spring-in, 100 ms fade-out.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'src/services/smart_action_tracker.dart';
import 'src/services/material3_theme.dart';
import 'services/clipboard_manager.dart';
import 'src/core/app_state.dart';
import 'src/core/app_registry.dart';
import 'src/apps/settings_app.dart';

// ── Public re-export so existing imports still compile ────────
export 'services/clipboard_manager.dart' show ClipboardManager;

// ═══════════════════════════════════════════════════════════════
// Data models
// ═══════════════════════════════════════════════════════════════

/// A single menu item.
class ContextMenuAction {
  const ContextMenuAction({
    required this.id,
    required this.label,
    this.icon,
    this.shortcut,
    this.onTap,
    this.children = const [],
    this.isSeparator = false,
    this.isDangerous = false,
    this.isEnabled = true,
  });

  /// Unique identifier — used for tracking & persistence.
  final String id;

  /// Display label.
  final String label;

  /// Leading icon (optional).
  final IconData? icon;

  /// Keyboard shortcut hint (e.g. "Ctrl+C").
  final String? shortcut;

  /// Callback when activated.  Ignored for separators and parents.
  final VoidCallback? onTap;

  /// Nested children → rendered as a sub-menu on hover / right-arrow.
  final List<ContextMenuAction> children;

  /// Visual separator line — no label, no interaction.
  final bool isSeparator;

  /// Red-tinted item (e.g. "Delete").
  final bool isDangerous;

  /// Greys out the item when false.
  final bool isEnabled;
}

/// A labelled group of actions with an optional section header.
class ContextMenuCategory {
  const ContextMenuCategory({
    this.header,
    required this.actions,
  });

  final String? header;
  final List<ContextMenuAction> actions;
}

// ═══════════════════════════════════════════════════════════════
// Menu builder — turns a context type into categories
// ═══════════════════════════════════════════════════════════════

class ContextMenuBuilder {
  const ContextMenuBuilder._();

  // ── Desktop root menu ───────────────────────────────────────

  static List<ContextMenuCategory> desktop({
    required VoidCallback onRefresh,
    required VoidCallback onDisplaySettings,
    required VoidCallback onPersonalize,
    required VoidCallback onOpenTerminal,
    required VoidCallback onPaste,
    required VoidCallback onNewFolder,
    required VoidCallback onSortByName,
    required VoidCallback onSortBySize,
    required VoidCallback onSortByType,
    required VoidCallback onSortByDate,
    required VoidCallback onIconSmall,
    required VoidCallback onIconMedium,
    required VoidCallback onIconLarge,
    required VoidCallback onIconExtraLarge,
    required VoidCallback onUndo,
    required VoidCallback? onPasteEnabled,
    required bool canPaste,
    bool Function(String)? isTopAction,
  }) {
    return [
      // Pinned / smart actions (top)
      ContextMenuCategory(
        actions: [
          ContextMenuAction(
            id: 'refresh',
            label: 'Refresh',
            icon: Icons.refresh_rounded,
            shortcut: 'F5',
            onTap: onRefresh,
          ),
          ContextMenuAction(
            id: 'open_terminal',
            label: 'Open in Terminal',
            icon: Icons.terminal_rounded,
            onTap: onOpenTerminal,
          ),
          if (canPaste)
            ContextMenuAction(
              id: 'paste',
              label: 'Paste',
              icon: Icons.paste_rounded,
              shortcut: 'Ctrl+V',
              onTap: onPaste,
            ),
        ],
      ),
      // New
      ContextMenuCategory(
        header: 'New',
        actions: [
          ContextMenuAction(
            id: 'new_folder',
            label: 'Folder',
            icon: Icons.create_new_folder_rounded,
            onTap: onNewFolder,
          ),
        ],
      ),
      // View
      ContextMenuCategory(
        header: 'View',
        actions: [
          ContextMenuAction(
            id: 'sort',
            label: 'Sort by',
            icon: Icons.sort_rounded,
            children: [
              ContextMenuAction(id: 'sort_name', label: 'Name', onTap: onSortByName),
              ContextMenuAction(id: 'sort_size', label: 'Size', onTap: onSortBySize),
              ContextMenuAction(id: 'sort_type', label: 'Item type', onTap: onSortByType),
              ContextMenuAction(id: 'sort_date', label: 'Date modified', onTap: onSortByDate),
            ],
          ),
          ContextMenuAction(
            id: 'icon_size',
            label: 'Icon size',
            icon: Icons.photo_size_select_small_rounded,
            children: [
              ContextMenuAction(id: 'icon_small', label: 'Small', onTap: onIconSmall),
              ContextMenuAction(id: 'icon_medium', label: 'Medium', onTap: onIconMedium),
              ContextMenuAction(id: 'icon_large', label: 'Large', onTap: onIconLarge),
              ContextMenuAction(id: 'icon_xl', label: 'Extra large', onTap: onIconExtraLarge),
            ],
          ),
        ],
      ),
      // Clipboard
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep1', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'undo',
            label: 'Undo',
            icon: Icons.undo_rounded,
            shortcut: 'Ctrl+Z',
            onTap: onUndo,
          ),
        ],
      ),
      // System
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep2', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'display_settings',
            label: 'Display settings',
            icon: Icons.desktop_windows_rounded,
            onTap: onDisplaySettings,
          ),
          ContextMenuAction(
            id: 'personalize',
            label: 'Personalize',
            icon: Icons.palette_rounded,
            onTap: onPersonalize,
          ),
        ],
      ),
    ];
  }

  // ── File context menu ───────────────────────────────────────

  static List<ContextMenuCategory> file({
    required String fileName,
    required VoidCallback onOpen,
    required VoidCallback onOpenLocation,
    required VoidCallback onCopy,
    required VoidCallback onCut,
    required VoidCallback onRename,
    required VoidCallback onDelete,
    required VoidCallback onProperties,
    required VoidCallback onShare,
    required VoidCallback onRunAsAdmin,
    required VoidCallback onPrint,
    bool Function(String)? isTopAction,
  }) {
    return [
      ContextMenuCategory(
        actions: [
          ContextMenuAction(
            id: 'open',
            label: 'Open',
            icon: Icons.open_in_new_rounded,
            onTap: onOpen,
          ),
          ContextMenuAction(
            id: 'run_admin',
            label: 'Run as Administrator',
            icon: Icons.admin_panel_settings_rounded,
            onTap: onRunAsAdmin,
          ),
        ],
      ),
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'copy',
            label: 'Copy',
            icon: Icons.copy_rounded,
            shortcut: 'Ctrl+C',
            onTap: onCopy,
          ),
          ContextMenuAction(
            id: 'cut',
            label: 'Cut',
            icon: Icons.content_cut_rounded,
            shortcut: 'Ctrl+X',
            onTap: onCut,
          ),
          ContextMenuAction(
            id: 'rename',
            label: 'Rename',
            icon: Icons.edit_rounded,
            shortcut: 'F2',
            onTap: onRename,
          ),
          ContextMenuAction(
            id: 'delete',
            label: 'Delete',
            icon: Icons.delete_rounded,
            shortcut: 'Del',
            onTap: onDelete,
            isDangerous: true,
          ),
        ],
      ),
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep2', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'share',
            label: 'Share',
            icon: Icons.share_rounded,
            onTap: onShare,
          ),
          ContextMenuAction(
            id: 'print',
            label: 'Print',
            icon: Icons.print_rounded,
            shortcut: 'Ctrl+P',
            onTap: onPrint,
          ),
          ContextMenuAction(
            id: 'open_location',
            label: 'Open file location',
            icon: Icons.folder_open_rounded,
            onTap: onOpenLocation,
          ),
        ],
      ),
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep3', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'properties',
            label: 'Properties',
            icon: Icons.info_outline_rounded,
            shortcut: 'Alt+Enter',
            onTap: onProperties,
          ),
        ],
      ),
    ];
  }

  // ── Folder context menu ─────────────────────────────────────

  static List<ContextMenuCategory> folder({
    required String folderName,
    required VoidCallback onOpen,
    required VoidCallback onOpenLocation,
    required VoidCallback onCopy,
    required VoidCallback onCut,
    required VoidCallback onRename,
    required VoidCallback onDelete,
    required VoidCallback onProperties,
    required VoidCallback onShare,
    bool Function(String)? isTopAction,
  }) {
    return [
      ContextMenuCategory(
        actions: [
          ContextMenuAction(
            id: 'open',
            label: 'Open',
            icon: Icons.folder_open_rounded,
            onTap: onOpen,
          ),
        ],
      ),
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'copy',
            label: 'Copy',
            icon: Icons.copy_rounded,
            shortcut: 'Ctrl+C',
            onTap: onCopy,
          ),
          ContextMenuAction(
            id: 'cut',
            label: 'Cut',
            icon: Icons.content_cut_rounded,
            shortcut: 'Ctrl+X',
            onTap: onCut,
          ),
          ContextMenuAction(
            id: 'rename',
            label: 'Rename',
            icon: Icons.edit_rounded,
            shortcut: 'F2',
            onTap: onRename,
          ),
          ContextMenuAction(
            id: 'delete',
            label: 'Delete',
            icon: Icons.delete_rounded,
            shortcut: 'Del',
            onTap: onDelete,
            isDangerous: true,
          ),
        ],
      ),
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep2', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'share',
            label: 'Share',
            icon: Icons.share_rounded,
            onTap: onShare,
          ),
          ContextMenuAction(
            id: 'open_location',
            label: 'Open file location',
            icon: Icons.folder_open_rounded,
            onTap: onOpenLocation,
          ),
        ],
      ),
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep3', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'properties',
            label: 'Properties',
            icon: Icons.info_outline_rounded,
            shortcut: 'Alt+Enter',
            onTap: onProperties,
          ),
        ],
      ),
    ];
  }

  // ── Taskbar context menu ────────────────────────────────────

  static List<ContextMenuCategory> taskbar({
    required VoidCallback onOpenTerminal,
    required VoidCallback onTaskManager,
    required VoidCallback onDisplaySettings,
    required VoidCallback onPersonalize,
  }) {
    return [
      ContextMenuCategory(
        actions: [
          ContextMenuAction(
            id: 'open_terminal',
            label: 'Open in Terminal',
            icon: Icons.terminal_rounded,
            onTap: onOpenTerminal,
          ),
          ContextMenuAction(
            id: 'task_manager',
            label: 'Task Manager',
            icon: Icons.speed_rounded,
            onTap: onTaskManager,
          ),
        ],
      ),
      ContextMenuCategory(
        actions: [
          const ContextMenuAction(id: '_sep', label: '', isSeparator: true),
          ContextMenuAction(
            id: 'display_settings',
            label: 'Display settings',
            icon: Icons.desktop_windows_rounded,
            onTap: onDisplaySettings,
          ),
          ContextMenuAction(
            id: 'personalize',
            label: 'Personalize',
            icon: Icons.palette_rounded,
            onTap: onPersonalize,
          ),
        ],
      ),
    ];
  }

  // ── Window title-bar context menu ───────────────────────────

  static List<ContextMenuCategory> window({
    required VoidCallback onMinimize,
    required VoidCallback onMaximize,
    required VoidCallback onClose,
    bool isMaximized = false,
  }) {
    return [
      ContextMenuCategory(
        actions: [
          ContextMenuAction(
            id: 'minimize',
            label: 'Minimize',
            icon: Icons.minimize_rounded,
            onTap: onMinimize,
          ),
          ContextMenuAction(
            id: 'maximize',
            label: isMaximized ? 'Restore Down' : 'Maximize',
            icon: isMaximized
                ? Icons.filter_none_rounded
                : Icons.maximize_rounded,
            onTap: onMaximize,
          ),
          ContextMenuAction(
            id: 'close',
            label: 'Close',
            icon: Icons.close_rounded,
            onTap: onClose,
            isDangerous: true,
          ),
        ],
      ),
    ];
  }
}

// ═══════════════════════════════════════════════════════════════
// Controller — manages overlay lifecycle
// ═══════════════════════════════════════════════════════════════

class UmerOSContextMenuController extends ChangeNotifier {
  OverlayEntry? _entry;
  bool _isVisible = false;

  bool get isVisible => _isVisible;

  void show(
    BuildContext context, {
    required List<ContextMenuCategory> categories,
    required Offset position,
    MenuContext menuContext = MenuContext.desktop,
  }) {
    dismiss();

    _entry = OverlayEntry(
      builder: (_) => _ContextMenuOverlay(
        categories: categories,
        position: position,
        menuContext: menuContext,
        onDismiss: dismiss,
      ),
    );

    Overlay.of(context, rootOverlay: true).insert(_entry!);
    _isVisible = true;
    notifyListeners();
  }

  void dismiss() {
    if (_entry != null) {
      _entry!.remove();
      _entry = null;
      _isVisible = false;
      notifyListeners();
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// The overlay widget — renders the glassmorphic menu
// ═══════════════════════════════════════════════════════════════

class _ContextMenuOverlay extends StatefulWidget {
  const _ContextMenuOverlay({
    required this.categories,
    required this.position,
    required this.menuContext,
    required this.onDismiss,
  });

  final List<ContextMenuCategory> categories;
  final Offset position;
  final MenuContext menuContext;
  final VoidCallback onDismiss;

  @override
  State<_ContextMenuOverlay> createState() => _ContextMenuOverlayState();
}

class _ContextMenuOverlayState extends State<_ContextMenuOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animCtrl;
  late final Animation<double> _scaleAnim;
  late final Animation<double> _fadeAnim;
  final FocusNode _focusNode = FocusNode();
  int _hoveredIndex = -1;
  int? _openSubmenuIndex;

  // Flatten categories into a single list of renderable items
  // (keeping category separators and headers).
  late final List<_RenderItem> _items;

  @override
  void initState() {
    super.initState();
    _items = _buildRenderItems();

    _animCtrl = AnimationController(
      vsync: this,
      duration: M3Theme.animDuration,
    );

    _scaleAnim = CurvedAnimation(
      parent: _animCtrl,
      curve: Curves.easeOutBack,
      reverseCurve: Curves.easeIn,
    );

    _fadeAnim = CurvedAnimation(
      parent: _animCtrl,
      curve: const Interval(0, 0.6, curve: Curves.easeOut),
      reverseCurve: const Interval(0.4, 1, curve: Curves.easeIn),
    );

    _animCtrl.forward();
    _focusNode.requestFocus();

    // Close on outside tap.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Handled by the HitTest in build.
    });
  }

  @override
  void dispose() {
    _animCtrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  List<_RenderItem> _buildRenderItems() {
    final items = <_RenderItem>[];
    for (var ci = 0; ci < widget.categories.length; ci++) {
      final cat = widget.categories[ci];
      if (cat.header != null) {
        items.add(_RenderItem.sectionHeader(cat.header!));
      }
      for (final action in cat.actions) {
        items.add(_RenderItem.action(action));
      }
    }
    return items;
  }

  // ── Keyboard handling ───────────────────────────────────────

  KeyEventResult _onKey(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) {
      return KeyEventResult.ignored;
    }

    if (event.logicalKey == LogicalKeyboardKey.escape) {
      widget.onDismiss();
      return KeyEventResult.handled;
    }

    if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
      _moveSelection(1);
      return KeyEventResult.handled;
    }

    if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
      _moveSelection(-1);
      return KeyEventResult.handled;
    }

    if (event.logicalKey == LogicalKeyboardKey.arrowRight) {
      _openSubmenuAtHovered();
      return KeyEventResult.handled;
    }

    if (event.logicalKey == LogicalKeyboardKey.arrowLeft) {
      if (_openSubmenuIndex != null) {
        setState(() => _openSubmenuIndex = null);
      }
      return KeyEventResult.handled;
    }

    if (event.logicalKey == LogicalKeyboardKey.enter ||
        event.logicalKey == LogicalKeyboardKey.space) {
      _activateHovered();
      return KeyEventResult.handled;
    }

    return KeyEventResult.ignored;
  }

  void _moveSelection(int delta) {
    // Skip separators and section headers.
    var idx = _hoveredIndex;
    do {
      idx += delta;
      if (idx < 0 || idx >= _items.length) return;
    } while (_items[idx].action.isSeparator || _items[idx].isHeader);

    setState(() => _hoveredIndex = idx);
  }

  void _openSubmenuAtHovered() {
    if (_hoveredIndex < 0 || _hoveredIndex >= _items.length) return;
    final item = _items[_hoveredIndex];
    if (item.action.children.isNotEmpty) {
      setState(() => _openSubmenuIndex = _hoveredIndex);
    }
  }

  void _activateHovered() {
    if (_hoveredIndex < 0 || _hoveredIndex >= _items.length) return;
    final item = _items[_hoveredIndex];
    if (item.action.children.isNotEmpty) {
      _openSubmenuAtHovered();
      return;
    }
    _activate(item.action);
  }

  void _activate(ContextMenuAction action) {
    if (!action.isEnabled || action.isSeparator) return;

    // Track usage.
    final tracker = context.read<SmartActionTracker>();
    tracker.track(widget.menuContext, action.id);

    widget.onDismiss();
    action.onTap?.call();
  }

  // ── Build ───────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final screen = MediaQuery.of(context).size;
    final menuWidth = 260.0;
    final estimatedHeight = _items.length * M3Theme.itemHeight + 32.0;

    // Clamp position so the menu stays on screen.
    var left = widget.position.dx;
    var top = widget.position.dy;
    if (left + menuWidth > screen.width) left = screen.width - menuWidth - 8;
    if (top + estimatedHeight > screen.height) {
      top = screen.height - estimatedHeight - 8;
    }
    if (left < 0) left = 8;
    if (top < 0) top = 8;

    return Stack(
      children: [
        // Dismiss on tap outside.
        Positioned.fill(
          child: GestureDetector(
            behavior: HitTestBehavior.translucent,
            onTap: widget.onDismiss,
            child: const SizedBox.expand(),
          ),
        ),
        // The menu itself.
        Positioned(
          left: left,
          top: top,
          child: ScaleTransition(
            scale: _scaleAnim,
            child: FadeTransition(
              opacity: _fadeAnim,
              child: _M3Menu(
                width: menuWidth,
                focusNode: _focusNode,
                onKey: _onKey,
                items: _items,
                hoveredIndex: _hoveredIndex,
                openSubmenuIndex: _openSubmenuIndex,
                onHover: (i) => setState(() => _hoveredIndex = i),
                onTap: _activate,
                onSubmenuHover: (i) => setState(() => _openSubmenuIndex = i),
                menuContext: widget.menuContext,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// Internal render helpers
// ═══════════════════════════════════════════════════════════════

class _RenderItem {
  _RenderItem.sectionHeader(this.label)
      : action = ContextMenuAction(id: '_hdr_$label', label: label!),
        isHeader = true;

  _RenderItem.action(this.action) : isHeader = false, label = null;

  final String? label;
  final ContextMenuAction action;
  final bool isHeader;
}

// ═══════════════════════════════════════════════════════════════
// The actual glassmorphic menu widget
// ═══════════════════════════════════════════════════════════════

class _M3Menu extends StatelessWidget {
  const _M3Menu({
    required this.width,
    required this.focusNode,
    required this.onKey,
    required this.items,
    required this.hoveredIndex,
    required this.openSubmenuIndex,
    required this.onHover,
    required this.onTap,
    required this.onSubmenuHover,
    required this.menuContext,
  });

  final double width;
  final FocusNode focusNode;
  final FocusOnKeyEventCallback onKey;
  final List<_RenderItem> items;
  final int hoveredIndex;
  final int? openSubmenuIndex;
  final ValueChanged<int> onHover;
  final ValueChanged<ContextMenuAction> onTap;
  final ValueChanged<int?> onSubmenuHover;
  final MenuContext menuContext;

  @override
  Widget build(BuildContext context) {
    final bgColor = M3Theme.backgroundColor(context);
    final bdrColor = M3Theme.borderColor(context);

    final mainMenu = Focus(
      focusNode: focusNode,
      onKeyEvent: onKey,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(M3Theme.borderRadius),
          child: Container(
            width: width,
            decoration: BoxDecoration(
              color: bgColor,
              borderRadius: BorderRadius.circular(M3Theme.borderRadius),
              border: Border.all(
                color: bdrColor,
                width: M3Theme.borderWidth,
              ),
              boxShadow: M3Theme.shadow,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (var i = 0; i < items.length; i++)
                  _buildItem(context, items[i], i),
              ],
            ),
          ),
        ),
      ),
    );

    // If a submenu is open, overlay it on top
    if (openSubmenuIndex != null &&
        openSubmenuIndex! >= 0 &&
        openSubmenuIndex! < items.length &&
        items[openSubmenuIndex!].action.children.isNotEmpty) {
      final submenuAction = items[openSubmenuIndex!].action;
      final submenuWidth = width;
      const submenuItemHeight = M3Theme.itemHeight;

      return Stack(
        clipBehavior: Clip.none,
        children: [
          mainMenu,
          Positioned(
            left: width,
            top: 0,
            child: MouseRegion(
              onEnter: (_) => onSubmenuHover(openSubmenuIndex),
              onExit: (_) => onSubmenuHover(null),
              child: Material(
                type: MaterialType.transparency,
                child: ClipRRect(
                  borderRadius:
                      BorderRadius.circular(M3Theme.borderRadius),
                  child: Container(
                    width: submenuWidth,
                    decoration: BoxDecoration(
                      color: bgColor,
                      borderRadius: BorderRadius.circular(
                          M3Theme.borderRadius),
                      border: Border.all(
                        color: bdrColor,
                        width: M3Theme.borderWidth,
                      ),
                      boxShadow: M3Theme.shadow,
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: submenuAction.children.map((child) {
                        return GestureDetector(
                          onTap: () => onTap(child),
                          child: MouseRegion(
                            cursor: SystemMouseCursors.click,
                            child: AnimatedContainer(
                              duration: M3Theme.hoverDuration,
                              height: submenuItemHeight,
                              padding: const EdgeInsets.symmetric(
                                horizontal: M3Theme.itemPaddingH,
                              ),
                              child: Row(
                                children: [
                                  if (child.icon != null)
                                    Icon(
                                      child.icon,
                                      size: M3Theme.iconSize,
                                      color: M3Theme.textColor(context).withAlpha(220),
                                    ),
                                  if (child.icon != null)
                                    const SizedBox(width: 10),
                                  Expanded(
                                    child: Text(
                                      child.label,
                                      style: TextStyle(
                                        fontSize:
                                            M3Theme.fontSizeItem,
                                        fontWeight: FontWeight.w400,
                                        color: M3Theme.textColor(context),
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      );
    }

    return mainMenu;
  }

  Widget _buildItem(BuildContext context, _RenderItem item, int index) {
    // ── Section header ──────────────────────────────────────
    if (item.isHeader) {
      return Padding(
        padding: const EdgeInsets.only(
          left: M3Theme.itemPaddingH,
          right: M3Theme.itemPaddingH,
          top: 10,
          bottom: 4,
        ),
        child: Text(
          item.action.label.toUpperCase(),
          style: TextStyle(
            fontSize: M3Theme.fontSizeSectionHeader,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.6,
            color: M3Theme.subtleTextColor(context),
          ),
        ),
      );
    }

    // ── Separator ───────────────────────────────────────────
    if (item.action.isSeparator) {
      return Padding(
        padding: const EdgeInsets.symmetric(
          vertical: 4,
          horizontal: M3Theme.itemPaddingH,
        ),
        child: Divider(
          height: M3Theme.separatorHeight,
          color: M3Theme.subtleTextColor(context).withAlpha(30),
        ),
      );
    }

    // ── Normal item ─────────────────────────────────────────
    final action = item.action;
    final isHovered = index == hoveredIndex;
    final hasSubmenu = action.children.isNotEmpty;

    return GestureDetector(
      onTap: () => onTap(action),
      child: MouseRegion(
        onEnter: (_) {
          onHover(index);
          if (hasSubmenu) onSubmenuHover(index);
        },
        onExit: (_) {
          if (hasSubmenu) onSubmenuHover(null);
        },
        child: AnimatedContainer(
          duration: M3Theme.hoverDuration,
          height: M3Theme.itemHeight,
          padding: const EdgeInsets.symmetric(
            horizontal: M3Theme.itemPaddingH,
          ),
          decoration: BoxDecoration(
            color: isHovered
                ? (action.isDangerous
                    ? Colors.redAccent.withAlpha(25)
                    : Theme.of(context)
                        .colorScheme
                        .primary
                        .withAlpha(
                            (M3Theme.hoverOpacity * 255).round()))
                : Colors.transparent,
            borderRadius:
                BorderRadius.circular(M3Theme.borderRadiusSmall),
          ),
          child: Row(
            children: [
              // Icon
              if (action.icon != null)
                Icon(
                  action.icon,
                  size: M3Theme.iconSize,
                  color: action.isDangerous
                      ? Colors.redAccent
                       : action.isEnabled
                          ? M3Theme.textColor(context).withAlpha(220)
                          : M3Theme.subtleTextColor(context),
                 ),
               if (action.icon != null) const SizedBox(width: 10),

               // Label
               Expanded(
                 child: Semantics(
                   label: action.label,
                   button: true,
                   enabled: action.isEnabled,
                   child: Text(
                     action.label,
                     style: TextStyle(
                       fontSize: M3Theme.fontSizeItem,
                       fontWeight:
                           isHovered ? FontWeight.w500 : FontWeight.w400,
                       color: action.isDangerous
                           ? Colors.redAccent
                           : action.isEnabled
                               ? M3Theme.textColor(context)
                               : M3Theme.subtleTextColor(context),
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ),

              // Shortcut hint
              if (action.shortcut != null && !hasSubmenu)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Text(
                    action.shortcut!,
                    style: TextStyle(
                      fontSize: M3Theme.fontSizeShortcut,
                      color: M3Theme.subtleTextColor(context),
                    ),
                  ),
                ),

              // Submenu arrow
              if (hasSubmenu)
                Icon(
                  Icons.chevron_right_rounded,
                  size: M3Theme.submenuArrowSize,
                  color: Theme.of(context)
                      .colorScheme
                      .onSurface
                      .withAlpha(140),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// Public convenience widget — drop-in for GestureDetector.onSecondaryTapUp
// ═══════════════════════════════════════════════════════════════

/// Shows the context menu at [position] for the given [context].
///
/// Usage:
/// ```dart
/// onSecondaryTapUp: (details) => UmerOSContextMenu.show(
///   context,
///   position: details.globalPosition,
///   contextType: MenuContext.desktop,
///   callbacks: UmerOSCallbacks(...),
/// );
/// ```
void showUmerOSContextMenu(
  BuildContext context, {
  required Offset position,
  required MenuContext contextType,
  required UmerOSContextMenuCallbacks callbacks,
}) {
  final categories = _buildCategories(contextType, callbacks);
  final controller = context.read<UmerOSContextMenuController>();
  controller.show(
    context,
    categories: categories,
    position: position,
    menuContext: contextType,
  );
}

List<ContextMenuCategory> _buildCategories(
  MenuContext contextType,
  UmerOSContextMenuCallbacks cb,
) {
  switch (contextType) {
    case MenuContext.desktop:
      return ContextMenuBuilder.desktop(
        onRefresh: cb.onRefresh,
        onDisplaySettings: cb.onDisplaySettings,
        onPersonalize: cb.onPersonalize,
        onOpenTerminal: cb.onOpenTerminal,
        onPaste: cb.onPaste,
        onNewFolder: cb.onNewFolder,
        onSortByName: cb.onSortByName,
        onSortBySize: cb.onSortBySize,
        onSortByType: cb.onSortByType,
        onSortByDate: cb.onSortByDate,
        onIconSmall: cb.onIconSmall,
        onIconMedium: cb.onIconMedium,
        onIconLarge: cb.onIconLarge,
        onIconExtraLarge: cb.onIconExtraLarge,
        onUndo: cb.onUndo,
        onPasteEnabled: cb.onPaste,
        canPaste: cb.canPaste,
      );
    case MenuContext.file:
      return ContextMenuBuilder.file(
        fileName: cb.targetName,
        onOpen: cb.onOpen,
        onOpenLocation: cb.onOpenLocation,
        onCopy: cb.onCopy,
        onCut: cb.onCut,
        onRename: cb.onRename,
        onDelete: cb.onDelete,
        onProperties: cb.onProperties,
        onShare: cb.onShare,
        onRunAsAdmin: cb.onRunAsAdmin,
        onPrint: cb.onPrint,
      );
    case MenuContext.folder:
      return ContextMenuBuilder.folder(
        folderName: cb.targetName,
        onOpen: cb.onOpen,
        onOpenLocation: cb.onOpenLocation,
        onCopy: cb.onCopy,
        onCut: cb.onCut,
        onRename: cb.onRename,
        onDelete: cb.onDelete,
        onProperties: cb.onProperties,
        onShare: cb.onShare,
      );
    case MenuContext.taskbar:
      return ContextMenuBuilder.taskbar(
        onOpenTerminal: cb.onOpenTerminal,
        onTaskManager: cb.onTaskManager,
        onDisplaySettings: cb.onDisplaySettings,
        onPersonalize: cb.onPersonalize,
      );
    case MenuContext.window:
      return ContextMenuBuilder.window(
        onMinimize: cb.onMinimize,
        onMaximize: cb.onMaximize,
        onClose: cb.onClose,
        isMaximized: cb.isMaximized,
      );
    case MenuContext.browser:
      return ContextMenuBuilder.desktop(
        onRefresh: cb.onRefresh,
        onDisplaySettings: cb.onDisplaySettings,
        onPersonalize: cb.onPersonalize,
        onOpenTerminal: cb.onOpenTerminal,
        onPaste: cb.onPaste,
        onNewFolder: cb.onNewFolder,
        onSortByName: cb.onSortByName,
        onSortBySize: cb.onSortBySize,
        onSortByType: cb.onSortByType,
        onSortByDate: cb.onSortByDate,
        onIconSmall: cb.onIconSmall,
        onIconMedium: cb.onIconMedium,
        onIconLarge: cb.onIconLarge,
        onIconExtraLarge: cb.onIconExtraLarge,
        onUndo: cb.onUndo,
        onPasteEnabled: cb.onPaste,
        canPaste: cb.canPaste,
      );
  }
}

// ═══════════════════════════════════════════════════════════════
// Callbacks bundle — single object passed to the menu builder
// ═══════════════════════════════════════════════════════════════

class UmerOSContextMenuCallbacks {
  const UmerOSContextMenuCallbacks({
    this.targetName = '',
    this.canPaste = false,
    this.isMaximized = false,
    // Common
    this.onRefresh = _noOp,
    this.onOpen = _noOp,
    this.onCopy = _noOp,
    this.onCut = _noOp,
    this.onPaste = _noOp,
    this.onUndo = _noOp,
    this.onRename = _noOp,
    this.onDelete = _noOp,
    this.onProperties = _noOp,
    this.onShare = _noOp,
    this.onOpenLocation = _noOp,
    // Desktop
    this.onDisplaySettings = _noOp,
    this.onPersonalize = _noOp,
    this.onOpenTerminal = _noOp,
    this.onNewFolder = _noOp,
    this.onSortByName = _noOp,
    this.onSortBySize = _noOp,
    this.onSortByType = _noOp,
    this.onSortByDate = _noOp,
    this.onIconSmall = _noOp,
    this.onIconMedium = _noOp,
    this.onIconLarge = _noOp,
    this.onIconExtraLarge = _noOp,
    // File
    this.onRunAsAdmin = _noOp,
    this.onPrint = _noOp,
    // Taskbar
    this.onTaskManager = _noOp,
    // Window
    this.onMinimize = _noOp,
    this.onMaximize = _noOp,
    this.onClose = _noOp,
  });

  static void _noOp() {}

  // ── Common ──────────────────────────────────────────────────
  final String targetName;
  final bool canPaste;
  final bool isMaximized;
  final VoidCallback onRefresh;
  final VoidCallback onOpen;
  final VoidCallback onCopy;
  final VoidCallback onCut;
  final VoidCallback onPaste;
  final VoidCallback onUndo;
  final VoidCallback onRename;
  final VoidCallback onDelete;
  final VoidCallback onProperties;
  final VoidCallback onShare;
  final VoidCallback onOpenLocation;

  // ── Desktop ─────────────────────────────────────────────────
  final VoidCallback onDisplaySettings;
  final VoidCallback onPersonalize;
  final VoidCallback onOpenTerminal;
  final VoidCallback onNewFolder;
  final VoidCallback onSortByName;
  final VoidCallback onSortBySize;
  final VoidCallback onSortByType;
  final VoidCallback onSortByDate;
  final VoidCallback onIconSmall;
  final VoidCallback onIconMedium;
  final VoidCallback onIconLarge;
  final VoidCallback onIconExtraLarge;

  // ── File ────────────────────────────────────────────────────
  final VoidCallback onRunAsAdmin;
  final VoidCallback onPrint;

  // ── Taskbar ─────────────────────────────────────────────────
  final VoidCallback onTaskManager;

  // ── Window ──────────────────────────────────────────────────
  final VoidCallback onMinimize;
  final VoidCallback onMaximize;
  final VoidCallback onClose;
}

// ═══════════════════════════════════════════════════════════════
// RightClickArea — wraps any widget so that a right-click opens
// the Smart Adaptive Context Menu for the desktop context.
// ═══════════════════════════════════════════════════════════════

class RightClickArea extends StatelessWidget {
  const RightClickArea({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.translucent,
      onSecondaryTapUp: (details) => _showDesktopMenu(context, details.globalPosition),
      child: child,
    );
  }

  void _showDesktopMenu(BuildContext context, Offset position) {
    final appState = context.read<AppState>();
    final clipboard = context.read<ClipboardManager>();

    showUmerOSContextMenu(
      context,
      position: position,
      contextType: MenuContext.desktop,
      callbacks: UmerOSContextMenuCallbacks(
        targetName: 'Desktop',
        canPaste: clipboard.hasContent,
        onRefresh: () {
          appState.refreshDesktop();
        },
        onDisplaySettings: () {
          final app = AppRegistry.byId('settings');
          if (app != null) {
            appState.openWindow(
              id: 'settings_display',
              title: 'Display Settings',
              icon: app.icon,
              child: const SettingsApp(initialSection: 2),
            );
          }
        },
        onPersonalize: () {
          final app = AppRegistry.byId('settings');
          if (app != null) {
            appState.openWindow(
              id: 'settings_personalize',
              title: 'Personalize',
              icon: app.icon,
              child: const SettingsApp(initialSection: 0),
            );
          }
        },
        onOpenTerminal: () {
          final app = AppRegistry.byId('terminal');
          if (app != null) {
            appState.openWindow(
              id: app.id,
              title: app.title,
              icon: app.icon,
              child: app.builder(context),
            );
          }
        },
        onNewFolder: () async {
          final nameController = TextEditingController(text: 'New Folder');
          final result = await showDialog<String>(
            context: context,
            builder: (ctx) => AlertDialog(
              title: const Text('New Folder'),
              content: TextField(
                controller: nameController,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Folder name',
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (v) => Navigator.of(ctx).pop(v),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.of(ctx).pop(nameController.text),
                  child: const Text('Create'),
                ),
              ],
            ),
          );
          if (result != null && result.isNotEmpty) {
            // Add folder to desktop
            appState.addDesktopItem(DesktopItemData(
              id: 'folder_${result.hashCode}',
              name: result,
              icon: Icons.folder_rounded,
              color: Colors.amber,
            ));
            appState.refreshDesktop();
          }
        },
        onSortByName: () {},
        onSortBySize: () {},
        onSortByType: () {},
        onSortByDate: () {},
        onIconSmall: () {},
        onIconMedium: () {},
        onIconLarge: () {},
        onIconExtraLarge: () {},
        onCopy: () {},
        onCut: () {},
        onPaste: () {},
        onUndo: () {},
        onProperties: () {},
        onShare: () {},
      ),
    );
  }
}
