// lib/context_menu.dart
import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart'; // for PointerDeviceKind and mouse button constants
import 'package:http/http.dart' as http;

class RightClickArea extends StatelessWidget {
  final Widget child;
  const RightClickArea({Key? key, required this.child}) : super(key: key);

  // Helper to perform the selected action and then show a snackbar safely.
  Future<void> _performAction(BuildContext context, String selected) async {
    // Perform the HTTP call without holding onto the BuildContext.
    switch (selected) {
      case 'refresh':
        await http.post(Uri.parse('http://127.0.0.1:5000/refresh'));
        break;
      case 'new_folder':
        await http.post(Uri.parse('http://127.0.0.1:5000/new_folder'),
            body: {'name': 'new_folder'});
        break;
      case 'sort':
        await http.post(Uri.parse('http://127.0.0.1:5000/sort'),
            body: {'by': 'name'});
        break;
      case 'icon_size':
        await http.post(Uri.parse('http://127.0.0.1:5000/icon_size'),
            body: {'size': 'medium'});
        break;
      case 'run_admin':
        await http.post(Uri.parse('http://127.0.0.1:5000/run_as_admin'),
            body: {'command': 'whoami'});
        break;
    }
    // Ensure the widget is still mounted before using the context.
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Action "$selected" executed')),
      );
    }
  }

  Future<void> _showMenu(BuildContext context, Offset position) async {
    final selected = await showMenu<String>(
      context: context,
      position: RelativeRect.fromLTRB(
        position.dx,
        position.dy,
        position.dx,
        position.dy,
      ),
      items: const <PopupMenuEntry<String>>[
        PopupMenuItem(value: 'refresh', child: Text('Refresh')),
        PopupMenuItem(value: 'new_folder', child: Text('Open New Folder')),
        PopupMenuItem(value: 'sort', child: Text('Sort By')),
        PopupMenuItem(value: 'icon_size', child: Text('Increase Icon Size')),
        PopupMenuItem(value: 'run_admin', child: Text('Open With → Run as Administrator')),
      ],
    );
    if (selected != null) {
      await _performAction(context, selected);
    }
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
