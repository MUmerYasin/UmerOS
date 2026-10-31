/// UmerOS Docs Manager — Documentation Browser
///
/// Desktop control panel for browsing /docs files.
/// Can open every documentation file in the /docs folder.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class DocsManagerApp extends StatefulWidget {
  const DocsManagerApp({super.key});

  @override
  State<DocsManagerApp> createState() => _DocsManagerAppState();
}

class _DocsManagerAppState extends State<DocsManagerApp> {
  int _selectedIndex = 0;
  final List<_DocFile> _docs = const [
    _DocFile('api_reference.md', 'API Reference', 'API documentation and reference', Icons.api),
    _DocFile('architecture.md', 'Architecture', 'System architecture overview', Icons.architecture),
    _DocFile('developer_guide.md', 'Developer Guide', 'Guide for developers', Icons.code),
    _DocFile('driver_writing_guide.md', 'Driver Writing Guide', 'Guide for writing drivers', Icons.extension),
    _DocFile('HARDWARE_REQUIREMENTS.md', 'Hardware Requirements', 'Hardware requirements specification', Icons.memory),
    _DocFile('index.html', 'Index', 'Documentation index page', Icons.home),
    _DocFile('installation_guide.md', 'Installation Guide', 'Installation instructions', Icons.install_desktop),
    _DocFile('quantum_tutorial.md', 'Quantum Tutorial', 'Quantum computing tutorial', Icons.science),
    _DocFile('reference_corpus.md', 'Reference Corpus', 'Reference corpus documentation', Icons.library_books),
    _DocFile('user_manual.md', 'User Manual', 'User manual and guide', Icons.menu_book),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        // Sidebar
        Container(
          width: 240,
          decoration: BoxDecoration(
            color: scheme.surfaceContainerHighest.withValues(alpha: 0.3),
            border: Border(
              right: BorderSide(color: scheme.outline.withValues(alpha: 0.2)),
            ),
          ),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                child: Text(
                  'Documentation',
                  style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w600),
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView.builder(
                  itemCount: _docs.length,
                  itemBuilder: (context, index) {
                    final doc = _docs[index];
                    final isSelected = index == _selectedIndex;
                    return ListTile(
                      leading: Icon(doc.icon, size: 18, color: isSelected ? scheme.primary : scheme.onSurfaceVariant),
                      title: Text(
                        doc.title,
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                          color: isSelected ? scheme.primary : scheme.onSurface,
                        ),
                      ),
                      subtitle: Text(
                        doc.filename,
                        style: GoogleFonts.firaCode(fontSize: 9, color: scheme.onSurfaceVariant),
                      ),
                      selected: isSelected,
                      onTap: () => setState(() => _selectedIndex = index),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        // Content
        Expanded(
          child: _DocViewer(doc: _docs[_selectedIndex]),
        ),
      ],
    );
  }
}

class _DocFile {
  final String filename;
  final String title;
  final String description;
  final IconData icon;
  const _DocFile(this.filename, this.title, this.description, this.icon);
}

class _DocViewer extends StatelessWidget {
  final _DocFile doc;
  const _DocViewer({required this.doc});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(doc.icon, size: 24, color: scheme.primary),
              const SizedBox(width: 8),
              Text(
                doc.title,
                style: GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            doc.filename,
            style: GoogleFonts.firaCode(fontSize: 11, color: scheme.onSurfaceVariant),
          ),
          const SizedBox(height: 4),
          Text(
            doc.description,
            style: GoogleFonts.inter(fontSize: 13, color: scheme.onSurfaceVariant),
          ),
          const SizedBox(height: 16),
          const Divider(),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: scheme.outline.withValues(alpha: 0.2)),
            ),
            child: Text(
              'Content of ${doc.filename} would be loaded here.\n\n'
              'This is a placeholder for the actual file content.\n'
              'The file is located at: /docs/${doc.filename}',
              style: GoogleFonts.inter(fontSize: 13, height: 1.6),
            ),
          ),
        ],
      ),
    );
  }
}