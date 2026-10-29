/// UmerOS /sources Manager — Standards, Bibliography, Signals & Docs
///
/// Desktop control panel for the UmerOS /sources subsystem.
/// Manages signals, glossary, bibliography, kernel docs, and source tree.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class SourcesManagerApp extends StatefulWidget {
  const SourcesManagerApp({super.key});

  @override
  State<SourcesManagerApp> createState() => _SourcesManagerAppState();
}

class _SourcesManagerAppState extends State<SourcesManagerApp> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        Container(
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(
              bottom: BorderSide(color: scheme.outline.withValues(alpha: 0.2)),
            ),
          ),
          child: AutoAdjustRow(
            spacing: 0,
            children: [
              _Tab('Signals', 0, Icons.bolt),
              _Tab('Glossary', 1, Icons.book),
              _Tab('Bibliography', 2, Icons.library_books),
              _Tab('Kernel Docs', 3, Icons.description),
              _Tab('Source Tree', 4, Icons.folder),
            ].map((t) => _TabButton(
              label: t.label,
              icon: t.icon,
              isSelected: _tab == t.index,
              onTap: () => setState(() => _tab = t.index),
            )).toList(),
          ),
        ),
        Expanded(child: _buildTabContent()),
      ],
    );
  }

  Widget _buildTabContent() {
    switch (_tab) {
      case 0:
        return _SignalsTab();
      case 1:
        return _GlossaryTab();
      case 2:
        return _BibliographyTab();
      case 3:
        return _KernelDocsTab();
      case 4:
        return _SourceTreeTab();
      default:
        return const SizedBox.shrink();
    }
  }
}

class _Tab {
  final String label;
  final int index;
  final IconData icon;
  const _Tab(this.label, this.index, this.icon);
}

class _TabButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;
  const _TabButton({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              width: 2,
              color: isSelected ? scheme.primary : Colors.transparent,
            ),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: isSelected ? scheme.primary : scheme.onSurfaceVariant),
            const SizedBox(width: 6),
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                color: isSelected ? scheme.primary : scheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Tab: Signals ─────────────────────────────────────────
class _SignalsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final signals = [
      _SignalEntry(name: 'SIGHUP', number: 1, action: 'Term', description: 'Hangup detected on controlling terminal'),
      _SignalEntry(name: 'SIGINT', number: 2, action: 'Term', description: 'Interrupt from keyboard (Ctrl+C)'),
      _SignalEntry(name: 'SIGQUIT', number: 3, action: 'Core', description: 'Quit from keyboard (Ctrl+\\)'),
      _SignalEntry(name: 'SIGILL', number: 4, action: 'Core', description: 'Illegal instruction'),
      _SignalEntry(name: 'SIGTRAP', number: 5, action: 'Core', description: 'Trace/breakpoint trap'),
      _SignalEntry(name: 'SIGABRT', number: 6, action: 'Core', description: 'Abort signal'),
      _SignalEntry(name: 'SIGBUS', number: 7, action: 'Core', description: 'Bus error (bad memory access)'),
      _SignalEntry(name: 'SIGFPE', number: 8, action: 'Core', description: 'Floating-point exception'),
      _SignalEntry(name: 'SIGKILL', number: 9, action: 'Term', description: 'Kill signal (cannot be caught)'),
      _SignalEntry(name: 'SIGUSR1', number: 10, action: 'Term', description: 'User-defined signal 1'),
      _SignalEntry(name: 'SIGSEGV', number: 11, action: 'Core', description: 'Invalid memory reference'),
      _SignalEntry(name: 'SIGUSR2', number: 12, action: 'Term', description: 'User-defined signal 2'),
      _SignalEntry(name: 'SIGPIPE', number: 13, action: 'Term', description: 'Broken pipe'),
      _SignalEntry(name: 'SIGALRM', number: 14, action: 'Term', description: 'Timer signal'),
      _SignalEntry(name: 'SIGTERM', number: 15, action: 'Term', description: 'Termination signal'),
      _SignalEntry(name: 'SIGCHLD', number: 17, action: 'Ign', description: 'Child stopped or terminated'),
      _SignalEntry(name: 'SIGCONT', number: 18, action: 'Cont', description: 'Continue if stopped'),
      _SignalEntry(name: 'SIGSTOP', number: 19, action: 'Stop', description: 'Stop process (cannot be caught)'),
      _SignalEntry(name: 'SIGTSTP', number: 20, action: 'Stop', description: 'Stop from terminal (Ctrl+Z)'),
      _SignalEntry(name: 'SIGTTIN', number: 21, action: 'Stop', description: 'Background read from tty'),
      _SignalEntry(name: 'SIGTTOU', number: 22, action: 'Stop', description: 'Background write to tty'),
    ];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'UNIX System V Signals',
            body: 'Complete POSIX signal specification with default actions, '
                'signal masks, handlers, and dispatching engine.',
          ),
          const SizedBox(height: 16),
          ...signals.map((s) => _SignalTile(signal: s)),
        ],
      ),
    );
  }
}

