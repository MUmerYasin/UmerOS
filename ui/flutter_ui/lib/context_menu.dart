import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart'; // PointerDeviceKind and mouse button constants
import 'package:http/http.dart' as http;

class RightClickArea extends StatelessWidget {
  final Widget child;
  const RightClickArea({super.key, required this.child});

  // Perform the selected backend action.
  Future<void> _performAction(BuildContext context, String selected) async {
    switch (selected) {
      case 'refresh':
        // Windows "Refresh" redraws the desktop – we ask the backend to refresh UI.
        await http.post(Uri.parse('http://127.0.0.1:5000/refresh'));
        break;
      case 'new_folder':
        await http.post(Uri.parse('http://127.0.0.1:5000/new_folder'),
            body: {'name': 'new_folder'});
        break;
      case 'sort_name':
        await http.post(Uri.parse('http://127.0.0.1:5000/sort'),
            body: {'by': 'name'});
        break;
      case 'sort_size':
        await http.post(Uri.parse('http://127.0.0.1:5000/sort'),
            body: {'by': 'size'});
        break;
      case 'sort_date':
        await http.post(Uri.parse('http://127.0.0.1:5000/sort'),
            body: {'by': 'date'});
        break;
      case 'sort_type':
        await http.post(Uri.parse('http://127.0.0.1:5000/sort'),
            body: {'by': 'type'});
        break;
      case 'icon_small':
        await http.post(Uri.parse('http://127.0.0.1:5000/icon_size'),
            body: {'size': 'small'});
        break;
      case 'icon_medium':
        await http.post(Uri.parse('http://127.0.0.1:5000/icon_size'),
            body: {'size': 'medium'});
        break;
      case 'icon_large':
        await http.post(Uri.parse('http://127.0.0.1:5000/icon_size'),
            body: {'size': 'large'});
        break;
      case 'run_admin':
        await http.post(Uri.parse('http://127.0.0.1:5000/run_as_admin'),
            body: {'command': 'whoami'});
        break;
    }
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
        PopupMenuItem(value: 'sort_name', child: Text('Sort By \u2192 Name')),
        PopupMenuItem(value: 'sort_size', child: Text('Sort By \u2192 Size')),
        PopupMenuItem(value: 'sort_date', child: Text('Sort By \u2192 Date Modified')),
        PopupMenuItem(value: 'sort_type', child: Text('Sort By \u2192 Type')),
        PopupMenuItem(value: 'icon_small', child: Text('Icon Size \u2192 Small')),
        PopupMenuItem(value: 'icon_medium', child: Text('Icon Size \u2192 Medium')),
        PopupMenuItem(value: 'icon_large', child: Text('Icon Size \u2192 Large')),
        PopupMenuItem(value: 'run_admin', child: Text('Open With \u2192 Run as Administrator')),
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
