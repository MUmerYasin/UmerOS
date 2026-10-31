/// UmerOS AI Manager — AI Assistant & Providers
///
/// Desktop control panel for the UmerOS AI subsystem.
/// Covers all AI modules.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AiManagerApp extends StatefulWidget {
  const AiManagerApp({super.key});

  @override
  State<AiManagerApp> createState() => _AiManagerAppState();
}

class _AiManagerAppState extends State<AiManagerApp> {
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
          child: Row(
            children: [
              _Tab('Assistant', 0, Icons.smart_toy),
              _Tab('Models', 1, Icons.model_training),
              _Tab('Providers', 2, Icons.cloud),
              _Tab('Resources', 3, Icons.memory),
              _Tab('Self-Healing', 4, Icons.healing),
              _Tab('Governance', 5, Icons.gavel),
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
        return _AssistantTab();
      case 1:
        return _ModelsTab();
      case 2:
        return _ProvidersTab();
      case 3:
        return _ResourcesTab();
      case 4:
        return _SelfHealingTab();
      case 5:
        return _GovernanceTab();
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

// ── Tab: Assistant ───────────────────────────────────────────────
class _AssistantTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'AI Assistant',
            body: 'Local AI assistant service.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Service', value: 'assistant.py'),
          _InfoRow(label: 'Status', value: 'Running'),
          _InfoRow(label: 'Port', value: '8421'),
          _InfoRow(label: 'Chat Service', value: 'Available'),
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

// ── Tab: Models ──────────────────────────────────────────────────
class _ModelsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Model Manager',
            body: 'Download, cache, and load AI models.',
          ),
          const SizedBox(height: 16),
          _ModelEntry(name: 'llama-3.2-1b', size: '1.2 GB', status: 'Downloaded', color: Colors.green),
          _ModelEntry(name: 'llama-3.2-3b', size: '2.0 GB', status: 'Downloaded', color: Colors.green),
          _ModelEntry(name: 'mistral-7b', size: '4.1 GB', status: 'Available', color: Colors.blue),
          _ModelEntry(name: 'phi-3-mini', size: '2.3 GB', status: 'Available', color: Colors.blue),
        ],
      ),
    );
  }
}

class _ModelEntry extends StatelessWidget {
  final String name;
  final String size;
  final String status;
  final Color color;
  const _ModelEntry({
    required this.name,
    required this.size,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.model_training, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Size: $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Providers ───────────────────────────────────────────────
class _ProvidersTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'AI Providers',
            body: 'Provider registry and adapters.',
          ),
          const SizedBox(height: 16),
          _ProviderEntry(name: 'OpenAI', type: 'Paid', status: 'Available', color: Colors.green),
          _ProviderEntry(name: 'Anthropic', type: 'Paid', status: 'Available', color: Colors.green),
          _ProviderEntry(name: 'Gemini', type: 'Free/Paid', status: 'Available', color: Colors.green),
          _ProviderEntry(name: 'Ollama', type: 'Local', status: 'Available', color: Colors.blue),
          _ProviderEntry(name: 'LlamaCpp', type: 'Local', status: 'Available', color: Colors.blue),
        ],
      ),
    );
  }
}

class _ProviderEntry extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _ProviderEntry({
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
        leading: Icon(Icons.cloud, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Type: $type', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Resources ───────────────────────────────────────────────
class _ResourcesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Resource Predictor',
            body: 'AI resource prediction and management.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Predictor', value: 'ResourcePredictor'),
          _InfoRow(label: 'AI Resource Manager', value: 'AIResourceManager'),
          _InfoRow(label: 'Status', value: 'Active'),
        ],
      ),
    );
  }
}

// ── Tab: Self-Healing ─────────────────────────────────────────────
class _SelfHealingTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Self-Healing',
            body: 'Self-healing service and engine.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Service', value: 'SelfHealingService'),
          _InfoRow(label: 'Engine', value: 'SelfHealingEngine'),
          _InfoRow(label: 'Status', value: 'Active'),
          _InfoRow(label: 'CAP_SYS_ADMIN', value: 'Required'),
        ],
      ),
    );
  }
}

// ── Tab: Governance ──────────────────────────────────────────────
class _GovernanceTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'AI Governance',
            body: 'AI governance and consent management.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Governance', value: 'AIGovernance'),
          _InfoRow(label: 'Consent', value: 'ConsentManager'),
          _InfoRow(label: 'Status', value: 'Active'),
        ],
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