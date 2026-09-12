import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

/// Interactive Python interpreter that launches `umeros_python.exe` and
/// communicates via stdin/stdout streams.  Designed with VS Code–style
/// toolbar icons (Run/Stop/Debug) and a status bar.
class PythonInterpreterApp extends StatefulWidget {
  const PythonInterpreterApp({super.key});

  @override
  State<PythonInterpreterApp> createState() => _PythonInterpreterAppState();
}

class _PythonInterpreterAppState extends State<PythonInterpreterApp> {
  // ── Controllers ───────────────────────────────────────────────
  final TextEditingController _controller = TextEditingController();
  final List<_LogEntry> _history = [];
  final ScrollController _scrollController = ScrollController();
  final FocusNode _inputFocus = FocusNode();

  // ── Process state ─────────────────────────────────────────────
  Process? _process;
  bool _running = false;
  String _pendingLine = '';
  int _exitCode = 0;

  // ── Debug mode ────────────────────────────────────────────────
  bool _debugMode = false;

  // ── History for Run button (code editor buffer) ───────────────
  final List<String> _inputHistory = [];
  int _inputHistoryIndex = -1;

  // Resolve the path to umeros_python.exe relative to the Flutter binary.
  static const String _exeName = 'umeros_python.exe';

  @override
  void initState() {
    super.initState();
    _history.add(const _LogEntry(
      type: _EntryType.system,
      text: 'UmerOS Python Interpreter (VS Code Style)\n'
          'Use the toolbar buttons: Run ▶, Stop ■, Debug 🐛\n'
          'Type "exit" or close the tab to quit.\n',
    ));
    _startProcess();
  }

  @override
  void dispose() {
    _killProcess();
    _controller.dispose();
    _scrollController.dispose();
    _inputFocus.dispose();
    super.dispose();
  }

  // ── Process management ────────────────────────────────────────

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

