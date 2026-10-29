/// UmerOS Security Center — Zero-Trust, Crypto, Sandbox & Star Shield
///
/// Desktop control panel for the UmerOS security subsystem.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class SecurityCenterApp extends StatefulWidget {
  const SecurityCenterApp({super.key});

  @override
  State<SecurityCenterApp> createState() => _SecurityCenterAppState();
}

class _SecurityCenterAppState extends State<SecurityCenterApp> {
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
              _Tab('Overview', 0, Icons.shield),
              _Tab('Sandbox', 1, Icons.security),
              _Tab('Crypto', 2, Icons.lock),
              _Tab('Firewall', 3, Icons.local_fire_department),
              _Tab('Star Shield', 4, Icons.verified_user),
              _Tab('Antivirus', 5, Icons.health_and_safety),
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
        return _SandboxTab();
      case 2:
        return _CryptoTab();
      case 3:
        return _FirewallTab();
      case 4:
        return _StarShieldTab();
      case 5:
        return _AntivirusTab();
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

// ── Tab: Overview ────────────────────────────────────────
class _OverviewTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Security Overview',
            body: 'Zero-trust security architecture with capability-based '
                'access control, cryptographic primitives, and Star Shield DSLM.',
          ),
          const SizedBox(height: 16),
          _StatRow(label: 'Security Level', value: 'SL3', color: Colors.green),
          _StatRow(label: 'Active Sandboxes', value: '4', color: Colors.blue),
          _StatRow(label: 'Crypto Operations', value: '1,247', color: Colors.purple),
          _StatRow(label: 'Firewall Rules', value: '28', color: Colors.orange),
          _StatRow(label: 'Threats Blocked', value: '0', color: Colors.teal),
          _StatRow(label: 'Star Shield Status', value: 'Active', color: Colors.green),
        ],
      ),
    );
  }
}

class _StatRow extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatRow({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        title: Text(label, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(value, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 13, color: color)),
      ),
    );
  }
}

// ── Tab: Sandbox ─────────────────────────────────────────
class _SandboxTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Security Sandbox',
            body: 'Process isolation with capability-based access control. '
                'Sandboxed processes have restricted system call access.',
          ),
          const SizedBox(height: 16),
          _SandboxEntry(name: 'app_sandbox_1', type: 'Application', status: 'Active', color: Colors.green),
          _SandboxEntry(name: 'driver_sandbox', type: 'Driver', status: 'Active', color: Colors.green),
          _SandboxEntry(name: 'compat_sandbox', type: 'Compatibility', status: 'Active', color: Colors.blue),
          _SandboxEntry(name: 'temp_sandbox', type: 'Temporary', status: 'Idle', color: Colors.grey),
        ],
      ),
    );
  }
}

class _SandboxEntry extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _SandboxEntry({
    required this.name,
    required this.type,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final isActive = status == 'Active';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: const Icon(Icons.security, color: Colors.green, size: 18),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Type: $type'),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: (isActive ? Colors.green : Colors.grey).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: isActive ? Colors.green : Colors.grey, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Crypto ──────────────────────────────────────────
class _CryptoTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Cryptographic Engine',
            body: 'HMAC-SHA256, AES, RSA, and post-quantum interfaces. '
                'Key management and certificate handling.',
          ),
          const SizedBox(height: 16),
          _CryptoEntry(name: 'HMAC-SHA256', status: 'Active', color: Colors.green),
          _CryptoEntry(name: 'AES-256-GCM', status: 'Active', color: Colors.green),
          _CryptoEntry(name: 'RSA-2048', status: 'Active', color: Colors.green),
          _CryptoEntry(name: 'Kyber (PQC)', status: 'Experimental', color: Colors.orange),
          _CryptoEntry(name: 'Dilithium (PQC)', status: 'Experimental', color: Colors.orange),
          _CryptoEntry(name: 'Ed25519', status: 'Active', color: Colors.green),
        ],
      ),
    );
  }
}

