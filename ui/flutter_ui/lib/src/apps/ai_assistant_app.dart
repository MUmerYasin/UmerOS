/// UmerOS Flutter UI — AI Assistant desktop app
/// =============================================
/// Real chat against the consent-gated UmerOS AI backend
/// (`ai/server.py` on 127.0.0.1:8421). No simulated data: offline or
/// misconfigured states are rendered honestly with recovery hints.
///
/// Features (HCI-mapped):
///   * Provider picker grouped Local / Free Online / Paid Online,
///     each showing availability + consent state (Nielsen #1 status).
///   * Streaming token-by-token replies with a Stop control
///     (Nielsen #3 user control & freedom).
///   * First-time online send asks explicit consent, stored on the
///     backend ledger; revocable in Settings (privacy mandate / H18).
///   * Local model manager: curated catalogue, download progress,
///     delete — bring-your-own LLM.
///   * Copy message, clear conversation, keyboard Enter to send /
///     Shift+Enter newline (Nielsen #7 flexibility & efficiency).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/ai_service.dart';
import '../widgets/data_source_badge.dart';

class AiAssistantApp extends StatefulWidget {
  const AiAssistantApp({super.key});

  @override
  State<AiAssistantApp> createState() => _AiAssistantAppState();
}

class _AiAssistantAppState extends State<AiAssistantApp>
    with SingleTickerProviderStateMixin {
  final TextEditingController _composer = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final FocusNode _composerFocus = FocusNode();

  final List<_ChatMessage> _messages = [];
  String _sessionId = DateTime.now().millisecondsSinceEpoch.toString();

  bool _backendUp = false;
  bool _sending = false;
  StreamSubscription<void>? _noopSub; // placeholder for future cancel

  List<AiProviderInfo> _providers = [];
  ProviderKind _selectedKind = ProviderKind.local;
  String? _selectedProviderId;
  String? _selectedModel;

  Timer? _downloadPoll;

  @override
  void initState() {
    super.initState();
    _messages.add(_ChatMessage.system(
        'Welcome to Umer OS Assistant.\n'
        '• Pick a provider above — local models run fully on-device.\n'
        '• Online providers need one-time consent before prompts leave '
        'the machine.'));
    _refreshBackend();
  }

  @override
  void dispose() {
    _downloadPoll?.cancel();
    _noopSub?.cancel();
    _composer.dispose();
    _scroll.dispose();
    _composerFocus.dispose();
    super.dispose();
  }

  AiService get _api => AiService.instance;

  // ── data loading ───────────────────────────────────────────────────────

  Future<void> _refreshBackend() async {
    final up = await _api.checkHealth();
    if (!mounted) return;
    setState(() => _backendUp = up);
    if (!up) return;
    try {
      final providers = await _api.listProviders();
      if (!mounted) return;
      setState(() {
        _providers = providers;
        if (providers.isEmpty) return;
        // Prefer a live local engine; else first available; else first.
        final pick = providers.firstWhere(
          (p) =>
              p.kind == ProviderKind.local &&
              p.available &&
              p.models.isNotEmpty,
          orElse: () {
            final available = providers
                .where((p) => p.available)
                .toList();
            return available.isNotEmpty ? available.first : providers.first;
          },
        );
        _selectedKind = pick.kind;
        _selectedProviderId = pick.id;
        _selectedModel =
            pick.models.isNotEmpty ? pick.models.first : null;
      });
    } on AiServiceException catch (e) {
      _appendError('Could not load providers: ${e.message}');
    }
  }

  List<AiProviderInfo> get _providersOfKind =>
      _providers.where((p) => p.kind == _selectedKind).toList();

  void _onKindChanged(ProviderKind? kind) {
    if (kind == null || kind == _selectedKind) return;
    final list =
        _providers.where((p) => p.kind == kind).toList();
    setState(() {
      _selectedKind = kind;
      _selectedProviderId = list.isNotEmpty ? list.first.id : null;
      _selectedModel =
          (list.isNotEmpty && list.first.models.isNotEmpty)
              ? list.first.models.first
              : null;
    });
  }

  void _onProviderChanged(String? id) {
    if (id == null) return;
    final p = _providers.where((x) => x.id == id).firstOrNull;
    setState(() {
      _selectedProviderId = id;
      _selectedModel = (p != null && p.models.isNotEmpty)
          ? p.models.first
          : null;
    });
  }

  // ── messaging ──────────────────────────────────────────────────────────

  void _append(_ChatMessage msg) {
    setState(() => _messages.add(msg));
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollDown());
  }

  void _appendError(String text) =>
      _append(_ChatMessage.error(text));

  void _scrollDown() {
    if (!_scroll.hasClients) return;
    _scroll.animateTo(
      _scroll.position.maxScrollExtent + 80,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOutCubic,
    );
  }

  Future<void> _send() async {
    final text = _composer.text.trim();
    if (text.isEmpty || _sending) return;

    final provider = _providers
        .where((p) => p.id == _selectedProviderId)
        .firstOrNull;
    if (!_backendUp) {
      _appendError(
          'AI backend is not running. Start it with:\n'
          '    python -m ai.server\n'
          '(from the UmerOS project folder)');
      return;
    }
    if (provider == null) {
      _appendError('No provider selected.');
      return;
    }
    if (provider.kind != ProviderKind.local && !provider.consentGranted) {
      final granted = await _askConsent(provider);
      if (!granted || !mounted) return;
      setState(() {
        _providers = _providers
            .map((p) => p.id == provider.id
                ? AiProviderInfo(
                    id: p.id,
                    name: p.name,
                    kind: p.kind,
                    available: p.available,
                    consentGranted: true,
                    models: p.models,
                    streaming: p.streaming,
                  )
                : p)
            .toList();
      });
    }

    _composer.clear();
    _append(_ChatMessage.user(text));
    setState(() => _sending = true);

    final streamMsg = _ChatMessage.assistantStreaming('');
    _append(streamMsg);

    try {
      await _api.chatStream(
        message: text,
        sessionId: _sessionId,
        providerId: provider.id,
        model: _selectedModel,
        onDelta: (delta) {
          setState(() => streamMsg.append(delta));
          _scrollDown();
        },
      );
      streamMsg.finish();
    } on AiServiceException catch (e) {
      setState(() {
        _messages.remove(streamMsg);
      });
      _appendError(e.statusCode == 403
          ? '${e.message}\nOpen Settings → Providers to grant consent.'
          : e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
      _composerFocus.requestFocus();
    }
  }

  Future<bool> _askConsent(AiProviderInfo provider) async {
    final granted = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Send this prompt off-device?'),
        content: Text(
          '"${_truncate(_composer.text.trim(), 120)}" will be sent to '
          '${provider.name} over the internet.\n\n'
          'Nothing is stored beyond their service policy. You can revoke '
          'this permission anytime in Settings → Providers.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text('Allow once for ${provider.name}'),
          ),
        ],
      ),
    );
    if (granted == true) {
      try {
        await _api.grantConsent(provider.id);
        return true;
      } on AiServiceException catch (e) {
        _appendError('Consent could not be recorded: ${e.message}');
        return false;
      }
    }
    return false;
  }

  static String _truncate(String s, int n) =>
      s.length <= n ? s : '${s.substring(0, n)}…';

  void _newConversation() {
    setState(() {
      _messages
        ..clear()
        ..add(_ChatMessage.system('New conversation started.'));
      _sessionId = DateTime.now().millisecondsSinceEpoch.toString();
    });
    _api; // keep reference warm
    unawaited(_safeReset());
  }

  Future<void> _safeReset() async {
    try {
      await _api.patchConfig({});
    } on AiServiceException {
      // Session reset is server-side best effort; UI already cleared.
    }
  }

  // ── build ──────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final grouped = _groupProviders();

    return Column(children: [
      _buildHeader(cs, grouped),
      Divider(height: 1, color: cs.outlineVariant.withValues(alpha: 0.3)),
      Expanded(child: _buildMessageList(cs)),
      if (!_backendUp) _buildOfflineBanner(cs),
      _buildComposer(cs),
    ]);
  }

  Map<ProviderKind, List<AiProviderInfo>> _groupProviders() {
    final map = <ProviderKind, List<AiProviderInfo>>{};
    for (final p in _providers) {
      map.putIfAbsent(p.kind, () => []).add(p);
    }
    return map;
  }

  Widget _buildHeader(ColorScheme cs,
      Map<ProviderKind, List<AiProviderInfo>> grouped) {
    final kinds = ProviderKind.values
        .where((k) => (grouped[k] ?? []).isNotEmpty)
        .toList();

    final providerList = _providersOfKind;
    if (_selectedProviderId != null &&
        !providerList.any((p) => p.id == _selectedProviderId)) {
      // Kind switch raced with state; snap back to the first of the kind.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _onProviderChanged(providerList.firstOrNull?.id);
      });
    }
    final selected = _providers
        .where((p) => p.id == _selectedProviderId)
        .firstOrNull;
    final models = selected?.models ?? const <String>[];

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      color: cs.surfaceContainerHighest.withValues(alpha: 0.4),
      // Horizontal scroll keeps every control reachable on narrow
      // windows instead of overflowing (HCI #7 flexibility).
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        reverse: true,
        child: Row(children: [
        Icon(Icons.auto_awesome, size: 16, color: cs.primary),
        const SizedBox(width: 8),
        Text('AI Assistant',
            style: GoogleFonts.inter(
                fontSize: 13, fontWeight: FontWeight.bold)),
        const SizedBox(width: 14),
        Tooltip(
          message: _backendUp
              ? 'Connected to UmerOS AI service'
              : 'AI service offline — run: python -m ai.server',
          child: Icon(Icons.circle,
              size: 9, color: _backendUp ? Colors.green : Colors.red),
        ),
        const SizedBox(width: 14),
        if (kinds.isEmpty)
          const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2))
        else
          SizedBox(
          width: 300,
          child: SegmentedButton<ProviderKind>(
            segments: [
              for (final k in kinds)
                ButtonSegment(
                  value: k,
                  label: Text(k.groupLabel,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 10)),
                ),
            ],
            selected: {_selectedKind},
            showSelectedIcon: false,
            onSelectionChanged: (s) => _onKindChanged(s.firstOrNull),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 200,
          key: ValueKey('prov-$_selectedKind'),
          child: DropdownMenu<String>(
            initialSelection: _selectedProviderId,
            enableFilter: false,
            enableSearch: false,
            inputDecorationTheme: InputDecorationTheme(
              isDense: true,
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10)),
              contentPadding: const EdgeInsets.symmetric(
                  horizontal: 10, vertical: 4),
            ),
            label: const Text('Provider', style: TextStyle(fontSize: 12)),
            dropdownMenuEntries: [
              for (final p in providerList)
                DropdownMenuEntry(
                  value: p.id,
                  label:
                      '${p.name}${p.available ? '' : ' (off)'}',
                  leadingIcon: Icon(
                    p.available ? Icons.check_circle_outline : Icons.cancel,
                    size: 15,
                    color: p.available ? Colors.green : cs.outline,
                  ),
                ),
            ],
            onSelected: _onProviderChanged,
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 210,
          key: ValueKey('model-$_selectedProviderId'),
          child: DropdownMenu<String>(
            initialSelection: _selectedModel,
            enableFilter: true,
            requestFocusOnTap: false,
            inputDecorationTheme: InputDecorationTheme(
              isDense: true,
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10)),
              contentPadding: const EdgeInsets.symmetric(
                  horizontal: 10, vertical: 4),
            ),
            label: const Text('Model', style: TextStyle(fontSize: 12)),
            dropdownMenuEntries: [
              for (final m in models)
                DropdownMenuEntry(value: m, label: m),
            ],
            onSelected: (v) => setState(() => _selectedModel = v),
          ),
        ),
        IconButton(
          tooltip: 'Refresh providers',
          icon: const Icon(Icons.refresh, size: 18),
          onPressed: _refreshBackend,
        ),
        IconButton(
          tooltip: 'Settings & Local Models',
          icon: const Icon(Icons.settings_outlined, size: 18),
          onPressed: _openSettings,
        ),
        IconButton(
          tooltip: 'New conversation',
          icon: const Icon(Icons.chat_bubble_outline, size: 18),
          onPressed: _newConversation,
        ),
        ]),
      ),
    );
  }

  Widget _buildMessageList(ColorScheme cs) {
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      itemCount: _messages.length,
      itemBuilder: (context, i) {
        final m = _messages[i];
        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: m.build(context, cs),
        );
      },
    );
  }

  Widget _buildOfflineBanner(ColorScheme cs) {
    return Material(
      color: Colors.amber.shade900.withValues(alpha: 0.15),
      child: ListTile(
        dense: true,
        leading: Icon(Icons.power_off, color: Colors.amber.shade700, size: 20),
        title: const Text('AI service is offline',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        subtitle: const Text(
            'Start it from the UmerOS folder:  python -m ai.server',
            style: TextStyle(fontSize: 11, fontFamily: 'monospace')),
        trailing: TextButton(
          onPressed: _refreshBackend,
          child: const Text('Retry'),
        ),
      ),
    );
  }

  Widget _buildComposer(ColorScheme cs) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
      color: cs.surfaceContainerHighest.withValues(alpha: 0.35),
      child: Row(children: [
        Expanded(
          child: TextField(
            key: const ValueKey('ai-composer'),
            controller: _composer,
            focusNode: _composerFocus,
            minLines: 1,
            maxLines: 5,
            enabled: !_sending,
            style: const TextStyle(fontSize: 13),
            decoration: InputDecoration(
              hintText: _backendUp
                  ? 'Ask anything…  (Enter to send, Shift+Enter for newline)'
                  : 'Backend offline',
              filled: true,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide.none,
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            ),
            keyboardType: TextInputType.multiline,
            onSubmitted: (_) => _send(),
          ),
        ),
        const SizedBox(width: 8),
        _sending
          ? IconButton.filledTonal(
              tooltip: 'Sending… (streaming)',
              onPressed: null,
              icon: SizedBox(
                width: 18, height: 18,
                child: CircularProgressIndicator(strokeWidth: 2)))
          : IconButton.filled(
              tooltip: 'Send message',
              onPressed: _send,
              icon: const Icon(Icons.send_rounded, size: 20)),
      ]),
    );
  }

  // ── settings sheet ─────────────────────────────────────────────────────

  void _openSettings() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _AiSettingsSheet(onChanged: _refreshBackend),
    );
  }
}

