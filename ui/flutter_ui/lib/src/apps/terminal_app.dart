import 'package:flutter/material.dart';
import 'dart:math';

class TerminalApp extends StatefulWidget {
  const TerminalApp({super.key});

  @override
  State<TerminalApp> createState() => _TerminalAppState();
}

class _TerminalAppState extends State<TerminalApp> {
  final TextEditingController _controller = TextEditingController();
  final List<Map<String, String>> _history = [];
  final ScrollController _scrollController = ScrollController();
  String _currentPath = '/home/user';
  bool _showCursor = true;

  @override
  void initState() {
    super.initState();
    _history.add({
      'type': 'system',
      'text': 'Welcome to UmerOS Terminal v2.0\nType "help" for available commands.\n',
    });
    _blinkCursor();
  }

  void _blinkCursor() {
    Future.doWhile(() async {
      await Future.delayed(const Duration(milliseconds: 530));
      if (!mounted) return false;
      setState(() => _showCursor = !_showCursor);
      return true;
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _executeCommand(String input) {
    if (input.trim().isEmpty) return;

    setState(() {
      _history.add({'type': 'input', 'text': '$_currentPath\$ $input'});
    });

    final parts = input.trim().split(' ');
    final command = parts[0].toLowerCase();
    final args = parts.sublist(1);

    switch (command) {
      case 'help':
        _addOutput(_getHelpText());
        break;
      case 'clear':
        setState(() => _history.clear());
        break;
      case 'ls':
        _addOutput(_ls(args));
        break;
      case 'cd':
        _cd(args);
        break;
      case 'pwd':
        _addOutput(_currentPath);
        break;
      case 'cat':
        _cat(args);
        break;
      case 'echo':
        _addOutput(args.join(' '));
        break;
      case 'date':
        _addOutput(DateTime.now().toString());
        break;
      case 'whoami':
        _addOutput('user@umeros');
        break;
      case 'uname':
        _addOutput('UmerOS 2.0 (Quantum Kernel)');
        break;
      case 'uptime':
        _addOutput(_getUptime());
        break;
      case 'neofetch':
        _addOutput(_getNeofetch());
        break;
      case 'quantum':
        _quantumSim(args);
        break;
      case 'ai':
        _aiCommand(args);
        break;
      case 'process':
        _processCommand(args);
        break;
      case 'memory':
        _memoryCommand(args);
        break;
      default:
        _addOutput('Command not found: $command\nType "help" for available commands.');
    }

    _controller.clear();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 100),
        curve: Curves.easeOut,
      );
    });
  }

  void _addOutput(String text) {
    setState(() {
      _history.add({'type': 'output', 'text': text});
    });
  }

  String _getHelpText() {
    return '''
UmerOS Terminal Commands:
─────────────────────────────────
  help          Show this help message
  clear         Clear terminal
  ls [path]     List directory contents
  cd <path>     Change directory
  pwd           Print working directory
  cat <file>    Display file contents
  echo <text>   Print text
  date          Show current date/time
  whoami        Show current user
  uname         Show system info
  uptime        Show system uptime
  neofetch      Show system info (fancy)
  quantum       Quantum computing commands
  ai            AI integration commands
  process       Process management
  memory        Memory management
─────────────────────────────────
  Type "quantum --help" for quantum commands.
  Type "ai --help" for AI commands.
''';
  }

  String _ls(List<String> args) {
    final dirs = {
      '/': ['home', 'usr', 'bin', 'etc', 'var', 'tmp', 'opt', 'dev', 'proc', 'sys'],
      '/home': ['user'],
      '/home/user': ['Documents', 'Downloads', 'Desktop', 'Pictures', 'Music', '.config'],
      '/usr': ['bin', 'lib', 'share', 'local'],
      '/bin': ['bash', 'sh', 'ls', 'cat', 'echo', 'mkdir', 'rm', 'cp', 'mv'],
    };
    final path = args.isNotEmpty ? args[0] : _currentPath;
    final contents = dirs[path] ?? ['file1.txt', 'file2.py', 'script.sh'];
    return contents.join('  ');
  }

  void _cd(List<String> args) {
    if (args.isEmpty) {
      _currentPath = '/home/user';
    } else {
      final target = args[0];
      if (target == '..') {
        final parts = _currentPath.split('/');
        if (parts.length > 1) {
          parts.removeLast();
          _currentPath = parts.join('/').isEmpty ? '/' : parts.join('/');
        }
      } else if (target.startsWith('/')) {
        _currentPath = target;
      } else {
        _currentPath = '$_currentPath/$target';
      }
    }
    _addOutput('');
  }

  void _cat(List<String> args) {
    if (args.isEmpty) {
      _addOutput('Usage: cat <filename>');
      return;
    }
    final files = {
      'README.md': '# UmerOS\nA quantum-powered operating system with AI integration.',
      'config.json': '{\n  "kernel": "quantum",\n  "ai": "enabled",\n  "version": "2.0"\n}',
      'script.sh': '#!/bin/bash\necho "Hello from UmerOS"',
    };
    _addOutput(files[args[0]] ?? 'File not found: ${args[0]}');
  }

  String _getUptime() {
    final hours = Random().nextInt(24);
    final mins = Random().nextInt(60);
    return 'up $hours hours, $mins minutes';
  }

  String _getNeofetch() {
    return '''
    ╔══════════════════╗
    ║   ▄▄▄▄▄▄▄▄▄▄▄   ║
    ║  █ UmerOS  █   ║
    ║  █ QUANTUM █   ║
    ║  █  KERNEL  █   ║
    ║  ▀▀▀▀▀▀▀▀▀▀▀   ║
    ╚══════════════════╝
  OS: UmerOS 2.0
  Kernel: Quantum Kernel 1.0
  Shell: UmerShell 2.0
  CPU: Quantum Core (128 qubits)
  Memory: 256 GB QRAM
  AI: Neural Engine v3
  Filesystem: QFS (Quantum File System)
''';
  }

  void _quantumSim(List<String> args) {
    if (args.isEmpty || args[0] == '--help') {
      _addOutput('''
Quantum Commands:
  quantum init       Initialize quantum state
  quantum entangle   Create entangled pair
  quantum measure    Measure quantum state
  quantum teleport   Quantum teleportation
  quantum simulate   Run quantum simulation
''');
      return;
    }
    switch (args[0]) {
      case 'init':
        _addOutput('Quantum state initialized: |0⟩');
        break;
      case 'entangle':
        _addOutput('Entangled pair created: (|00⟩ + |11⟩) / √2');
        break;
      case 'measure':
        final result = Random().nextBool() ? '|0⟩' : '|1⟩';
        _addOutput('Measurement result: $result');
        break;
      case 'teleport':
        _addOutput('Quantum state teleported successfully. Fidelity: 0.987');
        break;
      case 'simulate':
        _addOutput('Running quantum simulation... Complete.\nGate count: ${Random().nextInt(100) + 50}\nFidelity: ${(0.95 + Random().nextDouble() * 0.04).toStringAsFixed(4)}');
        break;
      default:
        _addOutput('Unknown quantum command: ${args[0]}');
    }
  }

  void _aiCommand(List<String> args) {
    if (args.isEmpty || args[0] == '--help') {
      _addOutput('''
AI Commands:
  ai status       Show AI engine status
  ai analyze      Analyze current state
  ai predict      Run prediction
  ai optimize     Optimize system
''');
      return;
    }
    switch (args[0]) {
      case 'status':
        _addOutput('AI Engine: Active\nModel: UmerNet v3\nNeurons: 1.2B\nStatus: Ready');
        break;
      case 'analyze':
        _addOutput('Analyzing system state...\nCPU: 23% | Memory: 45% | I/O: Low\nRecommendation: System optimal.');
        break;
      case 'predict':
        _addOutput('Prediction: Next process will need 2.3GB RAM\nConfidence: 87%');
        break;
      case 'optimize':
        _addOutput('Optimizing system...\nDefragmented memory: 12GB freed\nCache hit rate improved: 15%');
        break;
      default:
        _addOutput('Unknown AI command: ${args[0]}');
    }
  }

  void _processCommand(List<String> args) {
    if (args.isEmpty || args[0] == '--help') {
      _addOutput('''
Process Commands:
  process list      List running processes
  process kill <id> Kill a process
  process stats     Show process statistics
''');
      return;
    }
    switch (args[0]) {
      case 'list':
        _addOutput('''
PID   NAME              CPU%   MEM%
1     init              0.1    0.2
2     kernel            0.3    1.5
3     ai_engine         2.1    5.2
4     quantum_daemon    1.8    3.1
5     shell             0.5    0.8
''');
        break;
      case 'stats':
        _addOutput('Total: 5 | Running: 3 | Sleeping: 2 | Stopped: 0');
        break;
      case 'kill':
        if (args.length > 1) {
          _addOutput('Process ${args[1]} terminated.');
        } else {
          _addOutput('Usage: process kill <pid>');
        }
        break;
      default:
        _addOutput('Unknown process command: ${args[0]}');
    }
  }

  void _memoryCommand(List<String> args) {
    _addOutput('''
Memory Status:
  Total:     256.0 GB
  Used:      115.2 GB (45%)
  Free:      140.8 GB
  Cached:     32.4 GB
  Swap:        16.0 GB (0% used)
''');
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF1E1E2E),
      child: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(12),
              itemCount: _history.length,
              itemBuilder: (context, index) {
                final entry = _history[index];
                final isInput = entry['type'] == 'input';
                final isSystem = entry['type'] == 'system';

                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: SelectableText(
                    entry['text']!,
                    style: TextStyle(
                      fontFamily: 'Consolas',
                      fontSize: 14,
                      color: isSystem
                          ? Colors.tealAccent
                          : isInput
                              ? Colors.greenAccent
                              : Colors.white,
                    ),
                  ),
                );
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF181825),
              border: Border(
                top: BorderSide(
                  color: Colors.teal.withValues(alpha: 0.3),
                ),
              ),
            ),
            child: Row(
              children: [
                Text(
                  '$_currentPath\$ ',
                  style: const TextStyle(
                    fontFamily: 'Consolas',
                    fontSize: 14,
                    color: Colors.tealAccent,
                  ),
                ),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: const TextStyle(
                      fontFamily: 'Consolas',
                      fontSize: 14,
                      color: Colors.white,
                    ),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      hintText: _showCursor ? '█' : ' ',
                      hintStyle: const TextStyle(
                        fontFamily: 'Consolas',
                        color: Colors.tealAccent,
                      ),
                    ),
                    onSubmitted: _executeCommand,
                    autofocus: true,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
