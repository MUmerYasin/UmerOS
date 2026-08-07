import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

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
    final tab = BrowserTab(
      url: url ?? 'about:blank',
      title: 'New Tab',
    );
    setState(() {
      _tabs.add(tab);
      _activeTabIndex = _tabs.length - 1;
    });
  }

  void _closeTab(int index) {
    if (_tabs.length <= 1) return;
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
    _active.urlController.text = url;
    setState(() {
      _active.url = url;
      _active.title = _extractDomain(url);
    });
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
    }
  }

  String _extractDomain(String url) {
    try {
      final uri = Uri.parse(url);
      return uri.host;
    } catch (_) {
      return url;
    }
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
            isLoading: false,
            onBack: () {},
            onForward: () {},
            onRefresh: () => _navigate(_active.url),
            onHome: () => _navigate('https://www.google.com'),
          ),
          Expanded(
            child: Row(
              children: [
                if (_showSidebar) _SpeedDialSidebar(onNavigate: _navigate),
                Expanded(
                  child: Stack(
                    children: [
                      // New tab page or visited page display
                      if (_active.url == 'about:blank')
                        _NewTabPage(onNavigate: _navigate)
                      else
                        _VisitedPageView(
                          url: _active.url,
                          title: _active.title,
                        ),
                    ],
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
          // Sidebar toggle
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

          // Tabs
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

          // New tab button
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
  final VoidCallback onBack;
  final VoidCallback onForward;
  final VoidCallback onRefresh;
  final VoidCallback onHome;

  const _NavigationBar({
    required this.controller,
    required this.onNavigate,
    required this.isLoading,
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
          // Back
          _NavButton(
            icon: Icons.arrow_back,
            enabled: false,
            onTap: onBack,
          ),
          const SizedBox(width: 2),

          // Forward
          _NavButton(
            icon: Icons.arrow_forward,
            enabled: false,
            onTap: onForward,
          ),
          const SizedBox(width: 2),

          // Refresh
          _NavButton(
            icon: isLoading ? Icons.close : Icons.refresh,
            enabled: true,
            onTap: isLoading ? () {} : onRefresh,
          ),
          const SizedBox(width: 2),

          // Home
          _NavButton(
            icon: Icons.home,
            enabled: true,
            onTap: onHome,
          ),
          const SizedBox(width: 8),

          // URL bar
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
                  // Bookmark button
                  GestureDetector(
                    onTap: () {},
                    child: Icon(
                      Icons.bookmark_border,
                      size: 16,
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                    ),
                  ),
                  const SizedBox(width: 8),

                  // Menu
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
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
        ),
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
          // Header
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Icon(
                  Icons.bookmark,
                  size: 16,
                  color: Theme.of(context).colorScheme.primary,
                ),
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

          // Bookmarks list
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

          // Add bookmark button
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

// ─── Visited Page View ───────────────────────────────────────────────────────

class _VisitedPageView extends StatelessWidget {
  final String url;
  final String title;

  const _VisitedPageView({required this.url, required this.title});

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
              title,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w500,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              url,
              style: TextStyle(
                fontSize: 14,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Page opened in system browser',
              style: TextStyle(
                fontSize: 13,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.3),
              ),
            ),
          ],
        ),
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
            // Logo
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

            // Search bar
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

            // Quick links grid
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
  final TextEditingController urlController;

  BrowserTab({
    required this.url,
    this.title = 'New Tab',
  }) : urlController = TextEditingController(text: url);
}

class _Bookmark {
  final String name;
  final String url;
  final IconData icon;
  final Color color;

  const _Bookmark(this.name, this.url, this.icon, this.color);
}
