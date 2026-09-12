import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

/// Interactive Python interpreter that launches `umeros_python.exe` and
/// communicates via stdin/stdout streams.  Designed with VS Code–style
/// UI patterns: toolbar, debug toolbar, status bar with interpreter
/// selector, terminal tabs, command palette, and keyboard shortcuts.
class PythonInterpreterApp extends StatefulWidget {
  const PythonInterpreterApp({super.key});

  @override
  State<PythonInterpreterApp> createState() => _PythonInterpreterAppState();
}

class _PythonInterpreterAppState extends State<PythonInterpreterApp> {
  // ── Controllers ───────────────────────────────────────────────
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _inputFocus = FocusNode();

  // ── Session management (VS Code terminal tabs) ────────────────
  final List<_TerminalSession> _sessions = [];
  int _activeSessionIndex = 0;

  // ── Debug mode ────────────────────────────────────────────────
  bool _debugMode = false;

  // ── Command palette ───────────────────────────────────────────
  bool _showCommandPalette = false;
  final TextEditingController _paletteController = TextEditingController();
  final FocusNode _paletteFocus = FocusNode();

  // ── Interpreter selector ──────────────────────────────────────
  bool _showInterpreterPicker = false;

  // ── Output settings ───────────────────────────────────────────
  bool _wordWrap = true;
  bool _showLineNumbers = true;
  double _fontSize = 13;

  // ── History for Up/Down arrow recall ───────────────────────────
  final List<String> _inputHistory = [];
  int _inputHistoryIndex = -1;

  static const String _exeName = 'umeros_python.exe';

  _TerminalSession get _active => _sessions[_activeSessionIndex];

  @override
  void initState() {
    super.initState();
    _sessions.add(_TerminalSession(name: 'Python 1'));
    _active.history.add(const _LogEntry(
      type: _EntryType.system,
      text: 'UmerOS Python Interpreter\n'
          'Toolbar: Run ▶  Stop ■  Debug 🐛  Restart ↻\n'
          'Status bar: click interpreter to switch | F5 run | Shift+F5 stop\n'
          'Ctrl+Shift+P: command palette | Ctrl+L: clear | Ctrl+F: search\n',
    ));
    _startProcess();
  }

  @override
  void dispose() {
    for (final s in _sessions) {
      s.process?.kill();
    }
    _controller.dispose();
    _scrollController.dispose();
    _inputFocus.dispose();
    _paletteController.dispose();
    _paletteFocus.dispose();
    super.dispose();
  }

  // ── Process management ────────────────────────────────────────