  String _interpreterPath() {
    final exeDir = Platform.resolvedExecutable;
    final localPath =
        '${File(exeDir).parent.path}${Platform.pathSeparator}$_exeName';
    if (File(localPath).existsSync()) return localPath;

    final bootPath =
        '${File(exeDir).parent.parent.path}${Platform.pathSeparator}'
        'boot${Platform.pathSeparator}python_vm${Platform.pathSeparator}'
        'build${Platform.pathSeparator}$_exeName';
    if (File(bootPath).existsSync()) return bootPath;

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
      _exitCode = 0;

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
            _exitCode = code;
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

  void _restartProcess() {
    _killProcess();
    setState(() {
      _history.clear();
      _debugMode = false;
      _history.add(const _LogEntry(
        type: _EntryType.system,
        text: 'UmerOS Python Interpreter (restarted)\n'
            'Use the toolbar buttons: Run ▶, Stop ■, Debug 🐛\n'
            'Type "exit" or close the tab to quit.\n',
      ));
    });
    _startProcess();
  }

  String _workingDir() {
    final home = Platform.environment['HOME'] ??
        Platform.environment['USERPROFILE'] ??
        '.';
    return home;
  }

  // ── Stream handlers ───────────────────────────────────────────

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

  // ── User input ────────────────────────────────────────────────

  void _submitCode(String text) {
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

    // Save to input history
    _inputHistory.add(text);
    _inputHistoryIndex = _inputHistory.length;

    setState(() {
      _pendingLine = '>>> $text';
    });

    _process?.stdin.writeln(text);
  }

  void _runButton() {
    if (_running) {
      // If running, send the current input as code
      final text = _controller.text;
      if (text.trim().isNotEmpty) {
        _submitCode(text);
      }
    } else {
      // If stopped, restart and run
      _restartProcess();
    }
    _inputFocus.requestFocus();
  }

  void _stopButton() {
    if (_running) {
      _killProcess();
      setState(() {
        _history.add(const _LogEntry(
          type: _EntryType.system,
          text: '[Process stopped by user]',
        ));
      });
    }
    _inputFocus.requestFocus();
  }

  void _debugButton() {
    setState(() {
      _debugMode = !_debugMode;
      if (_debugMode) {
        _history.add(const _LogEntry(
          type: _EntryType.system,
          text: '[Debug mode enabled — interactive debugging available]',
        ));
      } else {
        _history.add(const _LogEntry(
          type: _EntryType.system,
          text: '[Debug mode disabled]',
        ));
      }
    });
    _inputFocus.requestFocus();
  }

  void _handleKeyDown(KeyEvent event) {
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) return;
    final logical = event.logicalKey;

    // Ctrl+Enter → Run current line
    if (HardwareKeyboard.instance.isControlPressed &&
        logical == LogicalKeyboardKey.enter) {
      _runButton();
      return;
    }

    // Shift+F5 → Stop
    if (HardwareKeyboard.instance.isShiftPressed &&
        logical == LogicalKeyboardKey.f5) {
      _stopButton();
      return;
    }

    // F5 → Run
    if (logical == LogicalKeyboardKey.f5) {
      _runButton();
      return;
    }

    // Up arrow → history previous
    if (logical == LogicalKeyboardKey.arrowUp && _inputHistory.isNotEmpty) {
      if (_inputHistoryIndex > 0) {
        _inputHistoryIndex--;
        _controller.text = _inputHistory[_inputHistoryIndex];
        _controller.selection = TextSelection.fromPosition(
          TextPosition(offset: _controller.text.length),
        );
      }
    }

    // Down arrow → history next
    if (logical == LogicalKeyboardKey.arrowDown && _inputHistory.isNotEmpty) {
      if (_inputHistoryIndex < _inputHistory.length - 1) {
        _inputHistoryIndex++;
        _controller.text = _inputHistory[_inputHistoryIndex];
        _controller.selection = TextSelection.fromPosition(
          TextPosition(offset: _controller.text.length),
        );
      } else {
        _inputHistoryIndex = _inputHistory.length;
        _controller.clear();
      }
    }
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

  // ── Build ─────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final codeStyle = GoogleFonts.firaCode(fontSize: 13, height: 1.45);
    final smallStyle = GoogleFonts.firaCode(fontSize: 11);

    return KeyboardListener(
      focusNode: FocusNode(),
      onKeyEvent: _handleKeyDown,
      child: Scaffold(
        backgroundColor: const Color(0xFF181825),
        body: Column(
          children: [
            // ── VS Code–style toolbar ───────────────────────────
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              color: const Color(0xFF11111B),
              child: Row(
                children: [
                  // Python icon
                  const Icon(Icons.code, size: 16, color: Colors.yellowAccent),
                  const SizedBox(width: 6),

                  // Title
                  Expanded(
                    child: Text(
                      'Python Interpreter',
                      style: smallStyle.copyWith(color: Colors.white70),
                      maxLines: 1,
                    ),
                  ),

                  // ── Run / Stop / Debug buttons ────────────────
                  // Run (▶)
                  _ToolbarIconButton(
                    icon: Icons.play_arrow_rounded,
                    tooltip: 'Run (F5)',
                    color: Colors.greenAccent,
                    enabled: true,
                    onPressed: _runButton,
                  ),
                  const SizedBox(width: 2),

                  // Stop (■)
                  _ToolbarIconButton(
                    icon: Icons.stop_rounded,
                    tooltip: 'Stop (Shift+F5)',
                    color: Colors.redAccent,
                    enabled: _running,
                    onPressed: _stopButton,
                  ),
                  const SizedBox(width: 2),

                  // Debug (🐛)
                  _ToolbarIconButton(
                    icon: Icons.bug_report_rounded,
                    tooltip: 'Toggle Debug Mode',
                    color: _debugMode ? Colors.orangeAccent : Colors.white54,
                    enabled: true,
                    onPressed: _debugButton,
                  ),

                  const SizedBox(width: 8),

                  // Status chip
                  _StatusChip(running: _running),
                  const SizedBox(width: 8),

                  // Restart
                  _ToolbarIconButton(
                    icon: Icons.refresh_rounded,
                    tooltip: 'Restart Interpreter',
                    color: Colors.tealAccent,
                    enabled: true,
                    onPressed: _restartProcess,
                  ),
                  const SizedBox(width: 2),

                  // Clear
                  _ToolbarIconButton(
                    icon: Icons.delete_sweep_rounded,
                    tooltip: 'Clear Output',
                    color: Colors.orangeAccent,
                    enabled: true,
                    onPressed: () => setState(() => _history.clear()),
                  ),
                ],
              ),
            ),

            // ── Debug toolbar (appears when debug mode is on) ───
            if (_debugMode)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                color: const Color(0xFF1E1E2E),
                child: Row(
                  children: [
                    Icon(Icons.bug_report,
                        size: 12, color: Colors.orangeAccent.shade200),
                    const SizedBox(width: 4),
                    Text('DEBUG', style: smallStyle.copyWith(color: Colors.orangeAccent, fontWeight: FontWeight.bold)),
                    const SizedBox(width: 12),
                    _DebugAction(icon: Icons.skip_next_rounded, label: 'Step Over', shortcut: 'F10', enabled: _running),
                    const SizedBox(width: 8),
                    _DebugAction(icon: Icons.arrow_downward_rounded, label: 'Step Into', shortcut: 'F11', enabled: _running),
                    const SizedBox(width: 8),
                    _DebugAction(icon: Icons.arrow_upward_rounded, label: 'Step Out', shortcut: 'Shift+F11', enabled: _running),
                    const SizedBox(width: 8),
                    _DebugAction(icon: Icons.play_circle_outline_rounded, label: 'Continue', shortcut: 'F5', enabled: _running),
                    const SizedBox(width: 8),
                    _DebugAction(icon: Icons.restart_alt_rounded, label: 'Restart', shortcut: 'Ctrl+Shift+F5', enabled: true),
                    const SizedBox(width: 8),
                    _DebugAction(icon: Icons.stop_circle_rounded, label: 'Stop', shortcut: 'Shift+F5', enabled: _running),
                  ],
                ),
              ),

            // ── Output area ────────────────────────────────────
            Expanded(
              child: Container(
                color: const Color(0xFF1E1E2E),
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
                      padding: const EdgeInsets.symmetric(vertical: 1),
                      child: SelectableText(
                        entry.text,
                        style: codeStyle.copyWith(color: color, fontSize: 13),
                      ),
                    );
                  },
                ),
              ),
            ),

