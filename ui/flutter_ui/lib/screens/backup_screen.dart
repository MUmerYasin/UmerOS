// License: GPL-3.0 (GNU General Public License Version 3)
// UmerOS Backup Subsystem UI Screen

import 'package:flutter/material.dart';
import '../services/backup_service.dart';

class BackupScreen extends StatefulWidget {
  const BackupScreen({Key? key}) : super(key: key);

  @override
  _BackupScreenState createState() => _BackupScreenState();
}

class _BackupScreenState extends State<BackupScreen> {
  List<BackupSnapshot> _snapshots = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadSnapshots();
  }

  Future<void> _loadSnapshots() async {
    setState(() => _isLoading = true);
    try {
      final snaps = await BackupService.listSnapshots();
      setState(() {
        _snapshots = snaps;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      _showError('Failed to load snapshots: $e');
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.red));
  }

  void _showSuccess(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.green));
  }

  Future<void> _createBackup() async {
    final descController = TextEditingController();
    final partsController = TextEditingController();

    await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create New Backup'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: descController,
              decoration: const InputDecoration(labelText: 'Description (e.g. Before update)'),
            ),
            TextField(
              controller: partsController,
              decoration: const InputDecoration(
                labelText: 'Specific Parts (Optional)',
                hintText: 'e.g., ui, kernel (leave empty for FULL)',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              setState(() => _isLoading = true);
              try {
                await BackupService.createSnapshot(
                  description: descController.text.isNotEmpty ? descController.text : 'Manual Backup',
                  parts: partsController.text,
                );
                _showSuccess('Backup Created Successfully!');
                _loadSnapshots();
              } catch (e) {
                _showError(e.toString());
                setState(() => _isLoading = false);
              }
            },
            child: const Text('Backup'),
          )
        ],
      ),
    );
  }

  Future<void> _restoreSnapshot(BackupSnapshot snap) async {
    final partsController = TextEditingController();

    await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Restore Snapshot: ${snap.id}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Warning: This will overwrite live files with the snapshot versions!'),
            const SizedBox(height: 16),
            TextField(
              controller: partsController,
              decoration: const InputDecoration(
                labelText: 'Restore Specific Parts Only (Optional)',
                hintText: 'e.g., ui, kernel (leave empty for FULL)',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
            onPressed: () async {
              Navigator.pop(context);
              setState(() => _isLoading = true);
              try {
                await BackupService.restoreSnapshot(snap.id, parts: partsController.text);
                _showSuccess('Restore Completed Successfully!');
                _loadSnapshots();
              } catch (e) {
                _showError(e.toString());
                setState(() => _isLoading = false);
              }
            },
            child: const Text('RESTORE'),
          )
        ],
      ),
    );
  }

  Future<void> _factoryReset() async {
    await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('FACTORY RESET', style: TextStyle(color: Colors.red)),
        content: const Text(
            'This is a destructive operation. All system changes, user configurations, '
            'and non-factory files will be permanently DELETED. Are you absolutely sure?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () async {
              Navigator.pop(context);
              setState(() => _isLoading = true);
              try {
                await BackupService.factoryReset();
                _showSuccess('Factory Reset Completed!');
                _loadSnapshots();
              } catch (e) {
                _showError(e.toString());
                setState(() => _isLoading = false);
              }
            },
            child: const Text('WIPE EVERYTHING', style: TextStyle(color: Colors.white)),
          )
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('UmerOS Backup & Restore'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadSnapshots),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Row(
                    children: [
                      ElevatedButton.icon(
                        icon: const Icon(Icons.backup),
                        label: const Text('New Backup'),
                        onPressed: _createBackup,
                      ),
                      const Spacer(),
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(backgroundColor: Colors.red.shade900),
                        icon: const Icon(Icons.warning, color: Colors.white),
                        label: const Text('Factory Reset', style: TextStyle(color: Colors.white)),
                        onPressed: _factoryReset,
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: _snapshots.isEmpty
                      ? const Center(child: Text('No snapshots found.'))
                      : ListView.builder(
                          itemCount: _snapshots.length,
                          itemBuilder: (context, index) {
                            final snap = _snapshots[index];
                            final isFactory = snap.level == 'F';
                            return Card(
                              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              child: ListTile(
                                leading: Icon(
                                  isFactory ? Icons.settings_backup_restore : Icons.folder_zip,
                                  color: isFactory ? Colors.red : Colors.blue,
                                ),
                                title: Text(snap.description.isEmpty ? 'Snapshot ${snap.id}' : snap.description),
                                subtitle: Text('ID: ${snap.id} | Level: ${snap.level} | Version: ${snap.sysVersion}'),
                                trailing: isFactory 
                                  ? const Text('LOCKED', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red))
                                  : IconButton(
                                      icon: const Icon(Icons.restore),
                                      tooltip: 'Restore',
                                      onPressed: () => _restoreSnapshot(snap),
                                    ),
                              ),
                            );
                          },
                        ),
                ),
              ],
            ),
    );
  }
}
