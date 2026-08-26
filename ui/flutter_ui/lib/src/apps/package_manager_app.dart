import 'package:flutter/material.dart';

import '../widgets/auto_adjust_box.dart';

class PackageManagerApp extends StatefulWidget {
  const PackageManagerApp({super.key});

  @override
  State<PackageManagerApp> createState() => _PackageManagerAppState();
}

class _PackageManagerAppState extends State<PackageManagerApp> {
  String _selectedCategory = 'All';
  String _selectedFilter = 'All';
  String _searchQuery = '';
  bool _isInstalling = false;
  double _installProgress = 0.0;
  String _installingPackage = '';

  final List<String> _categories = [
    'Development',
    'System',
    'Graphics',
    'Multimedia',
    'Internet',
    'Office',
  ];

  final Map<String, IconData> _categoryIcons = {
    'Development': Icons.code,
    'System': Icons.settings,
    'Graphics': Icons.palette,
    'Multimedia': Icons.play_circle,
    'Internet': Icons.language,
    'Office': Icons.work,
  };

  final List<Map<String, dynamic>> _packages = [
    {
      'name': 'python3',
      'version': '3.12.1',
      'size': '28.5 MB',
      'category': 'Development',
      'description': 'Python programming language interpreter',
      'icon': Icons.code,
      'installed': true,
    },
    {
      'name': 'gcc',
      'version': '13.2.0',
      'size': '45.2 MB',
      'category': 'Development',
      'description': 'GNU Compiler Collection for C and C++',
      'icon': Icons.build,
      'installed': false,
    },
    {
      'name': 'vim',
      'version': '9.0.2136',
      'size': '3.8 MB',
      'category': 'Development',
      'description': 'Highly configurable text editor',
      'icon': Icons.edit,
      'installed': true,
    },
    {
      'name': 'git',
      'version': '2.43.0',
      'size': '12.1 MB',
      'category': 'Development',
      'description': 'Distributed version control system',
      'icon': Icons.account_tree,
      'installed': true,
    },
    {
      'name': 'docker',
      'version': '25.0.2',
      'size': '67.3 MB',
      'category': 'System',
      'description': 'Container platform for building and deploying apps',
      'icon': Icons.view_in_ar,
      'installed': false,
    },
    {
      'name': 'nodejs',
      'version': '20.11.0',
      'size': '32.7 MB',
      'category': 'Development',
      'description': 'JavaScript runtime for server-side development',
      'icon': Icons.javascript,
      'installed': true,
    },
    {
      'name': 'rust',
      'version': '1.75.0',
      'size': '58.9 MB',
      'category': 'Development',
      'description': 'Rust programming language toolchain',
      'icon': Icons.memory,
      'installed': false,
    },
    {
      'name': 'cmake',
      'version': '3.28.1',
      'size': '8.4 MB',
      'category': 'Development',
      'description': 'Cross-platform build system generator',
      'icon': Icons.build_circle,
      'installed': false,
    },
    {
      'name': 'ffmpeg',
      'version': '6.1.1',
      'size': '78.2 MB',
      'category': 'Multimedia',
      'description': 'Framework for multimedia processing',
      'icon': Icons.movie,
      'installed': true,
    },
    {
      'name': 'libreoffice',
      'version': '24.2.0',
      'size': '312.5 MB',
      'category': 'Office',
      'description': 'Free office suite compatible with MS Office',
      'icon': Icons.description,
      'installed': false,
    },
    {
      'name': 'gimp',
      'version': '2.10.36',
      'size': '124.8 MB',
      'category': 'Graphics',
      'description': 'GNU Image Manipulation Program',
      'icon': Icons.brush,
      'installed': false,
    },
    {
      'name': 'vlc',
      'version': '3.0.20',
      'size': '45.6 MB',
      'category': 'Multimedia',
      'description': 'Free multimedia player and framework',
      'icon': Icons.play_circle,
      'installed': true,
    },
    {
      'name': 'blender',
      'version': '4.0.2',
      'size': '287.3 MB',
      'category': 'Graphics',
      'description': '3D creation suite for modeling and animation',
      'icon': Icons.view_in_ar,
      'installed': false,
    },
    {
      'name': 'thunderbird',
      'version': '115.6.0',
      'size': '89.4 MB',
      'category': 'Internet',
      'description': 'Free email client and news reader',
      'icon': Icons.mail,
      'installed': false,
    },
  ];

  List<Map<String, dynamic>> get _filteredPackages {
    return _packages.where((pkg) {
      final matchesCategory = _selectedCategory == 'All' || pkg['category'] == _selectedCategory;
      final matchesFilter = _selectedFilter == 'All' ||
          (_selectedFilter == 'Installed' && pkg['installed']) ||
          (_selectedFilter == 'Available' && !pkg['installed']);
      final matchesSearch = _searchQuery.isEmpty ||
          pkg['name'].toLowerCase().contains(_searchQuery.toLowerCase()) ||
          pkg['description'].toLowerCase().contains(_searchQuery.toLowerCase());
      return matchesCategory && matchesFilter && matchesSearch;
    }).toList();
  }

