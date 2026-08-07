import 'package:flutter/material.dart';
import 'package:webview_flutter_windows/webview_flutter_windows.dart';

class BrowserApp extends StatefulWidget {
  const BrowserApp({super.key});

  @override
  State<BrowserApp> createState() => _BrowserAppState();
}

class _BrowserAppState extends State<BrowserApp> {
  final List<BrowserTab> _tabs = [];
  int _activeTabIndex = 0;
  bool _showSidebar = false;

  @override
  void initState() {
    super.initState();
    _addTab('https://www.google.com');
  }

  BrowserTab get _active => _tabs[_activeTabIndex];

  void _addTab([String? url]) {
    final controller = WebviewController();
    final tab = BrowserTab(
      url: url ?? 'about:blank',
      title: 'New Tab',
      controller: controller,
    );
    _initTabController(tab);
    setState(() {
      _tabs.add(tab);
      _activeTabIndex = _tabs.length - 1;
    });
  }

  Future<void> _initTabController(BrowserTab tab) async {
    try {
      await tab.controller.initialize();
      await tab.controller.setPopupWindowPolicy(WebviewPopupWindowPolicy.deny);
      await tab.controller.setDefaultContextMenusEnabled(true);

      if (tab.url != 'about:blank') {
        await tab.controller.loadUrl(tab.url);
      }

      // Listen for URL changes
      tab.controller.url.listen((url) {
        if (mounted) {
          setState(() {
            tab.url = url;
            tab.urlController.text = url;
          });
        }
      });

      // Listen for title changes
      tab.controller.title.listen((title) {
        if (mounted) {
          setState(() {
            tab.title = title;
          });
        }
      });

      // Listen for loading state
      tab.controller.loadingState.listen((state) {
        if (mounted) {
          setState(() {
            tab.isLoading = state == LoadingState.loading;
          });
        }
      });

      if (mounted) setState(() {});
    } catch (e) {
      debugPrint('WebView init error: $e');
    }
  }

  void _closeTab(int index) {
    if (_tabs.length <= 1) return;
    final tab = _tabs[index];
    tab.controller.dispose();
    setState(() {
      _tabs.removeAt(index);
      if (_activeTabIndex >= _tabs.length) {
        _activeTabIndex = _tabs.length - 1;
      }
    });
  }

  void _navigate(String input) async {
    String url = input.trim();
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      if (url.contains('.') && !url.contains(' ')) {
        url = 'https://$url';
      } else {
        url = 'https://www.google.com/search?q=${Uri.encodeComponent(url)}';
      }
    }

    setState(() {
      _active.url = url;
      _active.urlController.text = url;
    });