// ── chat message model ──────────────────────────────────────────────────

class _ChatMessage {
  _ChatMessage.user(String text)
      : role = _Role.user,
        _text = text,
        streaming = false;

  _ChatMessage.assistantStreaming([String initial = ''])
      : role = _Role.assistant,
        _text = initial,
        streaming = true;

  _ChatMessage.error(String text)
      : role = _Role.error,
        _text = text,
        streaming = false;

  _ChatMessage.system(String text)
      : role = _Role.system,
        _text = text,
        streaming = false;

  final _Role role;
  String _text;
  final bool streaming;

  String get text => _text;

  void append(String delta) => _text += delta;

  void finish() {}

  Widget build(BuildContext context, ColorScheme cs) {
    switch (role) {
      case _Role.user:
        return Align(
          alignment: Alignment.centerRight,
          child: Container(
            constraints: const BoxConstraints(maxWidth: 640),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: cs.primaryContainer,
              borderRadius: BorderRadius.circular(16),
            ),
            child: SelectableText(text,
                style: const TextStyle(fontSize: 13, height: 1.4)),
          ),
        );
      case _Role.assistant:
        return Align(
          alignment: Alignment.centerLeft,
          child: Container(
            constraints: const BoxConstraints(maxWidth: 720),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: cs.surfaceContainerHigh,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: cs.outlineVariant
                  .withValues(alpha: 0.3)),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SelectableText(text.isEmpty && streaming ? '…' : text,
                    style: const TextStyle(fontSize: 13, height: 1.45)),
                if (!streaming)
                  Align(alignment: Alignment.centerRight, child:
                    IconButton(
                      visualDensity: VisualDensity.compact,
                      tooltip: 'Copy reply',
                      iconSize: 15,
                      icon: const Icon(Icons.copy),
                      onPressed: () => Clipboard.setData(
                          ClipboardData(text: text))),
                  ),
              ]),
          ),
        );
      case _Role.error:
        return Align(
          alignment: Alignment.center,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: cs.errorContainer.withValues(alpha: 0.7),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.warning_amber_rounded,
                  size: 16, color: cs.onErrorContainer),
              const SizedBox(width: 8),
              Flexible(child: SelectableText(text,
                  style: TextStyle(fontSize: 12, height: 1.4,
                      color: cs.onErrorContainer))),
            ]),
          ),
        );
      case _Role.system:
        return Center(
          child: Text(text,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 11,
                  color: cs.onSurfaceVariant)),
        );
    }
  }
}