  void _simulateInstall(String packageName) {
    setState(() {
      _isInstalling = true;
      _installProgress = 0.0;
      _installingPackage = packageName;
    });

    Future.doWhile(() async {
      await Future.delayed(const Duration(milliseconds: 50));
      if (!mounted) return false;
      setState(() {
        _installProgress += 0.02;
        if (_installProgress >= 1.0) {
          _installProgress = 1.0;
          _isInstalling = false;
          final index = _packages.indexWhere((p) => p['name'] == packageName);
          if (index != -1) {
            _packages[index]['installed'] = !_packages[index]['installed'];
          }
          _installingPackage = '';
        }
      });
      return _installProgress < 1.0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Column(
      children: [
        _buildHeader(colorScheme, textTheme),
        Expanded(
          child: Row(
            children: [
              _buildSidebar(colorScheme, textTheme),
              Expanded(child: _buildPackageList(colorScheme, textTheme)),
            ],
          ),
        ),
        if (_isInstalling) _buildProgressBar(colorScheme, textTheme),
      ],
    );
  }

  Widget _buildHeader(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: Border(
          bottom: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: Column(
        children: [
          AutoAdjustRow(
            children: [
              Icon(Icons.inventory_2, color: colorScheme.primary, size: 28),
              const SizedBox(width: 12),
              Text(
                'Package Manager',
                style: textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  decoration: InputDecoration(
                    hintText: 'Search packages...',
                    prefixIcon: const Icon(Icons.search, size: 20),
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(color: colorScheme.outline),
                    ),
                    filled: true,
                    fillColor: colorScheme.surface,
                  ),
                  onChanged: (value) => setState(() => _searchQuery = value),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            children: ['All', 'Installed', 'Updates', 'Available'].map((filter) {
              final isSelected = _selectedFilter == filter;
              return FilterChip(
                label: Text(filter),
                selected: isSelected,
                onSelected: (_) => setState(() => _selectedFilter = filter),
                selectedColor: colorScheme.primaryContainer,
                labelStyle: TextStyle(
                  color: isSelected ? colorScheme.onPrimaryContainer : colorScheme.onSurface,
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildSidebar(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      width: 180,
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
            child: Text(
              'Categories',
              style: textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _categoryTile('All', Icons.all_inclusive, colorScheme),
                  ..._categories.map((cat) {
                    return _categoryTile(cat, _categoryIcons[cat] ?? Icons.category, colorScheme);
                  }),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Checking for updates...'),
                      backgroundColor: colorScheme.primaryContainer,
                      behavior: SnackBarBehavior.floating,
                    ),
                  );
                },
                icon: const Icon(Icons.system_update, size: 18),
                label: const Text('Check Updates'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _categoryTile(String category, IconData icon, ColorScheme colorScheme) {
    final isSelected = _selectedCategory == category;
    return ListTile(
      leading: Icon(
        icon,
        size: 20,
        color: isSelected ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.7),
      ),
      title: Text(
        category,
        style: TextStyle(
          fontSize: 13,
          color: isSelected ? colorScheme.primary : colorScheme.onSurface,
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
      dense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
      tileColor: isSelected ? colorScheme.primaryContainer.withValues(alpha: 0.3) : null,
      onTap: () => setState(() => _selectedCategory = category),
    );
  }

  Widget _buildPackageList(ColorScheme colorScheme, TextTheme textTheme) {
    final packages = _filteredPackages;

    if (packages.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.inventory_2_outlined, size: 64, color: colorScheme.onSurface.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(
              'No packages found',
              style: textTheme.titleMedium?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: packages.length,
      itemBuilder: (context, index) {
        final pkg = packages[index];
        return _buildPackageCard(pkg, colorScheme, textTheme);
      },
    );
  }

  Widget _buildPackageCard(Map<String, dynamic> pkg, ColorScheme colorScheme, TextTheme textTheme) {
    final isInstalled = pkg['installed'] as bool;
    final isInstallingThis = _isInstalling && _installingPackage == pkg['name'];

    return Card(
      color: colorScheme.surfaceContainerHigh,
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: colorScheme.primaryContainer.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                pkg['icon'] as IconData,
                color: colorScheme.primary,
                size: 24,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          pkg['name'] as String,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: colorScheme.onSurface,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          pkg['version'] as String,
                          style: TextStyle(
                            fontSize: 11,
                            color: colorScheme.onSurface.withValues(alpha: 0.6),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        pkg['size'] as String,
                        style: TextStyle(
                          fontSize: 11,
                          color: colorScheme.onSurface.withValues(alpha: 0.5),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    pkg['description'] as String,
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 16),
            if (isInstallingThis)
              SizedBox(
                width: 100,
                child: Column(
                  children: [
                    LinearProgressIndicator(
                      value: _installProgress,
                      backgroundColor: colorScheme.surfaceContainerHighest,
                      valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${(_installProgress * 100).round()}%',
                      style: TextStyle(fontSize: 11, color: colorScheme.onSurface.withValues(alpha: 0.6)),
                    ),
                  ],
                ),
              )
            else
              FilledButton.tonal(
                onPressed: _isInstalling ? null : () => _simulateInstall(pkg['name'] as String),
                style: FilledButton.styleFrom(
                  backgroundColor: isInstalled
                      ? colorScheme.errorContainer
                      : colorScheme.primaryContainer,
                  foregroundColor: isInstalled
                      ? colorScheme.onErrorContainer
                      : colorScheme.onPrimaryContainer,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                ),
                child: Text(isInstalled ? 'Remove' : 'Install'),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressBar(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHigh,
        border: Border(
          top: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(Icons.download, size: 16, color: colorScheme.primary),
              const SizedBox(width: 8),
              Expanded(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Installing $_installingPackage... ${(_installProgress * 100).round()}%',
                    style: textTheme.bodySmall?.copyWith(color: colorScheme.onSurface),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: _installProgress,
            backgroundColor: colorScheme.surfaceContainerHighest,
            valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
          ),
        ],
      ),
    );
  }
}
