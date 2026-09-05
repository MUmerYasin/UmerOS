// License: GPL-3.0 (GNU General Public License Version 3)
// UmerOS Backup App Wrapper

import 'package:flutter/material.dart';
import '../../screens/backup_screen.dart';

class BackupApp extends StatelessWidget {
  const BackupApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    // The DesktopWindow provides its own scaffolding typically, 
    // but BackupScreen is a Scaffold. It will render fine inside the window.
    return const BackupScreen();
  }
}