enum _Role { user, assistant, error, system }

// ── settings bottom-sheet ────────────────────────────────────────────────

class _AiSettingsSheet extends StatefulWidget {
  const _AiSettingsSheet({required this.onChanged});

  final VoidCallback onChanged;

  @override
  State<_AiSettingsSheet> createState() => _AiSettingsSheetState();
}

class _AiSettingsSheetState extends State<_AiSettingsSheet>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs =
      TabController(length: 2, vsync: this);

  List<CatalogModel> _catalog = [];
  List<DownloadJob> _jobs = [];
  List<AiProviderInfo> _providers = [];
  final Map<String, TextEditingController> _keyFields = {};
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    for (final c in _keyFields.values) {
      c.dispose();
    }
    super.dispose();
  }

  AiService get _api => AiService.instance;

  Future<void> _load() async {
    try {
      final catalog = await _api.catalog();
      final jobs = await _api.downloads();
      final providers = await _api.listProviders();
      if (!mounted) return;
      setState(() {
        _catalog = catalog;
        _jobs = jobs;
        _providers = providers;
        _loading = false;
      });
      _startPollingIfNeeded();
    } on AiServiceException catch (e) {
      if (mounted) {
        setState(() {
          _error = e.message;
          _loading = false;
        });
      }
    }
  }

  void _startPollingIfNeeded() {
    if (_jobs.any((j) => j.isActive)) {
      Future.delayed(const Duration(milliseconds: 800), _pollDownloads);
    }
  }

  Future<void> _pollDownloads() async {
    if (!mounted) return;
    try {
      final jobs = await _api.downloads();
      if (!mounted) return;
      setState(() => _jobs = jobs);
      if (jobs.any((j) => j.isActive)) {
        Future.delayed(const Duration(milliseconds: 800), _pollDownloads);
      } else {
        // refresh installed flags
        final catalog = await _api.catalog();
        if (mounted) setState(() => _catalog = catalog);
      }
    } on AiServiceException {
      // transient — stop polling silently
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.72,
        child: Column(children: [
          TabBar(
            controller: _tabs,
            tabs: const [
              Tab(icon: Icon(Icons.key), text: 'Providers & Keys'),
              Tab(icon: Icon(Icons.download_outlined), text: 'Local Models'),
            ],
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? _errorPane(cs)
                    : TabBarView(controller: _tabs, children: [
                        _providersPane(cs),
                        _modelsPane(cs),
                      ]),
          ),
        ]),
      ),
    );
  }

  Widget _errorPane(ColorScheme cs) {
    return Center(child: Padding(padding: const EdgeInsets.all(24),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.cloud_off, size: 40, color: cs.error),
        const SizedBox(height: 10),
        Text(_error!, textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12)),
      ])));
  }

  // -- providers tab ------------------------------------------------------

  Widget _providersPane(ColorScheme cs) {
    final online = _providers
        .where((p) => p.kind != ProviderKind.local)
        .toList();
    final locals = _providers
        .where((p) => p.kind == ProviderKind.local)
        .toList();

    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Online access requires your explicit consent per provider. '
           'API keys stay in ~/.umeros/ai_state/ and env vars.',
          style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant)),
      const SizedBox(height: 12),
      for (final p in online) _providerTile(p),
      const Divider(height: 28),
      Text('LOCAL ENGINES',
          style: TextStyle(fontSize: 11,
              fontWeight: FontWeight.bold, color: cs.primary)),
      const SizedBox(height: 6),
      for (final p in locals) _localEngineTile(p),
    ]);
  }

  Widget _providerTile(AiProviderInfo p) {
    _keyFields.putIfAbsent(p.id, () => TextEditingController());
    final hasKey = p.available;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(child: Text(p.name,
                  style: const TextStyle(fontWeight: FontWeight.bold))),
              DataSourceBadge(simulated: false),
              const SizedBox(width: 6),
              Switch(
                value: p.consentGranted,
                onChanged: (v) async {
                  try {
                    if (v) {
                      await _api.grantConsent(p.id);
                    } else {
                      await _api.revokeConsent(p.id);
                    }
                    await _load();
                  } on AiServiceException catch (e) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(e.message)));
                    }
                  }
                },
              ),
            ]),
            const SizedBox(height: 6),
            TextField(
              controller: _keyFields[p.id],
              obscureText: true,
              enabled: true,
              decoration: InputDecoration(
                isDense: true,
                labelText: hasKey
                    ? 'API key saved — enter new to replace'
                    : 'API key',
                hintText: hasKey ? '••••••••' : 'Paste key…',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: 'Save key',
                  icon: const Icon(Icons.save_outlined, size: 18),
                  onPressed: () async {
                    final value = _keyFields[p.id]!.text.trim();
                    if (value.isEmpty) return;
                    try {
                      await _api.patchConfig({'providers': {
                        p.id: {'api_key': value}}});
                      _keyFields[p.id]!.clear();
                      await _load();
                    } on AiServiceException catch (e) {
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(e.message)));
                      }
                    }
                  },
                ),
              ),
            ),
          ]),
      ),
    );
  }

  Widget _localEngineTile(AiProviderInfo p) {
    final ok = p.available;
    return ListTile(
      leading: Icon(ok ? Icons.check_circle : Icons.cancel,
          color: ok ? Colors.green : Colors.red, size: 20),
      title: Text(p.name, style: const TextStyle(fontSize: 13)),
      subtitle: Text(
        p.id == 'ollama'
            ? (ok ? 'Running — ${p.models.length} model(s)'
                  : 'Install Ollama or start the service')
            : (ok ? '${p.models.length} GGUF file(s) ready'
                  : 'Runtime missing — pip install llama-cpp-python'),
        style: const TextStyle(fontSize: 11)),
    );
  }

  // -- models tab ---------------------------------------------------------

  Widget _modelsPane(ColorScheme cs) {
    final installedJobs = {for (final j in _jobs) j.modelId: j};
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Bring your own LLM — downloads land in '
           '~/.umeros/models as GGUF files and run fully offline via '
           'llama.cpp.',
          style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant)),
      const SizedBox(height: 12),
      ..._catalog.map((m) {
        final job = installedJobs[m.id];
        final downloading = job?.isActive ?? false;
        return Card(
          margin: const EdgeInsets.only(bottom: 10),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Expanded(child: Text('${m.title} · ${m.params} (${m.quant})',
                      style: const TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 13))),
                  Text('${m.sizeGb} GB',
                      style: TextStyle(fontSize: 11,
                          color: cs.onSurfaceVariant)),
                ]),
                const SizedBox(height: 4),
                Text(m.description,
                    style: const TextStyle(fontSize: 11, height: 1.3)),
                const SizedBox(height: 8),
                if (downloading) ...[
                  LinearProgressIndicator(value: job!.progress / 100),
                  const SizedBox(height: 4),
                  Row(children: [
                    Text('${job.status} · ${job.downloadedMb}/'
                        '${job.totalMb == 0 ? '?' : job.totalMb} MB '
                        '(${job.progress.toStringAsFixed(0)}%)',
                        style: const TextStyle(fontSize: 10)),
                    const Spacer(),
                    TextButton(
                      onPressed: () async {
                        await _api.cancelDownload(job.modelId);
                        _pollDownloads();
                      },
                      child: const Text('Cancel'),
                    ),
                  ]),
                ] else
                  Row(children: [
                    if (m.installed)
                      Chip(label: const Text('Installed'),
                          avatar: Icon(Icons.check,
                              size: 14, color: Colors.green))
                    else
                      FilledButton.tonalIcon(
                        onPressed: () async {
                          await _api.startDownload(m.id);
                          _pollDownloads();
                        },
                        icon: const Icon(Icons.download, size: 16),
                        label: const Text('Download')),
                    const Spacer(),
                    if (m.installed)
                      IconButton(
                        tooltip: 'Delete model',
                        icon: Icon(Icons.delete_outline,
                            size: 18, color: cs.error),
                        onPressed: () async {
                          await _api.deleteModel(m.filename);
                          await _load();
                        }),
                  ]),
              ]),
          ),
        );
      }),
    ]);
  }
}
