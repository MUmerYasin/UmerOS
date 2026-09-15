import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:google_fonts/google_fonts.dart';

/// Python interpreter with VS Code–style dual-panel layout:
/// top area = multi-line code editor, bottom = collapsible terminal output panel.
/// Press F5 or click Run to execute editor content.
class PythonInterpreterApp extends StatefulWidget {
  const PythonInterpreterApp({super.key});

  @override
  State<PythonInterpreterApp> createState() => _PythonInterpreterAppState();
}

class _PythonInterpreterAppState extends State<PythonInterpreterApp> {
  // ── Editor ──────────────────────────────────────────────────
  final TextEditingController _editorController = TextEditingController(
    text: 'print("Hello from UmerOS Python!")\n',
  );
  final FocusNode _editorFocus = FocusNode();

  // ── Terminal output ─────────────────────────────────────────
  final TextEditingController _terminalInput = TextEditingController();
  final FocusNode _terminalFocus = FocusNode();
  final ScrollController _terminalScrollController = ScrollController();
  final List<_LogEntry> _outputLines = [];
  bool _showTerminal = true;

  // ── Settings ────────────────────────────────────────────────
  double _fontSize = 13;
  bool _wordWrap = false;
  bool _showLineNumbers = true;

  // ── Process ─────────────────────────────────────────────────
  Process? _process;
  bool _running = false;
  int _exitCode = 0;
  String _pendingLine = '';
  bool _debugMode = false;

  // ── History ─────────────────────────────────────────────────
  final List<String> _inputHistory = [];


  // ── Command palette ─────────────────────────────────────────
  bool _showCommandPalette = false;
  final TextEditingController _paletteController = TextEditingController();
  final FocusNode _paletteFocus = FocusNode();

  // ── Interpreter picker ──────────────────────────────────────
  bool _showInterpreterPicker = false;

  static const String _exeName = 'umeros_python.exe';

  // ── File state ─────────────────────────────────────────────
  String? _currentFilePath;
  String _currentFileName = 'untitled.py';

  @override
  void initState() {
    super.initState();
    _startProcess();
  }

  @override
  void dispose() {
    _process?.kill();
    _editorController.dispose();
    _editorFocus.dispose();
    _terminalInput.dispose();
    _terminalFocus.dispose();
    _terminalScrollController.dispose();
    _paletteController.dispose();
    _paletteFocus.dispose();
    super.dispose();
  }

  // ── Process management ──────────────────────────────────────

  String _findInterpreter() {
    final exeDir = File(Platform.resolvedExecutable).parent;
    final sep = Platform.pathSeparator;

    // 1. Same dir as Flutter exe
    final local = '${exeDir.path}$sep$_exeName';
    if (File(local).existsSync()) return local;

    // 2. UmerOS/boot/python_vm/build/
    //    Flutter exe: .../flutter_ui/build/windows/x64/runner/Debug/
    //    Go up 6 levels → UmerOS root
    final root6 = exeDir.parent.parent.parent.parent.parent.parent;
    final p1 = '${root6.path}${sep}boot${sep}python_vm${sep}build${sep}$_exeName';
    if (File(p1).existsSync()) return p1;

    // 3. UmerOS/boot/python_vm/ (no build subdir)
    final p2 = '${root6.path}${sep}boot${sep}python_vm${sep}$_exeName';
    if (File(p2).existsSync()) return p2;

    // 4. Fallback: bare name (relies on PATH)
    return _exeName;
  }

  String _workingDir() {
    return Platform.environment['HOME'] ??
        Platform.environment['USERPROFILE'] ??
        '.';
  }

