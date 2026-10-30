/// UmerOS PQC Manager — Post-Quantum Cryptography
///
/// Desktop control panel for the UmerOS PQC subsystem.
/// Manages liboqs integration, KEM algorithms, signatures, provenance.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class PqcManagerApp extends StatefulWidget {
  const PqcManagerApp({super.key});

  @override
  State<PqcManagerApp> createState() => _PqcManagerAppState();
}

class _PqcManagerAppState extends State<PqcManagerApp> {
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
              _Tab('Overview', 0, Icons.security),
              _Tab('KEM', 1, Icons.vpn_key),
              _Tab('Signatures', 2, Icons.draw),
              _Tab('Provenance', 3, Icons.info),
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
        return _OverviewTab();
      case 1:
        return _KemTab();
      case 2:
        return _SignaturesTab();
      case 3:
        return _ProvenanceTab();
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

// ── Tab: Overview ────────────────────────────────────────────────
class _OverviewTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Post-Quantum Cryptography',
            body: 'PQC algorithms via vendored liboqs C library.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'liboqs Version', value: '0.16.0'),
          _InfoRow(label: 'Vendored Source', value: 'Present'),
          _InfoRow(label: 'Python Bindings', value: 'Not Available'),
          _InfoRow(label: 'KEM Algorithms', value: '12'),
          _InfoRow(label: 'Signature Algorithms', value: '8'),
          _InfoRow(label: 'Third-Party Notice', value: 'Present'),
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

// ── Tab: KEM ─────────────────────────────────────────────────────
class _KemTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Key Encapsulation Mechanisms',
            body: 'Post-quantum KEM algorithms available.',
          ),
          const SizedBox(height: 16),
          _AlgoEntry(name: 'ML-KEM-512', type: 'KEM', security: 'Level 1', status: 'Available', color: Colors.green),
          _AlgoEntry(name: 'ML-KEM-768', type: 'KEM', security: 'Level 3', status: 'Available', color: Colors.green),
          _AlgoEntry(name: 'ML-KEM-1024', type: 'KEM', security: 'Level 5', status: 'Available', color: Colors.green),
          _AlgoEntry(name: 'FrodoKEM-640', type: 'KEM', security: 'Level 1', status: 'Available', color: Colors.blue),
          _AlgoEntry(name: 'NTRU-HPS-2048', type: 'KEM', security: 'Level 1', status: 'Available', color: Colors.blue),
          _AlgoEntry(name: 'Kyber-512', type: 'KEM', security: 'Level 1', status: 'Available', color: Colors.orange),
        ],
      ),
    );
  }
}

class _AlgoEntry extends StatelessWidget {
  final String name;
  final String type;
  final String security;
  final String status;
  final Color color;
  const _AlgoEntry({
    required this.name,
    required this.type,
    required this.security,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.vpn_key, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$type · $security', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Signatures ──────────────────────────────────────────────
class _SignaturesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Digital Signature Algorithms',
            body: 'Post-quantum signature algorithms available.',
          ),
          const SizedBox(height: 16),
          _AlgoEntry(name: 'ML-DSA-44', type: 'Signature', security: 'Level 2', status: 'Available', color: Colors.green),
          _AlgoEntry(name: 'ML-DSA-65', type: 'Signature', security: 'Level 3', status: 'Available', color: Colors.green),
          _AlgoEntry(name: 'ML-DSA-87', type: 'Signature', security: 'Level 5', status: 'Available', color: Colors.green),
          _AlgoEntry(name: 'Falcon-512', type: 'Signature', security: 'Level 1', status: 'Available', color: Colors.blue),
          _AlgoEntry(name: 'Falcon-1024', type: 'Signature', security: 'Level 5', status: 'Available', color: Colors.blue),
          _AlgoEntry(name: 'SPHINCS+-SHA2-128f', type: 'Signature', security: 'Level 1', status: 'Available', color: Colors.orange),
          _AlgoEntry(name: 'Dilithium2', type: 'Signature', security: 'Level 2', status: 'Available', color: Colors.purple),
          _AlgoEntry(name: 'Dilithium3', type: 'Signature', security: 'Level 3', status: 'Available', color: Colors.purple),
        ],
      ),
    );
  }
}

// ── Tab: Provenance ──────────────────────────────────────────────
class _ProvenanceTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'liboqs Provenance',
            body: 'Integration status and provenance information.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Vendored Source Present', value: 'Yes'),
          _InfoRow(label: 'Vendored Source Dir', value: 'liboqs/'),
          _InfoRow(label: 'Vendored Version', value: '0.16.0'),
          _InfoRow(label: 'Declared in .gitmodules', value: 'Yes'),
          _InfoRow(label: 'Python Bindings Available', value: 'No'),
          _InfoRow(label: 'Python Bindings Version', value: 'N/A'),
          _InfoRow(label: 'Third-Party Notice Present', value: 'Yes'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.refresh),
            label: const Text('Check Integration'),
          ),
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