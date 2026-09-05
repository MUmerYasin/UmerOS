// License: GPL-3.0 (GNU General Public License Version 3)
// UmerOS Backup Subsystem UI Service

import 'dart:convert';
import 'dart:io';

class BackupSnapshot {
  final String id;
  final String timestamp;
  final String level;
  final String path;
  final String sysVersion;
  final String description;

  BackupSnapshot({
    required this.id,
    required this.timestamp,
    required this.level,
    required this.path,
    required this.sysVersion,
    required this.description,
  });

  factory BackupSnapshot.fromJson(Map<String, dynamic> json) {
    return BackupSnapshot(
      id: json['id'] ?? '',
      timestamp: json['timestamp'] ?? '',
      level: json['level'] ?? '',
      path: json['path'] ?? '',
      sysVersion: json['sys_version'] ?? '',
      description: json['description'] ?? '',
    );
  }
}

class BackupService {
  static const String pythonCmd = 'python';
  // Adjust paths as necessary for standard UmerOS layout
  static const String umerOsRoot = r'F:\Pension Person Details\UmerOS';
  static const String cliPath = r'backup\cli.py'; 

  static Future<List<BackupSnapshot>> listSnapshots() async {
    final result = await Process.run(pythonCmd, [
      '-m', 'backup.cli',
      '--list',
      '--json'
    ], workingDirectory: umerOsRoot);

    if (result.exitCode == 0) {
      if (result.stdout.toString().trim().isEmpty) {
        return [];
      }
      try {
        final List<dynamic> decoded = jsonDecode(result.stdout);
        return decoded.map((e) => BackupSnapshot.fromJson(e)).toList();
      } catch (e) {
        throw Exception('Failed to parse backup list: $e');
      }
    } else {
      throw Exception('Error listing snapshots: ${result.stderr}');
    }
  }

  static Future<void> createSnapshot({
    String description = 'UI Generated Snapshot',
    String level = 'O',
    String? parts,
  }) async {
    List<String> args = [
      '-m', 'backup.cli',
      '--create',
      '--comments', description,
      '--tags', level,
      '--json'
    ];

    if (parts != null && parts.isNotEmpty) {
      args.addAll(['--parts', parts]);
    }

    final result = await Process.run(pythonCmd, args, workingDirectory: umerOsRoot);
    if (result.exitCode != 0) {
      throw Exception('Failed to create snapshot: ${result.stderr}');
    }
  }

  static Future<bool> restoreSnapshot(String id, {String? parts}) async {
    List<String> args = [
      '-m', 'backup.cli',
      '--restore', id,
      '--json'
    ];

    if (parts != null && parts.isNotEmpty) {
      args.addAll(['--parts', parts]);
    }

    final result = await Process.run(pythonCmd, args, workingDirectory: umerOsRoot);
    if (result.exitCode == 0) {
      return true;
    } else {
      throw Exception('Restore failed: ${result.stderr}');
    }
  }

  static Future<void> factoryReset() async {
    // Factory reset usually requires interactive confirmation, 
    // but we can pass 'I AGREE' via stdin if the CLI expects it,
    // though Process.start is better for stdin.
    final process = await Process.start(pythonCmd, [
      '-m', 'backup.cli',
      '--factory-reset'
    ], workingDirectory: umerOsRoot);
    
    process.stdin.writeln('I AGREE');
    
    final exitCode = await process.exitCode;
    if (exitCode != 0) {
      throw Exception('Factory reset failed.');
    }
  }
}