  Future<void> _startProcess() async {
    try {
      final exePath = _findInterpreter();
      final proc = await Process.start(
        exePath,
        [],
        workingDirectory: _workingDir(),
      );
      _process = proc;
      _running = true;
      _exitCode = 0;

      setState(() {
        _outputLines.add(const _LogEntry(
          type: _EntryType.system,
          text: '── UmerOS Python Interpreter ──\n'
              'F5 Run | Shift+F5 Stop | Ctrl+L Clear\n'
              'Type code in the editor, press Run to execute.',
        ));
      });

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
            _running = false;
            _exitCode = code;
            _outputLines.add(_LogEntry(
              type: _EntryType.system,
              text: '[Process exited with code $code]',
            ));
          });
        }
      });
    } catch (e) {
      setState(() {
        _outputLines.add(_LogEntry(
          type: _EntryType.error,
          text: 'Failed to start interpreter: $e',
        ));
      });
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
      _outputLines.clear();
    });
    _startProcess();
  }

  // ── Stream handlers ─────────────────────────────────────────

  void _onStdout(String line) {
    if (!mounted) return;
    setState(() {
      if (_pendingLine.isNotEmpty) {
        _outputLines
            .add(_LogEntry(type: _EntryType.input, text: _pendingLine));
        _pendingLine = '';
      }
      _outputLines.add(_LogEntry(type: _EntryType.output, text: line));
    });
    _scrollTerminalToBottom();
  }

  void _onStderr(String line) {
    if (!mounted) return;
    setState(() {
      if (_pendingLine.isNotEmpty) {
        _outputLines
            .add(_LogEntry(type: _EntryType.input, text: _pendingLine));
        _pendingLine = '';
      }
      _outputLines.add(_LogEntry(type: _EntryType.error, text: line));
    });
    _scrollTerminalToBottom();
  }

  void _scrollTerminalToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_terminalScrollController.hasClients) {
        _terminalScrollController.animateTo(
          _terminalScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 80),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ── Actions ─────────────────────────────────────────────────

  /// Run entire editor content line-by-line via REPL stdin.
  void _runEditorCode() {
    if (!_running) {
      _restartProcess();
      return;
    }
    final code = _editorController.text;
    if (code.trim().isEmpty) return;

    final lines = code.split('\n');
    setState(() {
      _outputLines.add(_LogEntry(
        type: _EntryType.system,
        text: '── Run ──',
      ));
    });
    for (final line in lines) {
      if (line.trim().isNotEmpty) {
        _process?.stdin.writeln(line);
      }
    }
    _editorFocus.requestFocus();
  }

  /// Submit single line from terminal REPL input bar.
  void _submitTerminalLine(String text) {
    _terminalInput.clear();
    if (text.trim().isEmpty || !_running) return;

    if (text.trim().toLowerCase() == 'exit') {
      _killProcess();
      setState(() {
        _outputLines.add(const _LogEntry(
          type: _EntryType.system,
          text: '[Interpreter exited]',
        ));
      });
      return;
    }

    _inputHistory.add(text);

    setState(() {
      _pendingLine = '>>> $text';
    });
    _process?.stdin.writeln(text);
  }

  void _stopButton() {
    if (_running) {
      _killProcess();
      setState(() {
        _outputLines.add(const _LogEntry(
          type: _EntryType.system,
          text: '[Process stopped by user]',
        ));
      });
    }
  }

  void _clearOutput() {
    setState(() => _outputLines.clear());
  }

  // ── Command palette ─────────────────────────────────────────

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
          label: 'Run (F5)',
          icon: Icons.play_arrow_rounded,
          action: () {
            _runEditorCode();
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Stop (Shift+F5)',
          icon: Icons.stop_rounded,
          action: () {
            _stopButton();
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Restart Interpreter',
          icon: Icons.refresh_rounded,
          action: () {
            _restartProcess();
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Clear Output (Ctrl+L)',
          icon: Icons.delete_sweep_rounded,
          action: () {
            _clearOutput();
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Toggle Terminal Panel',
          icon: Icons.terminal,
          action: () {
            setState(() => _showTerminal = !_showTerminal);
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
        _PaletteCommand(
          label: 'Toggle Debug Mode',
          icon: Icons.bug_report_rounded,
          action: () {
            setState(() => _debugMode = !_debugMode);
            _showCommandPalette = false;
          },
        ),
        _PaletteCommand(
          label: 'Select Interpreter',
          icon: Icons.code,
          action: () {
            setState(() => _showInterpreterPicker = true);
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

  // ── File operations ─────────────────────────────────────────

  Future<void> _openFile() async {
    final result = await FilePicker.platform.pickFiles(
      dialogTitle: 'Open Python File',
      allowedExtensions: ['py', 'pyw', 'txt'],
      type: FileType.custom,
    );
    if (result != null && result.files.single.path != null) {
      final path = result.files.single.path!;
      final content = await File(path).readAsString();
      setState(() {
        _editorController.text = content;
        _currentFilePath = path;
        _currentFileName = path.split(Platform.pathSeparator).last;
      });
    }
  }

  Future<void> _saveFile() async {
    if (_currentFilePath != null) {
      await File(_currentFilePath!).writeAsString(_editorController.text);
    } else {
      await _saveFileAs();
    }
  }

  Future<void> _saveFileAs() async {
    final path = await FilePicker.platform.saveFile(
      dialogTitle: 'Save Python File',
      fileName: _currentFileName,
      allowedExtensions: ['py', 'pyw'],
      type: FileType.custom,
    );
    if (path != null) {
      await File(path).writeAsString(_editorController.text);
      setState(() {
        _currentFilePath = path;
        _currentFileName = path.split(Platform.pathSeparator).last;
      });
    }
  }

  // ── Keyboard shortcuts ──────────────────────────────────────

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

    // F5 → Run
    if (logical == LogicalKeyboardKey.f5) {
      _runEditorCode();
      return;
    }

    // Shift+F5 → Stop
    if (hw.isShiftPressed && logical == LogicalKeyboardKey.f5) {
      _stopButton();
      return;
    }

    // Ctrl+L → Clear
    if (hw.isControlPressed && logical == LogicalKeyboardKey.keyL) {
      _clearOutput();
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

    // Ctrl+O → Open file
    if (hw.isControlPressed && logical == LogicalKeyboardKey.keyO) {
      _openFile();
      return;
    }

    // Ctrl+S → Save file
    if (hw.isControlPressed && !hw.isShiftPressed && logical == LogicalKeyboardKey.keyS) {
      _saveFile();
      return;
    }

    // Ctrl+Shift+S → Save As
    if (hw.isControlPressed && hw.isShiftPressed && logical == LogicalKeyboardKey.keyS) {
      _saveFileAs();
      return;
    }

    // Ctrl+Enter → Run from editor
    if (hw.isControlPressed && logical == LogicalKeyboardKey.enter) {
      _runEditorCode();
      return;
    }
  }

  // ── Build ───────────────────────────────────────────────────

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
                // ── Toolbar ─────────────────────────────────────
                _buildToolbar(smallStyle),
                // ── Editor (top area) ───────────────────────────
                Expanded(
                  flex: _showTerminal ? 65 : 100,
                  child: _buildEditor(codeStyle),
                ),
                // ── Terminal panel (bottom, collapsible) ────────
                if (_showTerminal) ...[
                  _buildTerminalDivider(),
                  Expanded(
                    flex: 35,
                    child: _buildTerminalPanel(codeStyle, smallStyle),
                  ),
                ],
                // ── Status bar ─────────────────────────────────
                _buildStatusBar(smallStyle),
              ],
            ),

            // ── Command palette overlay ────────────────────────
            if (_showCommandPalette) _buildCommandPalette(),

            // ── Interpreter picker overlay ─────────────────────
            if (_showInterpreterPicker) _buildInterpreterPicker(),
          ],
        ),
      ),
    );
  }

  // ── Toolbar ───────────────────────────────────────────────

  Widget _buildToolbar(TextStyle smallStyle) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      color: const Color(0xFF11111B),
      child: Row(
        children: [
          const Icon(Icons.code, size: 16, color: Colors.yellowAccent),
          const SizedBox(width: 6),
          Text(
            'Python Interpreter',
            style: smallStyle.copyWith(color: Colors.white70),
          ),
          if (_currentFileName.isNotEmpty) ...[
            Text(
              ' — $_currentFileName',
              style: smallStyle.copyWith(color: Colors.white38),
            ),
          ],
          const SizedBox(width: 12),
          // ── File menu ─────────────────────────────────
          PopupMenuButton<String>(
            onSelected: (value) {
              switch (value) {
                case 'open':
                  _openFile();
                case 'save':
                  _saveFile();
                case 'save_as':
                  _saveFileAs();
              }
            },
            offset: const Offset(0, 28),
            color: const Color(0xFF2A2A3E),
            icon: Icon(Icons.folder_rounded, size: 16, color: Colors.white54),
            tooltip: 'File',
            itemBuilder: (_) => [
              _fileMenuItem('open', 'Open…', Icons.file_open_rounded, 'Ctrl+O'),
              _fileMenuItem('save', 'Save', Icons.save_rounded, 'Ctrl+S'),
              _fileMenuItem(
                  'save_as', 'Save As…', Icons.save_alt_rounded, 'Ctrl+Shift+S'),
            ],
          ),
          const Spacer(),
          // Run button
          _ToolbarIconButton(
            icon: Icons.play_arrow_rounded,
            tooltip: 'Run (F5)',
            color: Colors.greenAccent,
            enabled: true,
            onPressed: _runEditorCode,
          ),
          const SizedBox(width: 2),
          // Stop button
          _ToolbarIconButton(
            icon: Icons.stop_rounded,
            tooltip: 'Stop (Shift+F5)',
            color: Colors.redAccent,
            enabled: _running,
            onPressed: _stopButton,
          ),
          const SizedBox(width: 2),
          // Restart
          _ToolbarIconButton(
            icon: Icons.refresh_rounded,
            tooltip: 'Restart',
            color: Colors.tealAccent,
            enabled: true,
            onPressed: _restartProcess,
          ),
          const SizedBox(width: 2),
          // Debug toggle
          _ToolbarIconButton(
            icon: Icons.bug_report_rounded,
            tooltip: 'Toggle Debug Mode',
            color: _debugMode ? Colors.orangeAccent : Colors.white54,
            enabled: true,
            onPressed: () => setState(() => _debugMode = !_debugMode),
          ),
          const SizedBox(width: 8),
          // Status chip
          _StatusChip(running: _running),
          const SizedBox(width: 8),
          // Clear output
          _ToolbarIconButton(
            icon: Icons.delete_sweep_rounded,
            tooltip: 'Clear Output (Ctrl+L)',
            color: Colors.orangeAccent,
            enabled: true,
            onPressed: _clearOutput,
          ),
          const SizedBox(width: 2),
          // Toggle terminal
          _ToolbarIconButton(
            icon: _showTerminal
                ? Icons.terminal
                : Icons.terminal_rounded,
            tooltip: _showTerminal ? 'Hide Terminal' : 'Show Terminal',
            color: _showTerminal ? Colors.cyanAccent : Colors.white38,
            enabled: true,
            onPressed: () => setState(() => _showTerminal = !_showTerminal),
          ),
          const SizedBox(width: 2),
          // Word wrap
          _ToolbarIconButton(
            icon: _wordWrap ? Icons.wrap_text : Icons.short_text_rounded,
            tooltip: _wordWrap ? 'Word Wrap: ON' : 'Word Wrap: OFF',
            color: _wordWrap ? Colors.cyanAccent : Colors.white38,
            enabled: true,
            onPressed: () => setState(() => _wordWrap = !_wordWrap),
          ),
          const SizedBox(width: 2),
          // Line numbers
          _ToolbarIconButton(
            icon: Icons.format_list_numbered,
            tooltip:
                _showLineNumbers ? 'Line Numbers: ON' : 'Line Numbers: OFF',
            color: _showLineNumbers ? Colors.cyanAccent : Colors.white38,
            enabled: true,
            onPressed: () =>
                setState(() => _showLineNumbers = !_showLineNumbers),
          ),
        ],
      ),
    );
  }

  // ── Editor panel ─────────────────────────────────────────

  Widget _buildEditor(TextStyle codeStyle) {
    return Container(
      color: const Color(0xFF1E1E2E),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Line numbers
          if (_showLineNumbers) ...[
            _EditorLineNumbers(
              controller: _editorController,
              fontSize: _fontSize,
              codeStyle: codeStyle,
            ),
            const VerticalDivider(width: 1, color: Colors.white10),
          ],
          // Text editor
          Expanded(
            child: TextField(
              controller: _editorController,
              focusNode: _editorFocus,
              style: codeStyle.copyWith(color: Colors.white),
              maxLines: null,
              expands: true,
              keyboardType: TextInputType.multiline,
              textAlignVertical: TextAlignVertical.top,
              decoration: InputDecoration(
                border: InputBorder.none,
                contentPadding: const EdgeInsets.all(12),
                hintText: '# Write Python code here...\n# Press F5 or Ctrl+Enter to run',
                hintStyle: codeStyle.copyWith(
                  color: Colors.white24,
                  fontStyle: FontStyle.italic,
                ),
              ),
              onChanged: (_) => setState(() {}),
              onTapOutside: (_) {},
            ),
          ),
        ],
      ),
    );
  }

  // ── Terminal panel ───────────────────────────────────────

  Widget _buildTerminalDivider() {
    return GestureDetector(
      onVerticalDragUpdate: (details) {
        // Could implement resize here if needed
      },
      child: Container(
        height: 4,
        color: const Color(0xFF11111B),
        child: Center(
          child: Container(
            width: 40,
            height: 2,
            decoration: BoxDecoration(
              color: Colors.white24,
              borderRadius: BorderRadius.circular(1),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTerminalPanel(TextStyle codeStyle, TextStyle smallStyle) {
    return Column(
      children: [
        // Terminal header
        _buildTerminalHeader(smallStyle),
        // Terminal output
        Expanded(
          child: Container(
            color: const Color(0xFF11111B),
            child: _buildTerminalOutput(codeStyle),
          ),
        ),
        // Terminal REPL input
        if (_running) _buildTerminalInput(codeStyle),
      ],
    );
  }

  Widget _buildTerminalHeader(TextStyle smallStyle) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      color: const Color(0xFF11111B),
      child: Row(
        children: [
          Icon(Icons.terminal, size: 12, color: Colors.cyanAccent),
          const SizedBox(width: 6),
          Text(
            'OUTPUT',
            style: smallStyle.copyWith(
              color: Colors.cyanAccent,
              fontWeight: FontWeight.bold,
            ),
          ),
          const Spacer(),
          Text(
            '${_outputLines.length} lines',
            style: smallStyle.copyWith(color: Colors.white38, fontSize: 10),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _clearOutput,
            child: Icon(Icons.delete_sweep, size: 12, color: Colors.white38),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () => setState(() => _showTerminal = false),
            child: Icon(Icons.close, size: 12, color: Colors.white38),
          ),
        ],
      ),
    );
  }

  Widget _buildTerminalOutput(TextStyle codeStyle) {
    if (_outputLines.isEmpty) {
      return Center(
        child: Text(
          'No output yet. Press F5 to run your code.',
          style: codeStyle.copyWith(
            color: Colors.white24,
            fontStyle: FontStyle.italic,
          ),
        ),
      );
    }

    return ListView.builder(
      controller: _terminalScrollController,
      padding: const EdgeInsets.all(8),
      itemCount: _outputLines.length,
      itemBuilder: (context, index) {
        final entry = _outputLines[index];
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
            style: codeStyle.copyWith(
              color: color,
              fontSize: (_fontSize - 1).clamp(10.0, 22.0),
            ),
            maxLines: _wordWrap ? null : 1,
          ),
        );
      },
    );
  }

  Widget _buildTerminalInput(TextStyle codeStyle) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      color: const Color(0xFF181825),
      child: Row(
        children: [
          Text(
            '>>> ',
            style: codeStyle.copyWith(
              color: Colors.yellowAccent,
              fontSize: _fontSize - 1,
            ),
          ),
          Expanded(
            child: TextField(
              controller: _terminalInput,
              focusNode: _terminalFocus,
              style: codeStyle.copyWith(
                color: Colors.white,
                fontSize: _fontSize - 1,
              ),
              decoration: InputDecoration(
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
                hintText: 'REPL input...',
                hintStyle: codeStyle.copyWith(
                  color: Colors.white24,
                  fontStyle: FontStyle.italic,
                  fontSize: _fontSize - 1,
                ),
              ),
              onSubmitted: _submitTerminalLine,
            ),
          ),
        ],
      ),
    );
  }

  // ── File menu item helper ───────────────────────────────

  PopupMenuItem<String> _fileMenuItem(
    String value,
    String label,
    IconData icon,
    String shortcut,
  ) {
    return PopupMenuItem<String>(
      value: value,
      child: Row(
        children: [
          Icon(icon, size: 14, color: Colors.white60),
          const SizedBox(width: 8),
          Expanded(
            child: Text(label, style: const TextStyle(color: Colors.white, fontSize: 13)),
          ),
          Text(
            shortcut,
            style: const TextStyle(color: Colors.white38, fontSize: 11),
          ),
        ],
      ),
    );
  }

  // ── Status bar ───────────────────────────────────────────

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
            // Interpreter selector
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
            // Editor line count
            Text(
              'Ln ${_editorController.text.split('\n').length}',
              style:
                  smallStyle.copyWith(color: Colors.white70, fontSize: 10),
            ),
            const SizedBox(width: 10),
            // Char count
            Text(
              '${_editorController.text.length} chars',
              style:
                  smallStyle.copyWith(color: Colors.white70, fontSize: 10),
            ),
            const Spacer(),
            // Output lines
            Text(
              '${_outputLines.length} lines output',
              style:
                  smallStyle.copyWith(color: Colors.white, fontSize: 10),
            ),
            const SizedBox(width: 10),
            // Exit code
            Text(
              'exit: $_exitCode',
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
            // Debug indicator
            if (_debugMode) ...[
              const SizedBox(width: 10),
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
          ],
        ),
      ),
    );
  }

  // ── Command palette overlay ───────────────────────────────

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
                      hintText: 'Type a command...',
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

  // ── Interpreter picker overlay ────────────────────────────

  Widget _buildInterpreterPicker() {
    final interpreters = [
      _InterpreterInfo(
        name: 'UmerOS Python (recommended)',
        path: _findInterpreter(),
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
              onTap: () {},
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
                          interp.path == _findInterpreter();
                      return ListTile(
                        leading: Icon(
                          isCurrent
                              ? Icons.radio_button_checked
                              : Icons.radio_button_unchecked,
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

// ── Helpers ───────────────────────────────────────────────────

enum _EntryType { system, input, output, error }

class _LogEntry {
  final _EntryType type;
  final String text;
  const _LogEntry({required this.type, required this.text});
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

/// Line numbers gutter for the code editor.
class _EditorLineNumbers extends StatelessWidget {
  final TextEditingController controller;
  final double fontSize;
  final TextStyle codeStyle;

  const _EditorLineNumbers({
    required this.controller,
    required this.fontSize,
    required this.codeStyle,
  });

  @override
  Widget build(BuildContext context) {
    final lineCount = controller.text.split('\n').length;
    return Container(
      width: 44,
      padding: const EdgeInsets.only(top: 12, right: 8),
      child: ListView.builder(
        itemCount: lineCount,
        itemBuilder: (context, index) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 1),
            child: Text(
              '${index + 1}',
              style: codeStyle.copyWith(
                color: Colors.white24,
                fontSize: fontSize - 1,
              ),
              textAlign: TextAlign.right,
            ),
          );
        },
      ),
    );
  }
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
