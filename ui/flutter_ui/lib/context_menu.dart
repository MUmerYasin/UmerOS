import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;

const String _backendBase = 'http://127.0.0.1:5000';

/// Manages clipboard state for copy/cut/paste operations.
///
/// This is a lightweight ChangeNotifier that tracks the current
/// clipboard contents and mode (copy vs cut) across the desktop.
/// It does NOT store file data — it stores paths and the operation type
/// so that paste operations can delegate to the backend.
class ClipboardManager extends ChangeNotifier {
  /// The path(s) currently on the clipboard, if any.
  List<String> _paths = [];

  /// The operation type: null = empty, 'copy', 'cut'.
  String? _operation;

  /// True while a cut operation is pending (visual indicator on source).
  bool get hasSelection => _operation != null && _paths.isNotEmpty;

  /// The currently copied/cut paths.
  List<String> get paths => List.unmodifiable(_paths);

  /// The current operation: 'copy', 'cut', or null.
  String? get operation => _operation;

  /// True if clipboard is non-empty.
  bool get isNotEmpty => _paths.isNotEmpty;

  /// Put paths on the clipboard with the given operation.
  void copy(List<String> paths) {
    _paths = List.of(paths);
    _operation = 'copy';
    notifyListeners();
  }

  /// Cut puts paths on the clipboard and marks them as "moving".
  void cut(List<String> paths) {
    _paths = List.of(paths);
    _operation = 'cut';
    notifyListeners();
  }

  /// Clear the clipboard.
  void clear() {
    _paths = [];
    _operation = null;
    notifyListeners();
  }

  /// Paste the current clipboard to the given destination path via the backend.
  Future<void> pasteTo(String destPath) async {
    if (!isNotEmpty) return;
    try {
      await http.post(
        Uri.parse('$_backendBase/clipboard_paste'),
        body: {
          'operation': _operation,
          'paths': _paths.join('\n'),
          'destination': destPath,
        },
      );
      if (_operation == 'cut') {
        clear();
      }
    } catch (_) {
      // Backend may not be running; degrade silently.
    }
  }
}

/// A widget that intercepts right-clicks and shows a Windows-like context menu.
///
/// Wraps [child] and shows a popup menu on secondary mouse button.
/// Clipboard operations (Copy, Cut, Paste) are managed via [ClipboardManager]
/// which must be provided higher in the tree (via [Provider]).
class RightClickArea extends StatelessWidget {
  final Widget child;

  const RightClickArea({super.key, required this.child});

  // ── Backend action dispatch ──────────────────────────────────────────