            // ── Input area ─────────────────────────────────────
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
                      focusNode: _inputFocus,
                      style: codeStyle.copyWith(color: Colors.white),
                      decoration: InputDecoration(
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding: EdgeInsets.zero,
                        hintText: _running
                            ? 'Enter Python code… (F5 to run, ↑↓ history)'
                            : 'Interpreter stopped — press ▶ to restart',
                        hintStyle: codeStyle.copyWith(
                          color: Colors.white24,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                      onSubmitted: _submitCode,
                      enabled: _running,
                      autofocus: true,
                    ),
                  ),
                  // Inline Run button in input area
                  if (_running)
                    IconButton(
                      onPressed: () {
                        final text = _controller.text;
                        if (text.trim().isNotEmpty) {
                          _submitCode(text);
                        }
                      },
                      icon: const Icon(Icons.play_circle_fill_rounded,
                          color: Colors.greenAccent, size: 20),
                      tooltip: 'Run line',
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                ],
              ),
            ),

            // ── VS Code–style status bar ───────────────────────
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
              color: const Color(0xFF007ACC),
              child: Row(
                children: [
                  // Interpreter path
                  Icon(Icons.terminal, size: 11, color: Colors.white.withValues(alpha: 0.9)),
                  const SizedBox(width: 4),
                  Text(
                    _interpreterPath(),
                    style: smallStyle.copyWith(color: Colors.white, fontSize: 10),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const Spacer(),

                  // Line count
                  Text(
                    '${_history.length} lines',
                    style: smallStyle.copyWith(color: Colors.white, fontSize: 10),
                  ),
                  const SizedBox(width: 10),

                  // Exit code
                  Text(
                    'exit: $_exitCode',
                    style: smallStyle.copyWith(color: Colors.white, fontSize: 10),
                  ),
                  const SizedBox(width: 10),

                  // Encoding
                  Text(
                    'UTF-8',
                    style: smallStyle.copyWith(color: Colors.white, fontSize: 10),
                  ),
                  const SizedBox(width: 10),

                  // Debug indicator
                  if (_debugMode)
                    Row(
                      children: [
                        Icon(Icons.bug_report, size: 10, color: Colors.white),
                        const SizedBox(width: 3),
                        Text('DEBUG',
                            style: smallStyle.copyWith(
                                color: Colors.white, fontSize: 10,
                                fontWeight: FontWeight.bold)),
                      ],
                    ),
                ],
              ),
            ),
          ],
        ),
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

/// VS Code–style toolbar icon button.
class _ToolbarIconButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final Color color;
  final bool enabled;
  final VoidCallback onPressed;

  const _ToolbarIconButton({
    required this.icon,
    required this.tooltip,
    required this.color,
    required this.enabled,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: enabled ? onPressed : null,
        borderRadius: BorderRadius.circular(4),
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: Icon(
            icon,
            size: 18,
            color: enabled ? color : color.withValues(alpha: 0.3),
          ),
        ),
      ),
    );
  }
}

/// VS Code–style debug action button.
class _DebugAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final String shortcut;
  final bool enabled;

  const _DebugAction({
    required this.icon,
    required this.label,
    required this.shortcut,
    required this.enabled,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: '$label ($shortcut)',
      child: InkWell(
        onTap: enabled ? () {} : null,
        borderRadius: BorderRadius.circular(4),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                icon,
                size: 14,
                color: enabled
                    ? Colors.white70
                    : Colors.white.withValues(alpha: 0.2),
              ),
              const SizedBox(width: 3),
              Text(
                label,
                style: GoogleFonts.firaCode(
                  fontSize: 10,
                  color: enabled
                      ? Colors.white60
                      : Colors.white.withValues(alpha: 0.2),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
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
