/// UmerOS Legal Manager — Legal, Compliance & Consent
///
/// Desktop control panel for the UmerOS legal subsystem.
/// Manages disclaimers, consent, contributors, donations, licenses, maintainers.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class LegalManagerApp extends StatefulWidget {
  const LegalManagerApp({super.key});

  @override
  State<LegalManagerApp> createState() => _LegalManagerAppState();
}

class _LegalManagerAppState extends State<LegalManagerApp> {
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
              _Tab('Disclaimer', 0, Icons.warning),
              _Tab('Consent', 1, Icons.check_circle),
              _Tab('Contributors', 2, Icons.people),
              _Tab('Donations', 3, Icons.volunteer_activism),
              _Tab('Licenses', 4, Icons.description),
              _Tab('Maintainers', 5, Icons.admin_panel_settings),
              _Tab('Safety', 6, Icons.shield),
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
        return _DisclaimerTab();
      case 1:
        return _ConsentTab();
      case 2:
        return _ContributorsTab();
      case 3:
        return _DonationsTab();
      case 4:
        return _LicensesTab();
      case 5:
        return _MaintainersTab();
      case 6:
        return _SafetyTab();
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

// ── Tab: Disclaimer ──────────────────────────────────────────────
class _DisclaimerTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Legal Disclaimer',
            body: 'UmerOS is provided "as is" without warranty of any kind.',
          ),
          const SizedBox(height: 16),
          _DisclaimerEntry(risk: 'High', title: 'System Modification', description: 'Modifying system files may cause data loss.', color: Colors.red),
          _DisclaimerEntry(risk: 'Medium', title: 'Network Access', description: 'Network operations may expose your system.', color: Colors.orange),
          _DisclaimerEntry(risk: 'Low', title: 'Software Installation', description: 'Installing software may affect system stability.', color: Colors.green),
        ],
      ),
    );
  }
}

class _DisclaimerEntry extends StatelessWidget {
  final String risk;
  final String title;
  final String description;
  final Color color;
  const _DisclaimerEntry({
    required this.risk,
    required this.title,
    required this.description,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.warning, color: color, size: 20),
        title: Text(title, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(risk, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Consent ─────────────────────────────────────────────────
class _ConsentTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'User Consent',
            body: 'Consent records and verification gates.',
          ),
          const SizedBox(height: 16),
          _ConsentEntry(action: 'Terms of Service', status: 'Accepted', date: '2026-10-30', color: Colors.green),
          _ConsentEntry(action: 'Privacy Policy', status: 'Accepted', date: '2026-10-30', color: Colors.green),
          _ConsentEntry(action: 'Data Collection', status: 'Pending', date: 'N/A', color: Colors.orange),
        ],
      ),
    );
  }
}

class _ConsentEntry extends StatelessWidget {
  final String action;
  final String status;
  final String date;
  final Color color;
  const _ConsentEntry({
    required this.action,
    required this.status,
    required this.date,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.check_circle, color: color, size: 20),
        title: Text(action, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Date: $date', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Contributors ────────────────────────────────────────────
class _ContributorsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Contributors',
            body: 'Contributor registry with DCO status.',
          ),
          const SizedBox(height: 16),
          _ContributorEntry(name: 'Umer Yasin', role: 'Founder', dco: 'Signed', color: Colors.green),
          _ContributorEntry(name: 'Contributor A', role: 'Developer', dco: 'Signed', color: Colors.green),
          _ContributorEntry(name: 'Contributor B', role: 'Tester', dco: 'Pending', color: Colors.orange),
        ],
      ),
    );
  }
}