  Future<void> _performAction(BuildContext context, String action) async {
    switch (action) {
      case 'refresh':
        await http.post(Uri.parse('$_backendBase/refresh'));
        break;
      case 'new_folder':
        await http.post(
          Uri.parse('$_backendBase/new_folder'),
          body: {'name': 'new_folder'},
        );
        break;
      case 'sort_name':
        await http.post(Uri.parse('$_backendBase/sort'), body: {'by': 'name'});
        break;
      case 'sort_size':
        await http.post(Uri.parse('$_backendBase/sort'), body: {'by': 'size'});
        break;
      case 'sort_date':
        await http.post(Uri.parse('$_backendBase/sort'), body: {'by': 'date'});
        break;
      case 'sort_type':
        await http.post(Uri.parse('$_backendBase/sort'), body: {'by': 'type'});
        break;
      case 'icon_small':
        await http.post(Uri.parse('$_backendBase/icon_size'),
            body: {'size': 'small'});
        break;
      case 'icon_medium':
        await http.post(Uri.parse('$_backendBase/icon_size'),
            body: {'size': 'medium'});
        break;
      case 'icon_large':
        await http.post(Uri.parse('$_backendBase/icon_size'),
            body: {'size': 'large'});
        break;
      case 'run_admin':
        await http.post(Uri.parse('$_backendBase/run_as_admin'),
            body: {'command': 'whoami'});
        break;
      case 'copy':
        _copySelection(context);
        return; // Don't show snackbar for copy
      case 'cut':
        _cutSelection(context);
        return;
      case 'paste':
        _pasteClipboard(context);
        return;
    }
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Action "$action" executed')),
      );
    }
  }

  // ── Clipboard helpers ────────────────────────────────────────────────

  ClipboardManager? _clipboard(BuildContext context) {
    try {
      return context.read<ClipboardManager>();
    } catch (_) {
      return null;
    }
  }

  void _copySelection(BuildContext context) {
    final cm = _clipboard(context);
    if (cm != null) {
      cm.copy(['/desktop/selected']); // Placeholder — real selection would come from active window
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Copied to clipboard')),
      );
    }
  }

  void _cutSelection(BuildContext context) {
    final cm = _clipboard(context);
    if (cm != null) {
      cm.cut(['/desktop/selected']);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Cut to clipboard')),
      );
    }
  }

  void _pasteClipboard(BuildContext context) {
    final cm = _clipboard(context);
    if (cm != null && cm.isNotEmpty) {
      cm.pasteTo('/desktop');
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pasted from clipboard')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Clipboard is empty')),
      );
    }
  }

  // ── Menu tree ────────────────────────────────────────────────────────

  Future<void> _showMenu(BuildContext context, Offset position) async {
    final selected = await showMenu<String>(
      context: context,
      position: RelativeRect.fromLTRB(
        position.dx,
        position.dy,
        position.dx,
        position.dy,
      ),
      items: _buildMenuItems(context),
    );
    if (selected != null) {
      await _performAction(context, selected);
    }
  }

  List<PopupMenuEntry<String>> _buildMenuItems(BuildContext context) {
    final cm = _clipboard(context);
    final hasPaste = cm != null && cm.isNotEmpty;

    return <PopupMenuEntry<String>>[
      // ── View submenu ────────────────────────────────────────────────
      PopupMenuItem<String>(
        value: '__view__',
        enabled: false,
        child: Text(
          'View',
          style: TextStyle(
            fontWeight: FontWeight.w600,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
      ),
      const PopupMenuDivider(),
      _submenuItem<String>(
        context: context,
        label: 'Sort by',
        icon: Icons.sort,
        children: [
          const PopupMenuItem(value: 'sort_name', child: Text('Name')),
          const PopupMenuItem(value: 'sort_size', child: Text('Size')),
          const PopupMenuItem(value: 'sort_date', child: Text('Date modified')),
          const PopupMenuItem(value: 'sort_type', child: Text('Type')),
        ],
      ),
      _submenuItem<String>(
        context: context,
        label: 'Icon size',
        icon: Icons.photo_size_select_large,
        children: [
          const PopupMenuItem(value: 'icon_small', child: Text('Small')),
          const PopupMenuItem(value: 'icon_medium', child: Text('Medium')),
          const PopupMenuItem(value: 'icon_large', child: Text('Large')),
        ],
      ),

      const PopupMenuDivider(),

      // ── Clipboard actions ───────────────────────────────────────────
      PopupMenuItem<String>(
        value: 'copy',
        enabled: true,
        child: Row(
          children: [
            const Icon(Icons.copy, size: 18),
            const SizedBox(width: 8),
            const Text('Copy'),
            const Spacer(),
            Text(
              'Ctrl+C',
              style: TextStyle(
                fontSize: 11,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      ),
      PopupMenuItem<String>(
        value: 'cut',
        enabled: true,
        child: Row(
          children: [
            const Icon(Icons.content_cut, size: 18),
            const SizedBox(width: 8),
            const Text('Cut'),
            const Spacer(),
            Text(
              'Ctrl+X',
              style: TextStyle(
                fontSize: 11,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      ),
      PopupMenuItem<String>(
        value: 'paste',
        enabled: hasPaste,
        child: Row(
          children: [
            Icon(Icons.paste, size: 18,
                color: hasPaste ? null : Colors.grey),
            const SizedBox(width: 8),
            Text('Paste',
                style: TextStyle(
                    color: hasPaste ? null : Colors.grey)),
            const Spacer(),
            Text(
              'Ctrl+V',
              style: TextStyle(
                fontSize: 11,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      ),

      const PopupMenuDivider(),

      // ── System actions ──────────────────────────────────────────────
      PopupMenuItem<String>(
        value: 'new_folder',
        child: Row(
          children: [
            const Icon(Icons.create_new_folder, size: 18),
            const SizedBox(width: 8),
            const Text('New folder'),
          ],
        ),
      ),
      PopupMenuItem<String>(
        value: 'refresh',
        child: Row(
          children: [
            const Icon(Icons.refresh, size: 18),
            const SizedBox(width: 8),
            const Text('Refresh'),
          ],
        ),
      ),

      const PopupMenuDivider(),

      PopupMenuItem<String>(
        value: 'run_admin',
        child: Row(
          children: [
            const Icon(Icons.admin_panel_settings, size: 18),
            const SizedBox(width: 8),
            const Text('Run as Administrator'),
          ],
        ),
      ),
    ];
  }

  /// Helper: builds a [PopupMenuEntry] that opens a nested submenu.
  PopupMenuItem<T> _submenuItem<T>({
    required BuildContext context,
    required String label,
    required IconData icon,
    required List<PopupMenuEntry<T>> children,
  }) {
    return PopupMenuItem<T>(
      enabled: true,
      child: PopupMenuButton<T>(
        onSelected: (value) {
          // Forward the selected value up as a string action.
          _performAction(context, value as String);
        },
        offset: const Offset(200, 0),
        itemBuilder: (_) => children,
        child: Row(
          children: [
            Icon(icon, size: 18),
            const SizedBox(width: 8),
            Text(label),
            const Spacer(),
            const Icon(Icons.chevron_right, size: 16),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (event) {
        if (event.kind == PointerDeviceKind.mouse &&
            event.buttons == kSecondaryMouseButton) {
          _showMenu(context, event.position);
        }
      },
      child: child,
    );
  }
}