  String _findInterpreter() {
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
      final proc = await Process.start(
        exePath,
        [],
        workingDirectory: _workingDir(),
      );
      _active.process = proc;
      _active.running = true;
      _active.exitCode = 0;

      proc.stdout
          .transform(const SystemEncoding().decoder)
          .transform(const LineSplitter())
          .listen(_onStdout);

      proc.stderr
          .transform(const SystemEncoding().decoder)
          .transform(const LineSplitter())
          .listen(_onStderr);

      proc.exitCode.then((code) {
        if (mounted) {
          setState(() {
            _active.running = false;
            _active.exitCode = code;
            _active.history.add(_LogEntry(
              type: _EntryType.system,
              text: '[Process exited with code $code]',
            ));
          });
        }
      });
    } catch (e) {
      _active.history.add(_LogEntry(
        type: _EntryType.error,
        text: 'Failed to start Python interpreter: $e',
      ));
    }
  }

  void _killProcess() {
    _active.process?.kill();
    _active.process = null;
    _active.running = false;
  }

  void _restartProcess() {
    _killProcess();
    setState(() {
      _active.history.clear();
      _debugMode = false;
      _active.history.add(const _LogEntry(
        type: _EntryType.system,
        text: 'UmerOS Python Interpreter (restarted)\n'
            'Toolbar: Run ▶  Stop ■  Debug 🐛  Restart ↻\n',
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
      if (_active.pendingLine.isNotEmpty) {
        _active.history
            .add(_LogEntry(type: _EntryType.input, text: _active.pendingLine));
        _active.pendingLine = '';
      }
      _active.history.add(_LogEntry(type: _EntryType.output, text: line));
    });
    _scrollToBottom();
  }

  void _onStderr(String line) {
    if (!mounted) return;
    setState(() {
      if (_active.pendingLine.isNotEmpty) {
        _active.history
            .add(_LogEntry(type: _EntryType.input, text: _active.pendingLine));
        _active.pendingLine = '';
      }
      _active.history.add(_LogEntry(type: _EntryType.error, text: line));
    });
    _scrollToBottom();
  }

  // ── User input ────────────────────────────────────────────────

  void _submitCode(String text) {
    _controller.clear();
    if (text.trim().toLowerCase() == 'exit') {
      _killProcess();
      setState(() {
        _active.history.add(const _LogEntry(
          type: _EntryType.system,
          text: '[Interpreter exited]',
        ));
      });
      return;
    }

    if (text.trim().isEmpty || !_active.running) return;

    _inputHistory.add(text);
    _inputHistoryIndex = _inputHistory.length;

    setState(() {
      _active.pendingLine = '>>> $text';
    });

    _active.process?.stdin.writeln(text);
  }

  void _runButton() {
    if (_active.running) {
      final text = _controller.text;
      if (text.trim().isNotEmpty) {
        _submitCode(text);
      }
    } else {
      _restartProcess();
    }
    _inputFocus.requestFocus();
  }

  void _stopButton() {
    if (_active.running) {
      _killProcess();
      setState(() {
        _active.history.add(const _LogEntry(
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
      _active.history.add(_LogEntry(
        type: _EntryType.system,
        text: _debugMode
            ? '[Debug mode enabled — step/continue available]'
            : '[Debug mode disabled]',
      ));
    });
    _inputFocus.requestFocus();
  }

  // ── Terminal tab management ───────────────────────────────────

  void _newSession() {
    setState(() {
      final idx = _sessions.length + 1;
      _sessions.add(_TerminalSession(name: 'Python $idx'));
      _activeSessionIndex = _sessions.length - 1;
    });
    _startProcess();
    _inputFocus.requestFocus();
  }

  void _closeSession(int index) {
    if (_sessions.length <= 1) return;
    final session = _sessions[index];
    session.process?.kill();
    setState(() {
      _sessions.removeAt(index);
      if (_activeSessionIndex >= _sessions.length) {
        _activeSessionIndex = _sessions.length - 1;
      }
    });
  }

  void _switchSession(int index) {
    if (index == _activeSessionIndex) return;
    setState(() {
      _activeSessionIndex = index;
    });
    _inputFocus.requestFocus();
  }

  // ── Command palette ───────────────────────────────────────────

  void _toggleCommandPalette() {
    setState(() {
      _showCommandPalette = !_showCommandPalette;
      if (_showCommandPalette) {
        _paletteController.clear();
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _paletteFocus.requestFocus();
        });
      }
    });
  }

  List<_PaletteCommand> _paletteCommands() => [
        _PaletteCommand(
          label: 'Python Interpreter: Select Interpreter',
          icon: Icons.code,
          action: () {
            setState(() => _showInterpreterPicker = true);
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Terminal: New Session',
          icon: Icons.add,
          action: () {
            _newSession();
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Terminal: Restart',
          icon: Icons.refresh,
          action: () {
            _restartProcess();
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Terminal: Clear',
          icon: Icons.delete_sweep,
          action: () {
            setState(() => _active.history.clear());
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Toggle Debug Mode',
          icon: Icons.bug_report,
          action: () {
            _debugButton();
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Toggle Word Wrap',
          icon: Icons.wrap_text,
          action: () {
            setState(() => _wordWrap = !_wordWrap);
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Toggle Line Numbers',
          icon: Icons.format_list_numbered,
          action: () {
            setState(() => _showLineNumbers = !_showLineNumbers);
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Increase Font Size',
          icon: Icons.zoom_in,
          action: () {
            setState(() => _fontSize = (_fontSize + 1).clamp(10.0, 24.0));
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Decrease Font Size',
          icon: Icons.zoom_out,
          action: () {
            setState(() => _fontSize = (_fontSize - 1).clamp(10.0, 24.0));
            _showCommandPalette = false;
          },
        ),
      ];

  List<_PaletteCommand> get _filteredCommands {
    final q = _paletteController.text.toLowerCase();
    if (q.isEmpty) return _paletteCommands();
    return _paletteCommands()
        .where((c) => c.label.toLowerCase().contains(q))
        .toList();
  }

  // ── Keyboard shortcuts ────────────────────────────────────────

  void _handleKeyDown(KeyEvent event) {
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) return;
    final logical = event.logicalKey;
    final hw = HardwareKeyboard.instance;

    // Ctrl+Shift+P → Command palette
    if (hw.isControlPressed &&
        hw.isShiftPressed &&
        logical == LogicalKeyboardKey.keyP) {
      _toggleCommandPalette();
      return;
    }

    // Ctrl+Enter → Run current line
    if (hw.isControlPressed && logical == LogicalKeyboardKey.enter) {
      _runButton();
      return;
    }

    // Shift+F5 → Stop
    if (hw.isShiftPressed && logical == LogicalKeyboardKey.f5) {
      _stopButton();
      return;
    }

    // F5 → Run
    if (logical == LogicalKeyboardKey.f5) {
      _runButton();
      return;
    }

    // Ctrl+L → Clear
    if (hw.isControlPressed && logical == LogicalKeyboardKey.keyL) {
      setState(() => _active.history.clear());
      return;
    }

    // Ctrl+= → Zoom in
    if (hw.isControlPressed && logical == LogicalKeyboardKey.equal) {
      setState(() => _fontSize = (_fontSize + 1).clamp(10.0, 24.0));
      return;
    }

    // Ctrl+- → Zoom out
    if (hw.isControlPressed && logical == LogicalKeyboardKey.minus) {
      setState(() => _fontSize = (_fontSize - 1).clamp(10.0, 24.0));
      return;
    }

    // Ctrl+0 → Reset zoom
    if (hw.isControlPressed && logical == LogicalKeyboardKey.digit0) {
      setState(() => _fontSize = 13);
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
    final codeStyle = GoogleFonts.firaCode(fontSize: _fontSize, height: 1.45);
    final smallStyle = GoogleFonts.firaCode(fontSize: 11);

    return KeyboardListener(
      focusNode: FocusNode(),
      onKeyEvent: _handleKeyDown,
      child: Scaffold(
        backgroundColor: const Color(0xFF181825),
        body: Stack(
          children: [
            Column(
              children: [
                // ── Terminal tabs (VS Code tab bar) ──────────────
                _buildTabBar(smallStyle),

                // ── VS Code–style toolbar ───────────────────────
                _buildToolbar(smallStyle),

                // ── Debug toolbar ───────────────────────────────
                if (_debugMode) _buildDebugToolbar(smallStyle),

                // ── Output area ─────────────────────────────────
                Expanded(
                  child: Container(
                    color: const Color(0xFF1E1E2E),
                    child: _buildOutput(codeStyle),
                  ),
                ),

                // ── Input area ──────────────────────────────────
                _buildInputArea(codeStyle),

                // ── VS Code–style status bar ────────────────────
                _buildStatusBar(smallStyle),
              ],
            ),

            // ── Command palette overlay ─────────────────────────
            if (_showCommandPalette) _buildCommandPalette(),

            // ── Interpreter picker overlay ──────────────────────
            if (_showInterpreterPicker) _buildInterpreterPicker(),
          ],
        ),
      ),
    );
  }

  // ── Tab bar ─────────────────────────────────────────────────

  Widget _buildTabBar(TextStyle smallStyle) {
    return Container(
      height: 32,
      color: const Color(0xFF11111B),
      child: Row(
        children: [
          // New tab button
          InkWell(
            onTap: _newSession,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Icon(Icons.add, size: 14, color: Colors.white54),
            ),
          ),
          const VerticalDivider(width: 1, color: Colors.white12),

          // Tabs
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: _sessions.length,
              itemBuilder: (context, index) {
                final s = _sessions[index];
                final isActive = index == _activeSessionIndex;
                return GestureDetector(
                  onTap: () => _switchSession(index),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: isActive
                          ? const Color(0xFF1E1E2E)
                          : Colors.transparent,
                      border: Border(
                        right: BorderSide(color: Colors.white12),
                        bottom: BorderSide(
                          color: isActive
                              ? Colors.yellowAccent
                              : Colors.transparent,
                          width: 2,
                        ),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.code,
                          size: 12,
                          color: isActive
                              ? Colors.yellowAccent
                              : Colors.white38,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          s.name,
                          style: smallStyle.copyWith(
                            color:
                                isActive ? Colors.white : Colors.white54,
                            fontSize: 11,
                          ),
                        ),
                        if (_sessions.length > 1) ...[
                          const SizedBox(width: 6),
                          InkWell(
                            onTap: () => _closeSession(index),
                            child: Icon(Icons.close,
                                size: 10, color: Colors.white38),
                          ),
                        ],
                      ],
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

  // ── Toolbar ─────────────────────────────────────────────────

  Widget _buildToolbar(TextStyle smallStyle) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      color: const Color(0xFF11111B),
      child: Row(
        children: [
          const Icon(Icons.code, size: 16, color: Colors.yellowAccent),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              _active.name,
              style: smallStyle.copyWith(color: Colors.white70),
              maxLines: 1,
            ),
          ),
          _ToolbarIconButton(
            icon: Icons.play_arrow_rounded,
            tooltip: 'Run (F5)',
            color: Colors.greenAccent,
            enabled: true,
            onPressed: _runButton,
          ),
          const SizedBox(width: 2),
          _ToolbarIconButton(
            icon: Icons.stop_rounded,
            tooltip: 'Stop (Shift+F5)',
            color: Colors.redAccent,
            enabled: _active.running,
            onPressed: _stopButton,
          ),
          const SizedBox(width: 2),
          _ToolbarIconButton(
            icon: Icons.bug_report_rounded,
            tooltip: 'Toggle Debug Mode',
            color: _debugMode ? Colors.orangeAccent : Colors.white54,
            enabled: true,
            onPressed: _debugButton,
          ),
          const SizedBox(width: 8),
          _StatusChip(running: _active.running),
          const SizedBox(width: 8),
          _ToolbarIconButton(
            icon: Icons.refresh_rounded,
            tooltip: 'Restart',
            color: Colors.tealAccent,
            enabled: true,
            onPressed: _restartProcess,
          ),
          const SizedBox(width: 2),
          _ToolbarIconButton(
            icon: Icons.delete_sweep_rounded,
            tooltip: 'Clear (Ctrl+L)',
            color: Colors.orangeAccent,
            enabled: true,
            onPressed: () => setState(() => _active.history.clear()),
          ),
          const SizedBox(width: 2),
          _ToolbarIconButton(
            icon: _wordWrap ? Icons.wrap_text : Icons.short_text_rounded,
            tooltip: _wordWrap ? 'Word Wrap: ON' : 'Word Wrap: OFF',
            color: _wordWrap ? Colors.cyanAccent : Colors.white38,
            enabled: true,
            onPressed: () => setState(() => _wordWrap = !_wordWrap),
          ),
          const SizedBox(width: 2),
          _ToolbarIconButton(
            icon: _showLineNumbers
                ? Icons.format_list_numbered
                : Icons.format_list_numbered_sharp,
            tooltip: _showLineNumbers
                ? 'Line Numbers: ON'
                : 'Line Numbers: OFF',
            color: _showLineNumbers ? Colors.cyanAccent : Colors.white38,
            enabled: true,
            onPressed: () =>
                setState(() => _showLineNumbers = !_showLineNumbers),
          ),
        ],
      ),
    );
  }

  // ── Debug toolbar ───────────────────────────────────────────

  Widget _buildDebugToolbar(TextStyle smallStyle) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      color: const Color(0xFF1E1E2E),
      child: Row(
        children: [
          Icon(Icons.bug_report,
              size: 12, color: Colors.orangeAccent.shade200),
          const SizedBox(width: 4),
          Text('DEBUG',
              style: smallStyle.copyWith(
                  color: Colors.orangeAccent, fontWeight: FontWeight.bold)),
          const SizedBox(width: 12),
          _DebugAction(
              icon: Icons.skip_next_rounded,
              label: 'Step Over',
              shortcut: 'F10',
              enabled: _active.running),
          const SizedBox(width: 8),
          _DebugAction(
              icon: Icons.arrow_downward_rounded,
              label: 'Step Into',
              shortcut: 'F11',
              enabled: _active.running),
          const SizedBox(width: 8),
          _DebugAction(
              icon: Icons.arrow_upward_rounded,
              label: 'Step Out',
              shortcut: 'Shift+F11',
              enabled: _active.running),
          const SizedBox(width: 8),
          _DebugAction(
              icon: Icons.play_circle_outline_rounded,
              label: 'Continue',
              shortcut: 'F5',
              enabled: _active.running),
          const SizedBox(width: 8),
          _DebugAction(
              icon: Icons.restart_alt_rounded,
              label: 'Restart',
              shortcut: 'Ctrl+Shift+F5',
              enabled: true),
          const SizedBox(width: 8),
          _DebugAction(
              icon: Icons.stop_circle_rounded,
              label: 'Stop',
              shortcut: 'Shift+F5',
              enabled: _active.running),
        ],
      ),
    );
  }

  // ── Output ──────────────────────────────────────────────────

  Widget _buildOutput(TextStyle codeStyle) {
    if (_showLineNumbers) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Line numbers
          Container(
            width: 44,
            padding: const EdgeInsets.only(top: 12, right: 8),
            child: ListView.builder(
              controller: _scrollController,
              itemCount: _active.history.length,
              itemBuilder: (context, index) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 1),
                  child: Text(
                    '${index + 1}',
                    style: codeStyle.copyWith(
                      color: Colors.white24,
                      fontSize: _fontSize - 1,
                    ),
                    textAlign: TextAlign.right,
                  ),
                );
              },
            ),
          ),
          const VerticalDivider(width: 1, color: Colors.white10),
          // Content
          Expanded(
            child: _buildLogView(codeStyle),
          ),
        ],
      );
    }
    return _buildLogView(codeStyle);
  }

  Widget _buildLogView(TextStyle codeStyle) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(12),
      itemCount: _active.history.length,
      itemBuilder: (context, index) {
        final entry = _active.history[index];
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
            style: codeStyle.copyWith(color: color, fontSize: _fontSize),
            maxLines: _wordWrap ? null : 1,
          ),
        );
      },
    );
  }

  // ── Input area ──────────────────────────────────────────────

  Widget _buildInputArea(TextStyle codeStyle) {
    return Container(
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
                hintText: _active.running
                    ? 'Enter Python code… (F5 run, ↑↓ history, Ctrl+Shift+P palette)'
                    : 'Interpreter stopped — press ▶ to restart',
                hintStyle: codeStyle.copyWith(
                  color: Colors.white24,
                  fontStyle: FontStyle.italic,
                ),
              ),
              onSubmitted: _submitCode,
              enabled: _active.running,
              autofocus: true,
            ),
          ),
          if (_active.running)
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
    );
  }

  // ── Status bar ──────────────────────────────────────────────

  Widget _buildStatusBar(TextStyle smallStyle) {
    return GestureDetector(
      onTap: () => setState(() => _showInterpreterPicker = true),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
        color: const Color(0xFF007ACC),
        child: Row(
          children: [
            Icon(Icons.terminal,
                size: 11, color: Colors.white.withValues(alpha: 0.9)),
            const SizedBox(width: 4),
            // Interpreter path (clickable — like VS Code Python selector)
            Tooltip(
              message: 'Click to select interpreter',
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(3),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.code,
                        size: 11,
                        color: Colors.yellowAccent.withValues(alpha: 0.9)),
                    const SizedBox(width: 4),
                    Text(
                      'UmerOS Python',
                      style: smallStyle.copyWith(
                          color: Colors.white, fontSize: 10),
                    ),
                    const SizedBox(width: 4),
                    Icon(Icons.arrow_drop_down,
                        size: 12, color: Colors.white70),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 10),
            // Session info
            Text(
              '${_sessions.length} session${_sessions.length > 1 ? 's' : ''}',
              style:
                  smallStyle.copyWith(color: Colors.white70, fontSize: 10),
            ),
            const Spacer(),
            // Line count
            Text(
              '${_active.history.length} lines',
              style:
                  smallStyle.copyWith(color: Colors.white, fontSize: 10),
            ),
            const SizedBox(width: 10),
            // Exit code
            Text(
              'exit: ${_active.exitCode}',
              style:
                  smallStyle.copyWith(color: Colors.white, fontSize: 10),
            ),
            const SizedBox(width: 10),
            // Encoding
            Text(
              'UTF-8',
              style:
                  smallStyle.copyWith(color: Colors.white, fontSize: 10),
            ),
            const SizedBox(width: 10),
            // Font size
            Text(
              '${_fontSize.round()}px',
              style:
                  smallStyle.copyWith(color: Colors.white70, fontSize: 10),
            ),
            const SizedBox(width: 10),
            // Debug indicator
            if (_debugMode)
              Row(
                children: [
                  Icon(Icons.bug_report,
                      size: 10, color: Colors.white),
                  const SizedBox(width: 3),
                  Text('DEBUG',
                      style: smallStyle.copyWith(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.bold)),
                ],
              ),
          ],
        ),
      ),
    );
  }

  // ── Command palette overlay ─────────────────────────────────

  Widget _buildCommandPalette() {
    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: Material(
        color: Colors.black54,
        child: Center(
          child: Container(
            width: 500,
            margin: const EdgeInsets.only(top: 80),
            decoration: BoxDecoration(
              color: const Color(0xFF252536),
              borderRadius: BorderRadius.circular(6),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.5),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Search field
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: const BoxDecoration(
                    border: Border(
                      bottom: BorderSide(color: Colors.white12),
                    ),
                  ),
                  child: TextField(
                    controller: _paletteController,
                    focusNode: _paletteFocus,
                    style: GoogleFonts.firaCode(
                        fontSize: 13, color: Colors.white),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      isDense: true,
                      hintText: 'Type a command…',
                      hintStyle: GoogleFonts.firaCode(
                          fontSize: 13, color: Colors.white38),
                      prefixIcon: Icon(Icons.search,
                          size: 16, color: Colors.white54),
                    ),
                    onChanged: (_) => setState(() {}),
                    onSubmitted: (_) {
                      final cmds = _filteredCommands;
                      if (cmds.isNotEmpty) cmds.first.action();
                    },
                  ),
                ),
                // Command list
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 300),
                  child: ListView.builder(
                    shrinkWrap: true,
                    itemCount: _filteredCommands.length,
                    itemBuilder: (context, index) {
                      final cmd = _filteredCommands[index];
                      return InkWell(
                        onTap: cmd.action,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 8),
                          child: Row(
                            children: [
                              Icon(cmd.icon,
                                  size: 14, color: Colors.white54),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  cmd.label,
                                  style: GoogleFonts.firaCode(
                                      fontSize: 12,
                                      color: Colors.white70),
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── Interpreter picker overlay ──────────────────────────────

  Widget _buildInterpreterPicker() {
    final interpreters = [
      _InterpreterInfo(
        name: 'UmerOS Python (recommended)',
        path: _interpreterPath(),
        version: '3.x',
      ),
      _InterpreterInfo(
        name: 'System Python',
        path: 'python3',
        version: '3.x',
      ),
      _InterpreterInfo(
        name: 'Python 2 (legacy)',
        path: 'python2',
        version: '2.x',
      ),
    ];

    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      child: GestureDetector(
        onTap: () =>
            setState(() => _showInterpreterPicker = false),
        child: Material(
          color: Colors.black54,
          child: Center(
            child: GestureDetector(
              onTap: () {}, // absorb taps
              child: Container(
                width: 460,
                decoration: BoxDecoration(
                  color: const Color(0xFF252536),
                  borderRadius: BorderRadius.circular(6),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.5),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Header
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: const BoxDecoration(
                        border: Border(
                          bottom: BorderSide(color: Colors.white12),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.code,
                              size: 16, color: Colors.yellowAccent),
                          const SizedBox(width: 8),
                          Text(
                            'Select Python Interpreter',
                            style: GoogleFonts.firaCode(
                              fontSize: 13,
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const Spacer(),
                          IconButton(
                            icon: const Icon(Icons.close,
                                size: 16, color: Colors.white54),
                            onPressed: () => setState(
                                () => _showInterpreterPicker = false),
                          ),
                        ],
                      ),
                    ),
                    // Interpreter list
                    ...interpreters.map((interp) {
                      final isCurrent =
                          interp.path == _interpreterPath();
                      return ListTile(
                        leading: Icon(
                          isCurrent ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                          size: 16,
                          color: isCurrent
                              ? Colors.yellowAccent
                              : Colors.white38,
                        ),
                        title: Text(
                          interp.name,
                          style: GoogleFonts.firaCode(
                            fontSize: 12,
                            color: isCurrent
                                ? Colors.yellowAccent
                                : Colors.white70,
                          ),
                        ),
                        subtitle: Text(
                          '${interp.path} (${interp.version})',
                          style: GoogleFonts.firaCode(
                            fontSize: 10,
                            color: Colors.white38,
                          ),
                        ),
                        onTap: () {
                          setState(
                              () => _showInterpreterPicker = false);
                        },
                      );
                    }),
                    const SizedBox(height: 8),
                  ],
                ),
              ),
            ),
          ),
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

class _TerminalSession {
  final String name;
  Process? process;
  bool running = false;
  int exitCode = 0;
  String pendingLine = '';
  final List<_LogEntry> history = [];

  _TerminalSession({required this.name});
}

class _PaletteCommand {
  final String label;
  final IconData icon;
  final VoidCallback action;
  const _PaletteCommand({
    required this.label,
    required this.icon,
    required this.action,
  });
}

class _InterpreterInfo {
  final String name;
  final String path;
  final String version;
  const _InterpreterInfo({
    required this.name,
    required this.path,
    required this.version,
  });
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