    if (_active.controller.value.isInitialized) {
      await _active.controller.loadUrl(url);
    }
  }

  @override
  void dispose() {
    for (final tab in _tabs) {
      tab.controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: Column(
        children: [
          _TabBar(
            tabs: _tabs,
            activeIndex: _activeTabIndex,
            onTabTap: (i) => setState(() => _activeTabIndex = i),
            onTabClose: _closeTab,
            onNewTab: () => _addTab(),
            onToggleSidebar: () => setState(() => _showSidebar = !_showSidebar),
          ),
          _NavigationBar(
            controller: _active.urlController,
            onNavigate: _navigate,
            isLoading: _active.isLoading,
            canGoBack: _active.canGoBack,
            canGoForward: _active.canGoForward,
            onBack: () => _active.controller.goBack(),
            onForward: () => _active.controller.goForward(),
            onRefresh: () => _active.controller.reload(),
            onHome: () => _navigate('https://www.google.com'),
          ),
          Expanded(
            child: Row(
              children: [
                if (_showSidebar) _SpeedDialSidebar(onNavigate: _navigate),
                Expanded(
                  child: _active.controller.value.isInitialized
                      ? Webview(_active.controller)
                      : _NewTabPage(onNavigate: _navigate),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Tab Bar ─────────────────────────────────────────────────────────────────

class _TabBar extends StatelessWidget {
  final List<BrowserTab> tabs;
  final int activeIndex;
  final ValueChanged<int> onTabTap;
  final ValueChanged<int> onTabClose;
  final VoidCallback onNewTab;
  final VoidCallback onToggleSidebar;

  const _TabBar({
    required this.tabs,
    required this.activeIndex,
    required this.onTabTap,
    required this.onTabClose,
    required this.onNewTab,
    required this.onToggleSidebar,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40,
      color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      child: Row(
        children: [
          GestureDetector(
            onTap: onToggleSidebar,
            child: Container(
              width: 36,
              height: 40,
              alignment: Alignment.center,
              child: Icon(
                Icons.menu,
                size: 18,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: tabs.length,
              itemBuilder: (context, index) {
                final tab = tabs[index];
                final isActive = index == activeIndex;
                return GestureDetector(
                  onTap: () => onTabTap(index),
                  child: Container(
                    width: 180,
                    margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 2),
                    decoration: BoxDecoration(
                      color: isActive
                          ? Theme.of(context).colorScheme.surface
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(8),
                      border: isActive
                          ? Border.all(
                              color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
                            )
                          : null,
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Row(
                      children: [
                        if (tab.isLoading)
                          SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 1.5,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                          )
                        else
                          Icon(
                            _getTabIcon(tab.url),
                            size: 14,
                            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                          ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            tab.title,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                              color: Theme.of(context).colorScheme.onSurface,
                            ),
                          ),
                        ),
                        GestureDetector(
                          onTap: () => onTabClose(index),
                          child: Icon(
                            Icons.close,
                            size: 14,
                            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          GestureDetector(
            onTap: onNewTab,
            child: Container(
              width: 36,
              height: 40,
              alignment: Alignment.center,
              child: Icon(
                Icons.add,
                size: 18,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ),
        ],
      ),
    );
  }

  IconData _getTabIcon(String url) {
    if (url.contains('google')) return Icons.search;
    if (url.contains('youtube')) return Icons.play_circle;
    if (url.contains('github')) return Icons.code;
    if (url.contains('twitter') || url.contains('x.com')) return Icons.flutter_dash;
    if (url.contains('reddit')) return Icons.forum;
    return Icons.language;
  }
}

// ─── Navigation Bar ──────────────────────────────────────────────────────────

class _NavigationBar extends StatelessWidget {
  final TextEditingController controller;
  final ValueChanged<String> onNavigate;
  final bool isLoading;
  final bool canGoBack;
  final bool canGoForward;
  final VoidCallback onBack;
  final VoidCallback onForward;
  final VoidCallback onRefresh;
  final VoidCallback onHome;

  const _NavigationBar({
    required this.controller,
    required this.onNavigate,
    required this.isLoading,
    required this.canGoBack,
    required this.canGoForward,
    required this.onBack,
    required this.onForward,
    required this.onRefresh,
    required this.onHome,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.15),
          ),
        ),
      ),
      child: Row(
        children: [
          _NavButton(
            icon: Icons.arrow_back,
            enabled: canGoBack,
            onTap: onBack,
          ),
          const SizedBox(width: 2),
          _NavButton(
            icon: Icons.arrow_forward,
            enabled: canGoForward,
            onTap: onForward,
          ),
          const SizedBox(width: 2),
          _NavButton(
            icon: isLoading ? Icons.close : Icons.refresh,
            enabled: true,
            onTap: isLoading ? () {} : onRefresh,
          ),
          const SizedBox(width: 2),
          _NavButton(
            icon: Icons.home,
            enabled: true,
            onTap: onHome,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Container(
              height: 36,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  const SizedBox(width: 12),
                  Icon(
                    _getSecureIcon(controller.text),
                    size: 14,
                    color: controller.text.startsWith('https')
                        ? Colors.green
                        : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: controller,
                      onSubmitted: onNavigate,
                      style: TextStyle(
                        fontSize: 13,
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                      decoration: InputDecoration(
                        hintText: 'Search or enter URL',
                        hintStyle: TextStyle(
                          fontSize: 13,
                          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4),
                        ),
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.symmetric(vertical: 8),
                      ),
                    ),
                  ),
                  GestureDetector(
                    onTap: () {},
                    child: Icon(
                      Icons.bookmark_border,
                      size: 16,
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                    ),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: () => _showBrowserMenu(context),
                    child: Icon(
                      Icons.more_vert,
                      size: 16,
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                    ),
                  ),
                  const SizedBox(width: 4),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  IconData _getSecureIcon(String url) {
    if (url.startsWith('https')) return Icons.lock;
    return Icons.lock_open;
  }

  void _showBrowserMenu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      builder: (context) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.history),
              title: const Text('History'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.download),
              title: const Text('Downloads'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.bookmark),
              title: const Text('Bookmarks'),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.settings),
              title: const Text('Settings'),
              onTap: () => Navigator.pop(context),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Nav Button ──────────────────────────────────────────────────────────────

class _NavButton extends StatelessWidget {
  final IconData icon;
  final bool enabled;
  final VoidCallback onTap;

  const _NavButton({
    required this.icon,
    required this.enabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: enabled ? onTap : null,
      child: Container(
        width: 32,
        height: 32,
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(8)),
        alignment: Alignment.center,
        child: Icon(
          icon,
          size: 18,
          color: enabled
              ? Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.8)
              : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.3),
        ),
      ),
    );
  }
}

// ─── Speed Dial Sidebar ──────────────────────────────────────────────────────

class _SpeedDialSidebar extends StatelessWidget {
  final ValueChanged<String> onNavigate;

  const _SpeedDialSidebar({required this.onNavigate});

  static const _bookmarks = [
    _Bookmark('Google', 'https://www.google.com', Icons.search, Colors.blue),
    _Bookmark('YouTube', 'https://www.youtube.com', Icons.play_circle, Colors.red),
    _Bookmark('GitHub', 'https://www.github.com', Icons.code, Colors.black87),
    _Bookmark('Reddit', 'https://www.reddit.com', Icons.forum, Colors.orange),
    _Bookmark('Twitter / X', 'https://x.com', Icons.flutter_dash, Colors.blue),
    _Bookmark('Wikipedia', 'https://www.wikipedia.com', Icons.menu_book, Colors.grey),
    _Bookmark('Stack Overflow', 'https://stackoverflow.com', Icons.question_answer, Colors.orange),
    _Bookmark('MDN', 'https://developer.mozilla.org', Icons.code, Colors.blue),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 200,
      color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Icon(Icons.bookmark, size: 16, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Speed Dial',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              itemCount: _bookmarks.length,
              itemBuilder: (context, index) {
                final bm = _bookmarks[index];
                return ListTile(
                  dense: true,
                  leading: Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: bm.color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(bm.icon, size: 16, color: bm.color),
                  ),
                  title: Text(
                    bm.name,
                    style: TextStyle(
                      fontSize: 13,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  onTap: () => onNavigate(bm.url),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: OutlinedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.add, size: 14),
              label: const Text('Add Bookmark', style: TextStyle(fontSize: 12)),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(double.infinity, 32),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── New Tab Page ────────────────────────────────────────────────────────────

class _NewTabPage extends StatelessWidget {
  final ValueChanged<String> onNavigate;

  const _NewTabPage({required this.onNavigate});

  static const _quickLinks = [
    _Bookmark('Google', 'https://www.google.com', Icons.search, Colors.blue),
    _Bookmark('YouTube', 'https://www.youtube.com', Icons.play_circle, Colors.red),
    _Bookmark('GitHub', 'https://www.github.com', Icons.code, Colors.black87),
    _Bookmark('Reddit', 'https://www.reddit.com', Icons.forum, Colors.orange),
    _Bookmark('Twitter / X', 'https://x.com', Icons.flutter_dash, Colors.blue),
    _Bookmark('Wikipedia', 'https://www.wikipedia.com', Icons.menu_book, Colors.grey),
    _Bookmark('MDN', 'https://developer.mozilla.org', Icons.code, Colors.blue),
    _Bookmark('Stack Overflow', 'https://stackoverflow.com', Icons.question_answer, Colors.orange),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Theme.of(context).colorScheme.surface,
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.language,
              size: 72,
              color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.3),
            ),
            const SizedBox(height: 16),
            Text(
              'UmerOS Browser',
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w300,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Open source • Fast • Private',
              style: TextStyle(
                fontSize: 14,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4),
              ),
            ),
            const SizedBox(height: 40),
            Container(
              width: 500,
              height: 48,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  const SizedBox(width: 16),
                  Icon(
                    Icons.search,
                    size: 20,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      onSubmitted: onNavigate,
                      style: TextStyle(
                        fontSize: 14,
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                      decoration: InputDecoration(
                        hintText: 'Search the web or enter URL',
                        hintStyle: TextStyle(
                          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4),
                        ),
                        border: InputBorder.none,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 40),
            Wrap(
              spacing: 16,
              runSpacing: 16,
              children: _quickLinks.map((bm) {
                return GestureDetector(
                  onTap: () => onNavigate(bm.url),
                  child: Column(
                    children: [
                      Container(
                        width: 64,
                        height: 64,
                        decoration: BoxDecoration(
                          color: bm.color.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1),
                          ),
                        ),
                        child: Icon(bm.icon, size: 28, color: bm.color),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        bm.name,
                        style: TextStyle(
                          fontSize: 11,
                          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Models ──────────────────────────────────────────────────────────────────

class BrowserTab {
  String url;
  String title;
  bool isLoading;
  bool canGoBack;
  bool canGoForward;
  final TextEditingController urlController;
  final WebviewController controller;

  BrowserTab({
    required this.url,
    this.title = 'New Tab',
    this.isLoading = false,
    this.canGoBack = false,
    this.canGoForward = false,
    required this.controller,
  }) : urlController = TextEditingController(text: url);
}

class _Bookmark {
  final String name;
  final String url;
  final IconData icon;
  final Color color;

  const _Bookmark(this.name, this.url, this.icon, this.color);
}