class _ContributorEntry extends StatelessWidget {
  final String name;
  final String role;
  final String dco;
  final Color color;
  const _ContributorEntry({
    required this.name,
    required this.role,
    required this.dco,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.blue.withValues(alpha: 0.15),
          child: Text(name[0], style: GoogleFonts.inter(fontSize: 12, color: Colors.blue, fontWeight: FontWeight.bold)),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Role: $role', style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text('DCO: $dco', style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Donations ───────────────────────────────────────────────
class _DonationsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Donations & Sponsors',
            body: 'Donation records and funding channels.',
          ),
          const SizedBox(height: 16),
          _DonationEntry(tier: 'Gold', name: 'Sponsor A', amount: '\$500', color: Colors.amber),
          _DonationEntry(tier: 'Silver', name: 'Sponsor B', amount: '\$200', color: Colors.grey),
          _DonationEntry(tier: 'Bronze', name: 'Sponsor C', amount: '\$50', color: Colors.brown),
        ],
      ),
    );
  }
}

class _DonationEntry extends StatelessWidget {
  final String tier;
  final String name;
  final String amount;
  final Color color;
  const _DonationEntry({
    required this.tier,
    required this.name,
    required this.amount,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.volunteer_activism, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Tier: $tier', style: GoogleFonts.inter(fontSize: 11)),
        trailing: Text(amount, style: GoogleFonts.firaCode(fontSize: 12, color: Colors.green, fontWeight: FontWeight.bold)),
      ),
    );
  }
}

// ── Tab: Licenses ────────────────────────────────────────────────
class _LicensesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'License Compliance',
            body: 'Open-source license audit and compliance.',
          ),
          const SizedBox(height: 16),
          _LicenseEntry(name: 'GPL-3.0', type: 'Copyleft', files: '1,247', status: 'Compliant', color: Colors.green),
          _LicenseEntry(name: 'MIT', type: 'Permissive', files: '45', status: 'Compliant', color: Colors.green),
          _LicenseEntry(name: 'Apache-2.0', type: 'Permissive', files: '12', status: 'Compliant', color: Colors.green),
          _LicenseEntry(name: 'BSD-3-Clause', type: 'Permissive', files: '8', status: 'Compliant', color: Colors.green),
        ],
      ),
    );
  }
}

class _LicenseEntry extends StatelessWidget {
  final String name;
  final String type;
  final String files;
  final String status;
  final Color color;
  const _LicenseEntry({
    required this.name,
    required this.type,
    required this.files,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.description, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$type · $files files', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Maintainers ─────────────────────────────────────────────
class _MaintainersTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Maintainers',
            body: 'Core maintainer profiles and key fingerprints.',
          ),
          const SizedBox(height: 16),
          _MaintainerEntry(name: 'Umer Yasin', role: 'Lead Maintainer', keyType: 'ED25519', status: 'Active', color: Colors.green),
          _MaintainerEntry(name: 'Co-Maintainer', role: 'Co-Maintainer', keyType: 'ED25519', status: 'Active', color: Colors.green),
        ],
      ),
    );
  }
}

class _MaintainerEntry extends StatelessWidget {
  final String name;
  final String role;
  final String keyType;
  final String status;
  final Color color;
  const _MaintainerEntry({
    required this.name,
    required this.role,
    required this.keyType,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.admin_panel_settings, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$role · Key: $keyType', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Safety ──────────────────────────────────────────────────
class _SafetyTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Safety Checks',
            body: 'Pre-execution safety checkpoints and backup gates.',
          ),
          const SizedBox(height: 16),
          _SafetyEntry(check: 'Backup Gate', status: 'Passed', color: Colors.green),
          _SafetyEntry(check: 'PII Scan', status: 'Passed', color: Colors.green),
          _SafetyEntry(check: 'License Compliance', status: 'Passed', color: Colors.green),
          _SafetyEntry(check: 'Consent Verification', status: 'Passed', color: Colors.green),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.shield),
            label: const Text('Run Safety Check'),
          ),
        ],
      ),
    );
  }
}

class _SafetyEntry extends StatelessWidget {
  final String check;
  final String status;
  final Color color;
  const _SafetyEntry({
    required this.check,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.shield, color: color, size: 20),
        title: Text(check, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
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