import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Interactive Python interpreter that launches `umeros_python.exe` and
/// communicates via stdin/stdout streams.
class PythonInterpreterApp extends StatefulWidget {
  const PythonInterpreterApp({super.key});

  @override
  State<PythonInterpreterApp> createState() => _PythonInterpreterAppState();
}

class _PythonInterpreterAppState extends State<PythonInterpreterApp> {
  final TextEditingController _controller = TextEditingController();
  final List<_LogEntry> _history = [];
  final ScrollController _scrollController = ScrollController();

  Process? _process;
  bool _running = false;
  String _pendingLine = '';

  // Resolve the path to umeros_python.exe relative to the Flutter binary.
  static const String _exeName = 'umeros_python.exe';

  @override
  void initState() {
    super.initState();
    _history.add(const _LogEntry(
      type: _EntryType.system,
      text: 'UmerOS Python Interpreter\n'
          'Type Python code below.  Use "exit" or close the tab to quit.\n',
    ));
    _startProcess();
  }

  @override
  void dispose() {
    _killProcess();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ── Process management ──────────────────────────────────────────

  String _findInterpreter() {
    // 1) Same directory as the Flutter executable
    final exeDir = Platform.resolvedExecutable;
    final localPath =
        '${File(exeDir).parent.path}${Platform.pathSeparator}$_exeName';
    if (File(localPath).existsSync()) return localPath;

    // 2) boot/python_vm/build/ (development layout)
    final bootPath =
        '${File(exeDir).parent.parent.path}${Platform.pathSeparator}'
        'boot${Platform.pathSeparator}python_vm${Platform.pathSeparator}'
        'build${Platform.pathSeparator}$_exeName';
    if (File(bootPath).existsSync()) return bootPath;

    // 3) Fallback — hope it is on PATH
    return _exeName;
  }

  Future<void> _startProcess() async {
    try {
      final exePath = _findInterpreter();
      _process = await Process.start(
        exePath,
        [],
        workingDirectory: _workingDir(),
      );
      _running = true;

      // Pipe stdout
      _process!.stdout
          .transform(const SystemEncoding().decoder)
          .transform(const LineSplitter())
          .listen(_onStdout);

      // Pipe stderr
      _process!.stderr
          .transform(const SystemEncoding().decoder)
          .transform(const LineSplitter())
          .listen(_onStderr);

      // Detect exit
      _process!.exitCode.then((code) {
        if (mounted) {
          setState(() {
            _running = false;
            _history.add(_LogEntry(
              type: _EntryType.system,
              text: '[Process exited with code $code]',
            ));
          });
        }
      });
    } catch (e) {
      _history.add(_LogEntry(
        type: _EntryType.error,
        text: 'Failed to start Python interpreter: $e',
      ));
    }
  }

  void _killProcess() {
    _process?.kill();
    _process = null;
    _running = false;
  }

  String _workingDir() {
    final home = Platform.environment['HOME'] ??
        Platform.environment['USERPROFILE'] ??
        '.';
    return home;
  }

  // ── Stream handlers ─────────────────────────────────────────────

  void _onStdout(String line) {
    if (!mounted) return;
    setState(() {
      // If we had a pending prompt line (>>>), replace it with the echoed input
      if (_pendingLine.isNotEmpty) {
        _history.add(_LogEntry(type: _EntryType.input, text: _pendingLine));
        _pendingLine = '';
      }
      _history.add(_LogEntry(type: _EntryType.output, text: line));
    });
    _scrollToBottom();
  }

  void _onStderr(String line) {
    if (!mounted) return;
    setState(() {
      if (_pendingLine.isNotEmpty) {
        _history.add(_LogEntry(type: _EntryType.input, text: _pendingLine));
        _pendingLine = '';
      }
      _history.add(_LogEntry(type: _EntryType.error, text: line));
    });
    _scrollToBottom();
  }

  // ── User input ──────────────────────────────────────────────────

  void _onSubmit(String text) {
    _controller.clear();
    if (text.trim().toLowerCase() == 'exit') {
      _killProcess();
      setState(() {
        _history.add(const _LogEntry(
          type: _EntryType.system,
          text: '[Interpreter exited]',
        ));
      });
      return;
    }

    if (text.trim().isEmpty || !_running) return;

    setState(() {
      _pendingLine = '>>> $text';
    });

    _process?.stdin.writeln(text);
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 80),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ── Build ───────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final codeStyle = GoogleFonts.firaCode(fontSize: 13, height: 1.45);

    return Scaffold(
      backgroundColor: const Color(0xFF181825),
      body: Column(
        children: [
          // ── Toolbar ──────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            color: const Color(0xFF11111B),
            child: Row(
              children: [
                const Icon(Icons.code, size: 16, color: Colors.yellowAccent),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Python Interpreter',
                    style: codeStyle.copyWith(
                      color: Colors.white70,
                      fontSize: 11,
                    ),
                    maxLines: 1,
                  ),
                ),
                _StatusChip(running: _running),
                const SizedBox(width: 8),
                TextButton.icon(
                  onPressed: _running
                      ? null
                      : () {
                          _killProcess();
                          setState(() => _history.clear());
                          _startProcess();
                        },
                  icon: const Icon(Icons.refresh, size: 14),
                  label: Text('Restart', style: codeStyle.copyWith(fontSize: 11)),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.tealAccent,
                  ),
                ),
                TextButton.icon(
                  onPressed: () {
                    setState(() => _history.clear());
                  },
                  icon: const Icon(Icons.clear_all, size: 14),
                  label: Text('Clear', style: codeStyle.copyWith(fontSize: 11)),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.orangeAccent,
                  ),
                ),
              ],
            ),
          ),

          // ── Output ──────────────────────────────────────────────
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(12),
              itemCount: _history.length,
              itemBuilder: (context, index) {
                final entry = _history[index];
                Color color;
                switch (entry.type) {
                  case _EntryType.system:
                    color = Colors.tealAccent;
                  case _EntryType.input:
                    color = Colors.greenAccent;
                  case _EntryType.output:
                    color = Colors.white;
                  case _EntryType.error:
                    color = Colors.redAccent;
                }
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: SelectableText(
                    entry.text,
                    style: codeStyle.copyWith(color: color),
                  ),
                );
              },
            ),
          ),

          // ── Input ───────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            color: const Color(0xFF11111B),
            child: Row(
              children: [
                Text(
                  '>>> ',
                  style: codeStyle.copyWith(color: Colors.yellowAccent),
                ),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: codeStyle.copyWith(color: Colors.white),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      isDense: true,
                      contentPadding: EdgeInsets.zero,
                      hintText: _running ? 'Enter Python code…' : 'Interpreter stopped',
                      hintStyle: codeStyle.copyWith(
                        color: Colors.white24,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                    onSubmitted: _onSubmit,
                    enabled: _running,
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

// ── Helpers ─────────────────────────────────────────────────────

enum _EntryType { system, input, output, error }

class _LogEntry {
  final _EntryType type;
  final String text;
  const _LogEntry({required this.type, required this.text});
}

class _StatusChip extends StatelessWidget {
  final bool running;
  const _StatusChip({required this.running});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: running ? Colors.greenAccent : Colors.redAccent,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          running ? 'Running' : 'Stopped',
          style: GoogleFonts.firaCode(
            fontSize: 10,
            color: running ? Colors.greenAccent : Colors.redAccent,
          ),
        ),
      ],
    );
  }
}
