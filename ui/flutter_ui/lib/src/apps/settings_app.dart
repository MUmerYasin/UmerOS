import 'package:flutter/material.dart';
import '../widgets/auto_adjust_box.dart';

class SettingsApp extends StatefulWidget {
  const SettingsApp({super.key});

  @override
  State<SettingsApp> createState() => _SettingsAppState();
}

class _SettingsAppState extends State<SettingsApp> {
  bool _darkMode = true;
  int _selectedAccentIndex = 0;
  double _fontSize = 14;
  String _dockPosition = 'bottom';
  String _hostname = 'UmerOS';
  bool _autoStartApps = false;
  String _sleepTimer = 'Never';
  String _resolution = '1920x1080';
  String _refreshRate = '60Hz';
  bool _nightShift = false;
  double _colorTemperature = 0.5;
  double _volume = 0.7;
  bool _notificationSounds = true;
  bool _systemSounds = true;
  bool _wifiEnabled = true;
  String _proxyMode = 'None';
  String _dnsServer = '8.8.8.8';

  int _selectedSidebarIndex = 0;
  final ScrollController _scrollController = ScrollController();
  final List<GlobalKey> _sectionKeys = List.generate(6, (_) => GlobalKey());

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    for (int i = 0; i < _sectionKeys.length; i++) {
      final key = _sectionKeys[i];
      final ctx = key.currentContext;
      if (ctx != null) {
        final box = ctx.findRenderObject() as RenderBox?;
        if (box != null) {
          final offset = box.localToGlobal(Offset.zero, ancestor: null).dy;
          if (offset >= 0 && offset < 200) {
            if (_selectedSidebarIndex != i) {
              setState(() => _selectedSidebarIndex = i);
            }
            break;
          }
        }
      }
    }
  }

  void _scrollToSection(int index) {
    setState(() => _selectedSidebarIndex = index);
    final ctx = _sectionKeys[index].currentContext;
    if (ctx != null) {
      Scrollable.ensureVisible(
        ctx,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
        alignment: 0.0,
      );
    }
  }

  final List<Color> _accentColors = [
    Colors.blue,
    Colors.purple,
    Colors.teal,
    Colors.orange,
    Colors.red,
    Colors.green,
    Colors.pink,
    Colors.cyan,
  ];

  final List<String> _dockPositions = ['bottom', 'left', 'right'];
  final List<String> _sleepTimers = ['Never', '5 min', '15 min', '30 min', '1 hour', '2 hours'];
  final List<String> _resolutions = ['1280x720', '1366x768', '1600x900', '1920x1080', '2560x1440', '3840x2160'];
  final List<String> _refreshRates = ['30Hz', '60Hz', '120Hz', '144Hz'];
  final List<String> _proxyModes = ['None', 'Manual', 'Auto', 'System'];
  final List<String> _dnsOptions = ['8.8.8.8', '8.8.4.4', '1.1.1.1', '9.9.9.9', 'Custom'];

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      body: Row(
        children: [
          _buildSidebar(colorScheme, textTheme),
          Expanded(child: _buildContent(colorScheme, textTheme)),
        ],
      ),
    );
  }

  Widget _buildSidebar(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: Border(
          right: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Icon(Icons.settings, size: 20, color: colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Settings',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
                ),
              ],
            ),
          ),
          _sidebarItem(0, Icons.palette, 'Appearance', colorScheme),
          _sidebarItem(1, Icons.computer, 'System', colorScheme),
          _sidebarItem(2, Icons.monitor, 'Display', colorScheme),
          _sidebarItem(3, Icons.volume_up, 'Sound', colorScheme),
          _sidebarItem(4, Icons.wifi, 'Network', colorScheme),
          _sidebarItem(5, Icons.info_outline, 'About', colorScheme),
        ],
      ),
    );
  }

  Widget _sidebarItem(int index, IconData icon, String label, ColorScheme colorScheme) {
    final isSelected = _selectedSidebarIndex == index;
    return ListTile(
      leading: Icon(
        icon,
        size: 20,
        color: isSelected ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.7),
      ),
      title: Text(
        label,
        style: TextStyle(
          color: isSelected ? colorScheme.primary : colorScheme.onSurface,
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
      dense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
      tileColor: isSelected ? colorScheme.primaryContainer.withValues(alpha: 0.3) : null,
      onTap: () => _scrollToSection(index),
    );
  }

  Widget _buildContent(ColorScheme colorScheme, TextTheme textTheme) {
    return SingleChildScrollView(
      controller: _scrollController,
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAppearanceSection(colorScheme, textTheme, _sectionKeys[0]),
          const SizedBox(height: 16),
          _buildSystemSection(colorScheme, textTheme, _sectionKeys[1]),
          const SizedBox(height: 16),
          _buildDisplaySection(colorScheme, textTheme, _sectionKeys[2]),
          const SizedBox(height: 16),
          _buildSoundSection(colorScheme, textTheme, _sectionKeys[3]),
          const SizedBox(height: 16),
          _buildNetworkSection(colorScheme, textTheme, _sectionKeys[4]),
          const SizedBox(height: 16),
          _buildAboutSection(colorScheme, textTheme, _sectionKeys[5]),
        ],
      ),
    );
  }

  Widget _buildAppearanceSection(ColorScheme colorScheme, TextTheme textTheme, GlobalKey key) {
    return Card(
      key: key,
      color: colorScheme.surfaceContainerHigh,
      child: ExpansionTile(
        leading: Icon(Icons.palette, color: colorScheme.primary),
        title: Text('Appearance', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              children: [
                SwitchListTile(
                  title: const Text('Dark Mode'),
                  subtitle: const Text('Toggle between light and dark theme'),
                  value: _darkMode,
                  onChanged: (value) => setState(() => _darkMode = value),
                  contentPadding: EdgeInsets.zero,
                ),
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Accent Color', style: textTheme.titleSmall),
                ),
                const SizedBox(height: 8),
                AutoAdjustRow(
                  spacing: 0,
                  runSpacing: 8,
                  children: List.generate(_accentColors.length, (index) {
                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: GestureDetector(
                        onTap: () => setState(() => _selectedAccentIndex = index),
                        child: Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: _accentColors[index],
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: _selectedAccentIndex == index
                                  ? colorScheme.onSurface
                                  : Colors.transparent,
                              width: 3,
                            ),
                          ),
                          child: _selectedAccentIndex == index
                              ? const Icon(Icons.check, color: Colors.white, size: 16)
                              : null,
                        ),
                      ),
                    );
                  }),
                ),
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Font Size: ${_fontSize.round()}px', style: textTheme.titleSmall),
                ),
                Slider(
                  value: _fontSize,
                  min: 10,
                  max: 24,
                  divisions: 14,
                  label: '${_fontSize.round()}px',
                  onChanged: (value) => setState(() => _fontSize = value),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: _dockPosition,
                  decoration: const InputDecoration(
                    labelText: 'Dock Position',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: _dockPositions.map((pos) {
                    return DropdownMenuItem(value: pos, child: Text(pos[0].toUpperCase() + pos.substring(1)));
                  }).toList(),
                  onChanged: (value) => setState(() => _dockPosition = value!),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSystemSection(ColorScheme colorScheme, TextTheme textTheme, GlobalKey key) {
    return Card(
      key: key,
      color: colorScheme.surfaceContainerHigh,
      child: ExpansionTile(
        leading: Icon(Icons.computer, color: colorScheme.primary),
        title: Text('System', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              children: [
                TextField(
                  decoration: const InputDecoration(
                    labelText: 'Hostname',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  controller: TextEditingController(text: _hostname),
                  onChanged: (value) => _hostname = value,
                ),
                const SizedBox(height: 16),
                SwitchListTile(
                  title: const Text('Auto-start Apps'),
                  subtitle: const Text('Launch apps automatically on boot'),
                  value: _autoStartApps,
                  onChanged: (value) => setState(() => _autoStartApps = value),
                  contentPadding: EdgeInsets.zero,
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _sleepTimer,
                  decoration: const InputDecoration(
                    labelText: 'Sleep Timer',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: _sleepTimers.map((timer) {
                    return DropdownMenuItem(value: timer, child: Text(timer));
                  }).toList(),
                  onChanged: (value) => setState(() => _sleepTimer = value!),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDisplaySection(ColorScheme colorScheme, TextTheme textTheme, GlobalKey key) {
    return Card(
      key: key,
      color: colorScheme.surfaceContainerHigh,
      child: ExpansionTile(
        leading: Icon(Icons.monitor, color: colorScheme.primary),
        title: Text('Display', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              children: [
                DropdownButtonFormField<String>(
                  initialValue: _resolution,
                  decoration: const InputDecoration(
                    labelText: 'Resolution',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: _resolutions.map((res) {
                    return DropdownMenuItem(value: res, child: Text(res));
                  }).toList(),
                  onChanged: (value) => setState(() => _resolution = value!),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _refreshRate,
                  decoration: const InputDecoration(
                    labelText: 'Refresh Rate',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: _refreshRates.map((rate) {
                    return DropdownMenuItem(value: rate, child: Text(rate));
                  }).toList(),
                  onChanged: (value) => setState(() => _refreshRate = value!),
                ),
                const SizedBox(height: 16),
                SwitchListTile(
                  title: const Text('Night Shift'),
                  subtitle: const Text('Reduce blue light for comfortable viewing'),
                  value: _nightShift,
                  onChanged: (value) => setState(() => _nightShift = value),
                  contentPadding: EdgeInsets.zero,
                ),
                if (_nightShift) ...[
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Color Temperature: ${(_colorTemperature * 100).round()}%',
                      style: textTheme.titleSmall,
                    ),
                  ),
                  Slider(
                    value: _colorTemperature,
                    min: 0.0,
                    max: 1.0,
                    divisions: 20,
                    label: '${(_colorTemperature * 100).round()}%',
                    onChanged: (value) => setState(() => _colorTemperature = value),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSoundSection(ColorScheme colorScheme, TextTheme textTheme, GlobalKey key) {
    return Card(
      key: key,
      color: colorScheme.surfaceContainerHigh,
      child: ExpansionTile(
        leading: Icon(Icons.volume_up, color: colorScheme.primary),
        title: Text('Sound', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Volume: ${(_volume * 100).round()}%', style: textTheme.titleSmall),
                ),
                Slider(
                  value: _volume,
                  min: 0.0,
                  max: 1.0,
                  divisions: 20,
                  label: '${(_volume * 100).round()}%',
                  onChanged: (value) => setState(() => _volume = value),
                ),
                const SizedBox(height: 8),
                SwitchListTile(
                  title: const Text('Notification Sounds'),
                  subtitle: const Text('Play sounds for system notifications'),
                  value: _notificationSounds,
                  onChanged: (value) => setState(() => _notificationSounds = value),
                  contentPadding: EdgeInsets.zero,
                ),
                SwitchListTile(
                  title: const Text('System Sounds'),
                  subtitle: const Text('Play sounds for system events'),
                  value: _systemSounds,
                  onChanged: (value) => setState(() => _systemSounds = value),
                  contentPadding: EdgeInsets.zero,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNetworkSection(ColorScheme colorScheme, TextTheme textTheme, GlobalKey key) {
    return Card(
      key: key,
      color: colorScheme.surfaceContainerHigh,
      child: ExpansionTile(
        leading: Icon(Icons.wifi, color: colorScheme.primary),
        title: Text('Network', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              children: [
                SwitchListTile(
                  title: const Text('WiFi'),
                  subtitle: const Text('Enable wireless networking'),
                  value: _wifiEnabled,
                  onChanged: (value) => setState(() => _wifiEnabled = value),
                  contentPadding: EdgeInsets.zero,
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _proxyMode,
                  decoration: const InputDecoration(
                    labelText: 'Proxy Mode',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: _proxyModes.map((mode) {
                    return DropdownMenuItem(value: mode, child: Text(mode));
                  }).toList(),
                  onChanged: (value) => setState(() => _proxyMode = value!),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _dnsServer,
                  decoration: const InputDecoration(
                    labelText: 'DNS Server',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: _dnsOptions.map((dns) {
                    return DropdownMenuItem(value: dns, child: Text(dns));
                  }).toList(),
                  onChanged: (value) => setState(() => _dnsServer = value!),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAboutSection(ColorScheme colorScheme, TextTheme textTheme, GlobalKey key) {
    return Card(
      key: key,
      color: colorScheme.surfaceContainerHigh,
      child: ExpansionTile(
        leading: Icon(Icons.info_outline, color: colorScheme.primary),
        title: Text('About', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    children: [
                      Icon(Icons.computer, size: 48, color: colorScheme.primary),
                      const SizedBox(height: 12),
                      Text(
                        'UmerOS',
                        style: textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Version 1.0.0',
                        style: textTheme.bodyMedium?.copyWith(
                          color: colorScheme.onSurface.withValues(alpha: 0.7),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                _infoRow('Kernel', 'UmerOS Kernel 6.2.0'),
                _infoRow('Architecture', 'x86_64'),
                _infoRow('Desktop', 'UmerOS Desktop 1.0.0'),
                _infoRow('Display Server', 'Wayland 1.21'),
                _infoRow('Window Manager', 'UmerWM 1.0'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(child: Text(label, style: TextStyle(color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6)))),
          Text(value, style: TextStyle(color: Theme.of(context).colorScheme.onSurface)),
        ],
      ),
    );
  }
}