class _SignalEntry {
  final String name;
  final int number;
  final String action;
  final String description;
  const _SignalEntry({
    required this.name,
    required this.number,
    required this.action,
    required this.description,
  });
}

class _SignalTile extends StatelessWidget {
  final _SignalEntry signal;
  const _SignalTile({required this.signal});

  @override
  Widget build(BuildContext context) {
    final actionColor = switch (signal.action) {
      'Term' => Colors.red,
      'Core' => Colors.orange,
      'Ign' => Colors.grey,
      'Stop' => Colors.blue,
      'Cont' => Colors.green,
      _ => Colors.grey,
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: actionColor.withValues(alpha: 0.15),
          child: Text('${signal.number}', style: GoogleFonts.firaCode(fontSize: 11, color: actionColor, fontWeight: FontWeight.bold)),
        ),
        title: Text(signal.name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(signal.description, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: actionColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(signal.action, style: GoogleFonts.inter(fontSize: 10, color: actionColor, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Glossary ────────────────────────────────────────
class _GlossaryTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final terms = [
      _GlossaryEntry(term: 'CAS', definition: 'Content-Addressed Storage — data identified by its content hash'),
      _GlossaryEntry(term: 'IPC', definition: 'Inter-Process Communication — mechanism for processes to exchange data'),
      _GlossaryEntry(term: 'KVM', definition: 'Kernel-based Virtual Machine — hardware virtualization'),
      _GlossaryEntry(term: 'QFS', definition: 'Quantum File System — content-addressed filesystem with compression'),
      _GlossaryEntry(term: 'UDMF', definition: 'Unified Data Management Framework — typed data exchange'),
      _GlossaryEntry(term: 'UTD', definition: 'Uniform Type Descriptor — hierarchical data type identifiers'),
      _GlossaryEntry(term: 'vCPU', definition: 'Virtual CPU — emulated processor for guest VMs'),
      _GlossaryEntry(term: 'VFIO', definition: 'Virtual Function I/O — device passthrough framework'),
      _GlossaryEntry(term: 'MMIO', definition: 'Memory-Mapped I/O — device registers mapped to memory'),
      _GlossaryEntry(term: 'DMA', definition: 'Direct Memory Access — hardware data transfer without CPU'),
    ];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Glossary & Terminology',
            body: 'Definitions of key UmerOS and systems programming terms.',
          ),
          const SizedBox(height: 16),
          ...terms.map((t) => _GlossaryTile(entry: t)),
        ],
      ),
    );
  }
}

class _GlossaryEntry {
  final String term;
  final String definition;
  const _GlossaryEntry({required this.term, required this.definition});
}

class _GlossaryTile extends StatelessWidget {
  final _GlossaryEntry entry;
  const _GlossaryTile({required this.entry});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.indigo.withValues(alpha: 0.15),
          child: Text(entry.term[0], style: GoogleFonts.inter(fontSize: 12, color: Colors.indigo, fontWeight: FontWeight.bold)),
        ),
        title: Text(entry.term, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(entry.definition, style: GoogleFonts.inter(fontSize: 12)),
      ),
    );
  }
}

