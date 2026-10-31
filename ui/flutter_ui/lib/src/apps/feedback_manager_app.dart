/// UmerOS Feedback Manager — Community Feedback & Bug Reports
///
/// Desktop control panel for the UmerOS feedback subsystem.
/// Manages bug reports, suggestions, feature requests, and triage.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class FeedbackManagerApp extends StatefulWidget {
  const FeedbackManagerApp({super.key});

  @override
  State<FeedbackManagerApp> createState() => _FeedbackManagerAppState();
}

class _FeedbackManagerAppState extends State<FeedbackManagerApp> {
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
              _Tab('Reports', 0, Icons.bug_report),
              _Tab('Suggestions', 1, Icons.lightbulb),
              _Tab('Features', 2, Icons.new_releases),
              _Tab('Triage', 3, Icons.label),
              _Tab('Stats', 4, Icons.bar_chart),
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
        return _ReportsTab();
      case 1:
        return _SuggestionsTab();
      case 2:
        return _FeaturesTab();
      case 3:
        return _TriageTab();
      case 4:
        return _StatsTab();
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

// ── Tab: Reports ─────────────────────────────────────────────────
class _ReportsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Bug Reports',
            body: 'Community bug reports and issues.',
          ),
          const SizedBox(height: 16),
          _FeedbackEntry(id: '#142', title: 'Crash on startup', kind: 'Bug', priority: 'High', status: 'Open', color: Colors.red),
          _FeedbackEntry(id: '#138', title: 'Memory leak in scheduler', kind: 'Bug', priority: 'Medium', status: 'In Progress', color: Colors.orange),
          _FeedbackEntry(id: '#125', title: 'UI glitch in settings', kind: 'Bug', priority: 'Low', status: 'Resolved', color: Colors.green),
        ],
      ),
    );
  }
}

class _FeedbackEntry extends StatelessWidget {
  final String id;
  final String title;
  final String kind;
  final String priority;
  final String status;
  final Color color;
  const _FeedbackEntry({
    required this.id,
    required this.title,
    required this.kind,
    required this.priority,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Text(id, style: GoogleFonts.firaCode(fontSize: 10, color: Colors.grey.shade600, fontWeight: FontWeight.bold)),
        title: Text(title, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$kind · $priority', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Suggestions ─────────────────────────────────────────────
class _SuggestionsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Suggestions',
            body: 'Community suggestions and improvements.',
          ),
          const SizedBox(height: 16),
          _FeedbackEntry(id: '#140', title: 'Add dark mode toggle', kind: 'Suggestion', priority: 'Medium', status: 'Under Review', color: Colors.blue),
          _FeedbackEntry(id: '#135', title: 'Improve search performance', kind: 'Suggestion', priority: 'High', status: 'Accepted', color: Colors.green),
          _FeedbackEntry(id: '#128', title: 'Add keyboard shortcuts', kind: 'Suggestion', priority: 'Low', status: 'Rejected', color: Colors.grey),
        ],
      ),
    );
  }
}

// ── Tab: Features ────────────────────────────────────────────────
class _FeaturesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Feature Requests',
            body: 'Requested features from the community.',
          ),
          const SizedBox(height: 16),
          _FeedbackEntry(id: '#145', title: 'Quantum circuit visualizer', kind: 'Feature', priority: 'High', status: 'Planned', color: Colors.purple),
          _FeedbackEntry(id: '#141', title: 'Multi-monitor support', kind: 'Feature', priority: 'Medium', status: 'Planned', color: Colors.purple),
          _FeedbackEntry(id: '#133', title: 'Plugin system', kind: 'Feature', priority: 'Low', status: 'Under Review', color: Colors.blue),
        ],
      ),
    );
  }
}

// ── Tab: Triage ──────────────────────────────────────────────────
class _TriageTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Triage',
            body: 'Triage and assign feedback items.',
          ),
          const SizedBox(height: 16),
          _TriageEntry(item: '#142', assignee: 'Developer A', priority: 'High', status: 'Assigned', color: Colors.blue),
          _TriageEntry(item: '#140', assignee: 'Developer B', priority: 'Medium', status: 'Assigned', color: Colors.blue),
          _TriageEntry(item: '#145', assignee: 'Unassigned', priority: 'High', status: 'Needs Triage', color: Colors.orange),
        ],
      ),
    );
  }
}

class _TriageEntry extends StatelessWidget {
  final String item;
  final String assignee;
  final String priority;
  final String status;
  final Color color;
  const _TriageEntry({
    required this.item,
    required this.assignee,
    required this.priority,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Text(item, style: GoogleFonts.firaCode(fontSize: 10, color: Colors.grey.shade600, fontWeight: FontWeight.bold)),
        title: Text(assignee, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Priority: $priority', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Stats ───────────────────────────────────────────────────
class _StatsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Feedback Statistics',
            body: 'Overview of feedback and bug reports.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Total Reports', value: '145'),
          _InfoRow(label: 'Open', value: '23'),
          _InfoRow(label: 'In Progress', value: '12'),
          _InfoRow(label: 'Resolved', value: '98'),
          _InfoRow(label: 'Rejected', value: '12'),
          _InfoRow(label: 'Avg Resolution Time', value: '3.2 days'),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        title: Text(label, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(value, style: GoogleFonts.inter(fontSize: 12, color: Colors.grey.shade700)),
      ),
    );
  }
}

// ── Shared widgets ───────────────────────────────────────────────
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