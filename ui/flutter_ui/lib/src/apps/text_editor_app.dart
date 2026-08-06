import 'package:flutter/material.dart';

class TextEditorApp extends StatefulWidget {
  const TextEditorApp({super.key});

  @override
  State<TextEditorApp> createState() => _TextEditorAppState();
}

class _TextEditorAppState extends State<TextEditorApp> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _showFindReplace = false;
  String _findText = '';
  String _replaceText = '';
  int _currentLine = 1;
  int _currentCol = 1;
  int _lineCount = 1;
  int _wordCount = 0;
  int _charCount = 0;
  String _languageMode = 'Plain Text';

  final List<Map<String, dynamic>> _openFiles = [
    {'name': 'untitled.txt', 'content': '', 'modified': false},
  ];
  int _activeTabIndex = 0;

  final List<String> _languageModes = [
    'Plain Text',
    'Dart',
    'Python',
    'JavaScript',
    'TypeScript',
    'C',
    'C++',
    'Java',
    'Rust',
    'Go',
    'HTML',
    'CSS',
    'JSON',
    'YAML',
    'Markdown',
    'Shell',
    'SQL',
  ];

  @override
  void initState() {
    super.initState();
    _textController.addListener(_updateStats);
    _updateStats();
  }

  @override
  void dispose() {
    _textController.removeListener(_updateStats);
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _updateStats() {
    final text = _textController.text;
    setState(() {
      _charCount = text.length;
      _wordCount = text.trim().isEmpty ? 0 : text.trim().split(RegExp(r'\s+')).length;
      _lineCount = text.split('\n').length;
    });
  }

  void _newFile() {
    setState(() {
      _openFiles.add({'name': 'untitled${_openFiles.length}.txt', 'content': '', 'modified': false});
      _activeTabIndex = _openFiles.length - 1;
      _textController.clear();
    });
  }

  void _closeTab(int index) {
    if (_openFiles.length <= 1) return;
    setState(() {
      _openFiles.removeAt(index);
      if (_activeTabIndex >= _openFiles.length) {
        _activeTabIndex = _openFiles.length - 1;
      }
      _textController.text = _openFiles[_activeTabIndex]['content'] ?? '';
    });
  }

  void _selectTab(int index) {
    setState(() {
      _openFiles[_activeTabIndex]['content'] = _textController.text;
      _activeTabIndex = index;
      _textController.text = _openFiles[index]['content'] ?? '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Column(
      children: [
        _buildToolbar(colorScheme),
        if (_showFindReplace) _buildFindReplaceBar(colorScheme),
        _buildTabBar(colorScheme, textTheme),
        Expanded(
          child: Row(
            children: [
              _buildLineNumbers(colorScheme),
              Expanded(child: _buildEditorArea(colorScheme)),
            ],
          ),
        ),
        _buildStatusBar(colorScheme, textTheme),
      ],
    );
  }

  Widget _buildToolbar(ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: Border(
          bottom: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: Row(
        children: [
          _toolButton(Icons.add, 'New', _newFile, colorScheme),
          _toolButton(Icons.folder_open, 'Open', () {}, colorScheme),
          _toolButton(Icons.save, 'Save', () {}, colorScheme),
          const SizedBox(width: 8),
          Container(width: 1, height: 24, color: colorScheme.outline.withValues(alpha: 0.3)),
          const SizedBox(width: 8),
          _toolButton(Icons.undo, 'Undo', () {}, colorScheme),
          _toolButton(Icons.redo, 'Redo', () {}, colorScheme),
          const SizedBox(width: 8),
          Container(width: 1, height: 24, color: colorScheme.outline.withValues(alpha: 0.3)),
          const SizedBox(width: 8),
          _toolButton(Icons.find_replace, 'Find', () {
            setState(() => _showFindReplace = !_showFindReplace);
          }, colorScheme),
        ],
      ),
    );
  }

  Widget _toolButton(IconData icon, String tooltip, VoidCallback onPressed, ColorScheme colorScheme) {
    return Tooltip(
      message: tooltip,
      child: IconButton(
        icon: Icon(icon, size: 20),
        onPressed: onPressed,
        style: IconButton.styleFrom(
          foregroundColor: colorScheme.onSurface.withValues(alpha: 0.8),
        ),
        padding: const EdgeInsets.all(8),
        constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
      ),
    );
  }

  Widget _buildFindReplaceBar(ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHigh,
        border: Border(
          bottom: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Find...',
                prefixIcon: const Icon(Icons.search, size: 18),
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(4),
                  borderSide: BorderSide(color: colorScheme.outline),
                ),
              ),
              onChanged: (value) => _findText = value,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Replace...',
                prefixIcon: const Icon(Icons.find_replace, size: 18),
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(4),
                  borderSide: BorderSide(color: colorScheme.outline),
                ),
              ),
              onChanged: (value) => _replaceText = value,
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            icon: const Icon(Icons.arrow_forward, size: 18),
            tooltip: 'Replace',
            onPressed: () {},
          ),
          IconButton(
            icon: const Icon(Icons.find_replace, size: 18),
            tooltip: 'Replace All',
            onPressed: () {},
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 18),
            tooltip: 'Close',
            onPressed: () => setState(() => _showFindReplace = false),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      height: 36,
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        border: Border(
          bottom: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: _openFiles.length,
        itemBuilder: (context, index) {
          final file = _openFiles[index];
          final isActive = index == _activeTabIndex;
          return GestureDetector(
            onTap: () => _selectTab(index),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                color: isActive ? colorScheme.surface : Colors.transparent,
                border: Border(
                  right: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
                  bottom: isActive
                      ? BorderSide(color: colorScheme.primary, width: 2)
                      : BorderSide.none,
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    file['name'].toString().endsWith('.dart')
                        ? Icons.code
                        : Icons.description,
                    size: 14,
                    color: colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    file['name'].toString(),
                    style: textTheme.bodySmall?.copyWith(
                      color: isActive
                          ? colorScheme.onSurface
                          : colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                  if (file['modified'] == true) ...[
                    const SizedBox(width: 4),
                    Icon(Icons.circle, size: 6, color: colorScheme.primary),
                  ],
                  if (_openFiles.length > 1) ...[
                    const SizedBox(width: 4),
                    GestureDetector(
                      onTap: () => _closeTab(index),
                      child: Icon(
                        Icons.close,
                        size: 12,
                        color: colorScheme.onSurface.withValues(alpha: 0.5),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildLineNumbers(ColorScheme colorScheme) {
    return Container(
      width: 50,
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
      child: ListView.builder(
        controller: _scrollController,
        itemCount: _lineCount,
        itemBuilder: (context, index) {
          return Container(
            height: 20,
            alignment: Alignment.centerRight,
            padding: const EdgeInsets.only(right: 8),
            child: Text(
              '${index + 1}',
              style: TextStyle(
                fontSize: 12,
                color: colorScheme.onSurface.withValues(alpha: 0.4),
                fontFamily: 'monospace',
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildEditorArea(ColorScheme colorScheme) {
    return TextField(
      controller: _textController,
      scrollController: _scrollController,
      maxLines: null,
      expands: true,
      keyboardType: TextInputType.multiline,
      style: TextStyle(
        fontSize: 14,
        fontFamily: 'monospace',
        color: colorScheme.onSurface,
      ),
      decoration: InputDecoration(
        border: InputBorder.none,
        contentPadding: const EdgeInsets.all(12),
        hintText: 'Start typing...',
        hintStyle: TextStyle(color: colorScheme.onSurface.withValues(alpha: 0.3)),
      ),
      onChanged: (value) {
        _updateStats();
        setState(() {
          _openFiles[_activeTabIndex]['modified'] = true;
        });
      },
    );
  }

  Widget _buildStatusBar(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: colorScheme.primaryContainer.withValues(alpha: 0.5),
        border: Border(
          top: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: Row(
        children: [
          _statusItem('Lines: $_lineCount', colorScheme),
          const SizedBox(width: 16),
          _statusItem('Words: $_wordCount', colorScheme),
          const SizedBox(width: 16),
          _statusItem('Chars: $_charCount', colorScheme),
          const SizedBox(width: 16),
          _statusItem('Ln $_currentLine, Col $_currentCol', colorScheme),
          const Spacer(),
          _statusItem('UTF-8', colorScheme),
          const SizedBox(width: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: colorScheme.surface.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(4),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _languageMode,
                isDense: true,
                style: textTheme.bodySmall?.copyWith(color: colorScheme.onSurface),
                items: _languageModes.map((mode) {
                  return DropdownMenuItem(value: mode, child: Text(mode));
                }).toList(),
                onChanged: (value) => setState(() => _languageMode = value!),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _statusItem(String text, ColorScheme colorScheme) {
    return Text(
      text,
      style: TextStyle(
        fontSize: 12,
        color: colorScheme.onSurface.withValues(alpha: 0.7),
      ),
    );
  }
}