// ── Tab: Bibliography ────────────────────────────────────
class _BibliographyTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final sources = [
      _BibEntry(title: 'Linux Kernel Documentation', author: 'Linux Kernel Community', year: '2024', category: 'Kernel'),
      _BibEntry(title: 'Understanding the Linux Kernel', author: 'Bovet & Cesati', year: '2005', category: 'Books'),
      _BibEntry(title: 'Linux Device Drivers', author: 'Corbet, Rubini & Kroah-Hartman', year: '2005', category: 'Books'),
      _BibEntry(title: 'Advanced Programming in UNIX', author: 'Stevens & Rago', year: '2013', category: 'Books'),
      _BibEntry(title: 'Quantum Computation and Information', author: 'Nielsen & Chuang', year: '2010', category: 'Quantum'),
      _BibEntry(title: 'The Art of Computer Programming', author: 'Knuth', year: '1997', category: 'Algorithms'),
    ];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Bibliography & References',
            body: 'Curated list of reference sources for UmerOS development.',
          ),
          const SizedBox(height: 16),
          ...sources.map((s) => _BibTile(entry: s)),
        ],
      ),
    );
  }
}

class _BibEntry {
  final String title;
  final String author;
  final String year;
  final String category;
  const _BibEntry({
    required this.title,
    required this.author,
    required this.year,
    required this.category,
  });
}

class _BibTile extends StatelessWidget {
  final _BibEntry entry;
  const _BibTile({required this.entry});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.amber.withValues(alpha: 0.15),
          child: const Icon(Icons.menu_book, color: Colors.amber, size: 18),
        ),
        title: Text(entry.title, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('${entry.author} (${entry.year}) · ${entry.category}', style: GoogleFonts.inter(fontSize: 11)),
      ),
    );
  }
}

// ── Tab: Kernel Docs ─────────────────────────────────────
class _KernelDocsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Kernel Documentation',
            body: 'proc.txt, initrd.txt, runlevels and other kernel documentation.',
          ),
          const SizedBox(height: 16),
          _DocEntry(name: 'proc.txt', description: 'Process information pseudo-filesystem', size: '4.2 KB'),
          _DocEntry(name: 'initrd.txt', description: 'Initial RAM disk specification', size: '3.1 KB'),
          _DocEntry(name: 'runlevels', description: 'System runlevel definitions', size: '1.8 KB'),
          _DocEntry(name: 'sysctl.conf', description: 'Kernel parameter configuration', size: '2.4 KB'),
          _DocEntry(name: 'fstab', description: 'Filesystem table', size: '1.1 KB'),
        ],
      ),
    );
  }
}

class _DocEntry extends StatelessWidget {
  final String name;
  final String description;
  final String size;
  const _DocEntry({
    required this.name,
    required this.description,
    required this.size,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.description, color: Colors.teal, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Text(size, style: GoogleFonts.inter(fontSize: 11, color: Colors.grey)),
      ),
    );
  }
}

// ── Tab: Source Tree ─────────────────────────────────────
class _SourceTreeTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Source Tree (/usr/src)',
            body: 'Kernel source hierarchy and package metadata.',
          ),
          const SizedBox(height: 16),
          _SourceEntry(name: 'linux-6.x', type: 'Kernel Source', status: 'Available', color: Colors.green),
          _SourceEntry(name: 'umeros-1.0', type: 'UmerOS Source', status: 'Active', color: Colors.blue),
          _SourceEntry(name: 'headers', type: 'Kernel Headers', status: 'Installed', color: Colors.orange),
          _SourceEntry(name: 'modules', type: 'Kernel Modules', status: 'Available', color: Colors.purple),
        ],
      ),
    );
  }
}

class _SourceEntry extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _SourceEntry({
    required this.name,
    required this.type,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.folder, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(type, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Shared widgets ───────────────────────────────────────
class _InfoCard extends StatelessWidget {
  final String title;
  final String body;
  const _InfoCard({required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.blue.shade50,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.blue.shade100),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.blue.shade900)),
          const SizedBox(height: 4),
          Text(body, style: GoogleFonts.inter(fontSize: 12, color: Colors.blue.shade800, height: 1.4)),
        ],
      ),
    );
  }
}