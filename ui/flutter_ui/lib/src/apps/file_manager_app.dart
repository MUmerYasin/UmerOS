import 'package:flutter/material.dart';

class FileManagerApp extends StatefulWidget {
  const FileManagerApp({super.key});

  @override
  State<FileManagerApp> createState() => _FileManagerAppState();
}

class _FileManagerAppState extends State<FileManagerApp> {
  String _currentPath = '/home/user';
  String _selectedItem = '';
  bool _viewMode = false; // false = list, true = grid

  final Map<String, List<Map<String, dynamic>>> _fileSystem = {
    '/': [
      {'name': 'home', 'type': 'folder', 'icon': Icons.home, 'size': '--'},
      {'name': 'usr', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'bin', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'etc', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'var', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'tmp', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'opt', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'dev', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
    ],
    '/home': [
      {'name': 'user', 'type': 'folder', 'icon': Icons.person, 'size': '--'},
    ],
    '/home/user': [
      {'name': 'Documents', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'Downloads', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'Desktop', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'Pictures', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'Music', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': '.config', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
      {'name': 'README.md', 'type': 'file', 'icon': Icons.description, 'size': '2.4 KB'},
      {'name': 'config.json', 'type': 'file', 'icon': Icons.code, 'size': '1.1 KB'},
      {'name': 'script.sh', 'type': 'file', 'icon': Icons.terminal, 'size': '512 B'},
    ],
    '/home/user/Documents': [
      {'name': 'report.pdf', 'type': 'file', 'icon': Icons.picture_as_pdf, 'size': '1.2 MB'},
      {'name': 'notes.txt', 'type': 'file', 'icon': Icons.description, 'size': '4.5 KB'},
      {'name': 'project', 'type': 'folder', 'icon': Icons.folder, 'size': '--'},
    ],
    '/home/user/Downloads': [
      {'name': 'image.png', 'type': 'file', 'icon': Icons.image, 'size': '2.3 MB'},
      {'name': 'archive.zip', 'type': 'file', 'icon': Icons.archive, 'size': '15.6 MB'},
    ],
  };

  List<Map<String, dynamic>> get _currentFiles =>
      _fileSystem[_currentPath] ?? [];

  void _navigateTo(String path) {
    setState(() {
      _currentPath = path;
      _selectedItem = '';
    });
  }

  void _goBack() {
    if (_currentPath == '/') return;
    final parts = _currentPath.split('/');
    parts.removeLast();
    _navigateTo(parts.join('/') == '' ? '/' : parts.join('/'));
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Sidebar
        Container(
          width: 200,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
            border: Border(
              right: BorderSide(
                color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'Favorites',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                ),
              ),
              _SidebarItem(
                icon: Icons.home,
                label: 'Home',
                onTap: () => _navigateTo('/home/user'),
              ),
              _SidebarItem(
                icon: Icons.description,
                label: 'Documents',
                onTap: () => _navigateTo('/home/user/Documents'),
              ),
              _SidebarItem(
                icon: Icons.download,
                label: 'Downloads',
                onTap: () => _navigateTo('/home/user/Downloads'),
              ),
              _SidebarItem(
                icon: Icons.image,
                label: 'Pictures',
                onTap: () => _navigateTo('/home/user/Pictures'),
              ),
              const Divider(),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'Devices',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                ),
              ),
              _SidebarItem(
                icon: Icons.computer,
                label: 'Root (/)',
                onTap: () => _navigateTo('/'),
              ),
              _SidebarItem(
                icon: Icons.sd_storage,
                label: 'QFS Drive',
                onTap: () => _navigateTo('/opt'),
              ),
            ],
          ),
        ),

        // Main Content
        Expanded(
          child: Column(
            children: [
              // Toolbar
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface,
                  border: Border(
                    bottom: BorderSide(
                      color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: _goBack,
                      iconSize: 20,
                    ),
                    IconButton(
                      icon: const Icon(Icons.arrow_forward),
                      onPressed: () {},
                      iconSize: 20,
                    ),
                    IconButton(
                      icon: const Icon(Icons.arrow_upward),
                      onPressed: () {
                        if (_currentPath != '/') {
                          _goBack();
                        }
                      },
                      iconSize: 20,
                    ),
                    const SizedBox(width: 8),
                    // Path Bar
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          _currentPath,
                          style: TextStyle(
                            fontSize: 13,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      icon: Icon(_viewMode ? Icons.view_list : Icons.grid_view),
                      onPressed: () => setState(() => _viewMode = !_viewMode),
                      iconSize: 20,
                    ),
                  ],
                ),
              ),

              // File List
              Expanded(
                child: _viewMode ? _buildGridView() : _buildListView(),
              ),

              // Status Bar
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface,
                  border: Border(
                    top: BorderSide(
                      color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Text(
                      '${_currentFiles.length} items',
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                    const Spacer(),
                    if (_selectedItem.isNotEmpty)
                      Text(
                        'Selected: $_selectedItem',
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildListView() {
    return ListView.builder(
      itemCount: _currentFiles.length,
      itemBuilder: (context, index) {
        final file = _currentFiles[index];
        final isSelected = _selectedItem == file['name'];

        return ListTile(
          leading: Icon(
            file['icon'] as IconData,
            color: file['type'] == 'folder'
                ? Colors.blue
                : Theme.of(context).colorScheme.primary,
          ),
          title: Text(file['name'] as String),
          subtitle: file['type'] == 'file' ? Text(file['size'] as String) : null,
          selected: isSelected,
          selectedTileColor: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.3),
          onTap: () {
            setState(() => _selectedItem = file['name'] as String);
            if (file['type'] == 'folder') {
              _navigateTo('$_currentPath/${file['name']}');
            }
          },
          onLongPress: () {
            if (file['type'] == 'folder') {
              _navigateTo('$_currentPath/${file['name']}');
            }
          },
        );
      },
    );
  }

  Widget _buildGridView() {
    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 5,
        mainAxisSpacing: 16,
        crossAxisSpacing: 16,
        childAspectRatio: 0.8,
      ),
      itemCount: _currentFiles.length,
      itemBuilder: (context, index) {
        final file = _currentFiles[index];
        final isSelected = _selectedItem == file['name'];

        return GestureDetector(
          onTap: () {
            setState(() => _selectedItem = file['name'] as String);
            if (file['type'] == 'folder') {
              _navigateTo('$_currentPath/${file['name']}');
            }
          },
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: isSelected
                      ? Theme.of(context).colorScheme.primaryContainer
                      : Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  file['icon'] as IconData,
                  size: 32,
                  color: file['type'] == 'folder'
                      ? Colors.blue
                      : Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                file['name'] as String,
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        );
      },
    );
  }
}

class _SidebarItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _SidebarItem({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, size: 20),
      title: Text(label, style: const TextStyle(fontSize: 13)),
      dense: true,
      onTap: onTap,
    );
  }
}