class _CryptoEntry extends StatelessWidget {
  final String name;
  final String status;
  final Color color;
  const _CryptoEntry({
    required this.name,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final isActive = status == 'Active';
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: const Icon(Icons.lock, color: Colors.green, size: 18),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: (isActive ? Colors.green : Colors.orange).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: isActive ? Colors.green : Colors.orange, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Firewall ────────────────────────────────────────
class _FirewallTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Firewall & Network Security',
            body: 'Packet filtering, port blocking, and network access control.',
          ),
          const SizedBox(height: 16),
          _FirewallRule(name: 'Allow SSH (22)', action: 'ALLOW', color: Colors.green),
          _FirewallRule(name: 'Allow HTTP (80)', action: 'ALLOW', color: Colors.green),
          _FirewallRule(name: 'Allow HTTPS (443)', action: 'ALLOW', color: Colors.green),
          _FirewallRule(name: 'Block Telnet (23)', action: 'DENY', color: Colors.red),
          _FirewallRule(name: 'Block FTP (21)', action: 'DENY', color: Colors.red),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add Rule'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Reload'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _FirewallRule extends StatelessWidget {
  final String name;
  final String action;
  final Color color;
  const _FirewallRule({
    required this.name,
    required this.action,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final isAllow = action == 'ALLOW';
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(isAllow ? Icons.check_circle : Icons.block, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(action, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Star Shield ─────────────────────────────────────
class _StarShieldTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Star Shield — Device Security Level Management',
            body: 'DSLM (SL1-SL5) matched against Data Sensitivity (S1-S4). '
                'Scoped ephemeral tokens for permissionless pickers.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Device Security Levels'),
          const SizedBox(height: 8),
          _DslmEntry(name: 'This Node', level: 'SL3', status: 'Verified', color: Colors.green),
          _DslmEntry(name: 'Peer Node 1', level: 'SL4', status: 'Verified', color: Colors.green),
          _DslmEntry(name: 'Peer Node 2', level: 'SL2', status: 'Unverified', color: Colors.orange),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Data Sensitivity Levels'),
          const SizedBox(height: 8),
          _DslmEntry(name: 'S1 — Public', level: 'S1', status: 'Routable to all', color: Colors.green),
          _DslmEntry(name: 'S2 — Internal', level: 'S2', status: 'SL2+', color: Colors.blue),
          _DslmEntry(name: 'S3 — Confidential', level: 'S3', status: 'SL3+', color: Colors.orange),
          _DslmEntry(name: 'S4 — Critical', level: 'S4', status: 'SL4+', color: Colors.red),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Scoped Tokens'),
          const SizedBox(height: 8),
          _StatRow(label: 'Active Tokens', value: '3', color: Colors.blue),
          _StatRow(label: 'Expired (cleaned)', value: '12', color: Colors.grey),
        ],
      ),
    );
  }
}

class _DslmEntry extends StatelessWidget {
  final String name;
  final String level;
  final String status;
  final Color color;
  const _DslmEntry({
    required this.name,
    required this.level,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Text(level, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.bold)),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(status, style: GoogleFonts.inter(fontSize: 11)),
      ),
    );
  }
}

// ── Tab: Antivirus ───────────────────────────────────────
class _AntivirusTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Antivirus Engine',
            body: 'Signature-based and heuristic malware detection. '
                'Real-time monitoring and quarantine management.',
          ),
          const SizedBox(height: 16),
          _StatRow(label: 'Signatures', value: '12,847', color: Colors.blue),
          _StatRow(label: 'Files Scanned', value: '4,231', color: Colors.green),
          _StatRow(label: 'Threats Found', value: '0', color: Colors.teal),
          _StatRow(label: 'Quarantined', value: '0', color: Colors.grey),
          _StatRow(label: 'Real-time', value: 'Active', color: Colors.green),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.search, size: 16),
                label: const Text('Quick Scan'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.security, size: 16),
                label: const Text('Full Scan'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.update, size: 16),
                label: const Text('Update Signatures'),
              ),
            ],
          ),
        ],
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

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
    );
  }
}