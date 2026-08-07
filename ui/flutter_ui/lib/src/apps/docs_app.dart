import 'package:flutter/material.dart';

// ─── Documentation Browser App ───────────────────────────────────────────────

class DocsApp extends StatefulWidget {
  const DocsApp({super.key});

  @override
  State<DocsApp> createState() => _DocsAppState();
}

class _DocsAppState extends State<DocsApp> {
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';
  String _selectedSection = 'getting-started';
  String _selectedPage = 'installation';
  bool _sidebarExpanded = true;
  bool _tocExpanded = true;

  // Documentation tree structure
  final Map<String, Map<String, dynamic>> _toc = {
    'getting-started': {
      'title': 'Getting Started',
      'icon': Icons.rocket_launch,
      'expanded': true,
      'pages': {
        'installation': 'Installation',
        'quick-start': 'Quick Start',
        'system-requirements': 'System Requirements',
      },
    },
    'user-guide': {
      'title': 'User Guide',
      'icon': Icons.person,
      'expanded': false,
      'pages': {
        'desktop': 'Desktop Environment',
        'file-manager': 'File Manager',
        'terminal': 'Terminal',
        'settings': 'System Settings',
      },
    },
    'developer-guide': {
      'title': 'Developer Guide',
      'icon': Icons.code,
      'expanded': false,
      'pages': {
        'architecture': 'Architecture',
        'apis': 'APIs Overview',
        'sdk': 'SDK',
        'plugin-dev': 'Plugin Development',
      },
    },
    'quantum-computing': {
      'title': 'Quantum Computing',
      'icon': Icons.science,
      'expanded': false,
      'pages': {
        'qc-intro': 'Introduction',
        'gates': 'Quantum Gates',
        'circuits': 'Quantum Circuits',
        'algorithms': 'Algorithms',
      },
    },
    'security': {
      'title': 'Security',
      'icon': Icons.shield,
      'expanded': false,
      'pages': {
        'overview': 'Overview',
        'encryption': 'Encryption',
        'firewall': 'Firewall',
        'sandboxing': 'Sandboxing',
      },
    },
    'api-reference': {
      'title': 'API Reference',
      'icon': Icons.api,
      'expanded': false,
      'pages': {
        'kernel-api': 'Kernel API',
        'network-api': 'Network API',
        'ai-api': 'AI API',
      },
    },
  };

  // Page content
  final Map<String, Map<String, dynamic>> _pageContent = {
    'installation': {
      'title': 'Installation',
      'content': '''
# Installation

## Prerequisites

Before installing UmerOS, ensure you have:
- A 64-bit x86 or ARM processor
- At least 4 GB of RAM (8 GB recommended)
- 20 GB of free disk space
- Active internet connection

## Download Options

### ISO Image
Download the latest UmerOS ISO from the official repository:

```bash
wget https://releases.umeros.org/latest/umeros-2.0-amd64.iso
```

### Write to USB
```bash
sudo dd if=umeros-2.0-amd64.iso of=/dev/sdX bs=4M status=progress
```

### Boot and Install
1. Insert the USB drive
2. Restart and enter BIOS (F2/F12)
3. Select USB boot device
4. Follow the installer wizard

## Network Install
For minimal installations over the network:
```bash
netboot install --mirror=https://repo.umeros.org
```
''',
      'sections': ['Prerequisites', 'Download Options', 'Network Install'],
    },
    'quick-start': {
      'title': 'Quick Start',
      'content': '''
# Quick Start Guide

## First Boot
After installation, UmerOS will guide you through:
1. Language selection
2. User account creation
3. Network configuration
4. Desktop theme selection

## Desktop Overview
The UmerOS desktop includes:
- **Top Panel**: App menu, system tray, clock
- **Dock**: Favorite and running applications
- **Desktop**: Wallpaper and widgets

## Essential Shortcuts
| Shortcut | Action |
|----------|--------|
| Super + Space | Application launcher |
| Super + T | Open terminal |
| Super + D | Show desktop |
| Alt + Tab | Switch windows |
| Ctrl + Alt + Del | System monitor |
''',
      'sections': ['First Boot', 'Desktop Overview', 'Essential Shortcuts'],
    },
    'system-requirements': {
      'title': 'System Requirements',
      'content': '''
# System Requirements

## Minimum Requirements
- **CPU**: 64-bit dual-core processor (2 GHz)
- **RAM**: 4 GB
- **Storage**: 20 GB
- **GPU**: OpenGL 3.3 compatible
- **Network**: Ethernet or Wi-Fi adapter

## Recommended
- **CPU**: 64-bit quad-core processor (3 GHz+)
- **RAM**: 8 GB or more
- **Storage**: 50 GB SSD
- **GPU**: Vulkan 1.2 compatible
- **Network**: Gigabit Ethernet

## Supported Architectures
- x86_64 (amd64)
- AArch64 (ARM64)
- RISC-V (experimental)

## Virtualization
UmerOS runs great in VMs:
- VirtualBox 7.0+
- VMware Workstation 17+
- QEMU/KVM
- Hyper-V (Windows)
''',
      'sections': ['Minimum Requirements', 'Recommended', 'Supported Architectures', 'Virtualization'],
    },
    'desktop': {
      'title': 'Desktop Environment',
      'content': '''
# Desktop Environment

## Overview
UmerOS uses the UmerDE, a modern Linux desktop environment built with:
- Wayland display server
- GTK4/Libadwaita applications
- Flutter-based system components

## Panels and Docks

### Top Panel
- **Left**: Application menu
- **Center**: Window title / Clock
- **Right**: System tray (network, volume, battery, user)

### Application Dock
- Pin apps by right-clicking → "Add to Dock"
- Drag to reorder
- Running apps show an indicator dot

## Virtual Workspaces
Switch between workspaces:
- Super + ←/→ for horizontal navigation
- Super + 1-9 to jump directly
- Drag windows between workspaces

## Widgets
Add widgets to your desktop:
1. Right-click desktop → "Add Widget"
2. Choose from: Clock, Weather, System Monitor, Notes
3. Drag to position
''',
      'sections': ['Overview', 'Panels and Docks', 'Virtual Workspaces', 'Widgets'],
    },
    'file-manager': {
      'title': 'File Manager',
      'content': '''
# File Manager

## Interface
The UmerOS file manager features:
- Dual-pane view (press F3)
- Path bar with breadcrumb navigation
- Preview panel (press F11)
- Tabs for multiple locations

## Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Ctrl+N | New folder |
| Ctrl+Shift+N | New file |
| Ctrl+C/X/V | Copy/Cut/Paste |
| Ctrl+H | Show hidden files |
| F2 | Rename |
| Delete | Move to trash |

## Network Locations
Connect to network shares:
1. File → Connect to Server
2. Enter smb://, nfs://, or ssh:// address
3. Bookmark for quick access

## Search
- Press Ctrl+F to search
- Supports regex patterns
- Filter by type, date, size
''',
      'sections': ['Interface', 'Keyboard Shortcuts', 'Network Locations', 'Search'],
    },
    'terminal': {
      'title': 'Terminal',
      'content': '''
# Terminal Emulator

## Features
- GPU-accelerated rendering
- Split panes (horizontal/vertical)
- Tabs and profiles
- Built-in tmux integration

## Configuration
Edit ~/.config/umerterm/config.toml:

```toml
[font]
family = "JetBrains Mono"
size = 12

[colors]
scheme = "dracula"

[behavior]
scrollback_lines = 10000
copy_on_select = true
```

## Tips
- Right-click for context menu
- Hold Ctrl to select text
- Ctrl+Shift+C/V for copy/paste
- Ctrl+Shift+F to find in scrollback
''',
      'sections': ['Features', 'Configuration', 'Tips'],
    },
    'settings': {
      'title': 'System Settings',
      'content': '''
# System Settings

## Categories

### Appearance
- Theme: Light / Dark / Auto
- Accent color selection
- Font scaling
- Night light (blue light filter)

### Display
- Resolution and scaling
- Multiple monitor setup
- Refresh rate
- HDR support

### Sound
- Output/Input device selection
- Volume levels per-app
- Sound effects
- Spatial audio

### Network
- Wi-Fi management
- VPN configuration
- Proxy settings
- Firewall rules

### Privacy
- Location services
- Usage statistics
- App permissions
- Screen lock
''',
      'sections': ['Categories'],
    },
    'architecture': {
      'title': 'Architecture',
      'content': '''
# Architecture Overview

## System Layers
```
┌─────────────────────────────┐
│     User Applications       │
├─────────────────────────────┤
│   Desktop Environment       │
│   (Flutter / GTK4)         │
├─────────────────────────────┤
│   System Services           │
│   (DBus / Systemd)         │
├─────────────────────────────┤
│   UmerOS Kernel Module      │
│   (Linux 6.x + custom)     │
├─────────────────────────────┤
│   Hardware Layer            │
└─────────────────────────────┘
```

## Core Components
- **UmerFS**: Custom overlay filesystem
- **UmerNet**: Network management daemon
- **UmerAI**: On-device AI inference engine
- **UmerBox**: Application sandboxing
''',
      'sections': ['System Layers', 'Core Components'],
    },
    'apis': {
      'title': 'APIs Overview',
      'content': '''
# APIs Overview

UmerOS exposes three main API families:

## Kernel API
Low-level system calls and interfaces:
- Process management
- Filesystem operations
- Device control
- IPC mechanisms

## Network API
Network service interfaces:
- Connection management
- DNS resolution
- Service discovery
- Traffic shaping

## AI API
Machine learning integration:
- Model inference
- Speech recognition
- Image processing
- Natural language

## Authentication
All APIs use OAuth2/OIDC tokens:
```bash
umer-auth token --scope=kernel:read,network:write
```
''',
      'sections': ['Kernel API', 'Network API', 'AI API', 'Authentication'],
    },
    'sdk': {
      'title': 'SDK',
      'content': '''
# UmerOS SDK

## Installation
```bash
curl -sSL https://sdk.umeros.org/install.sh | sh
```

## Project Structure
```
my-app/
├── src/
│   ├── main.dart
│   └── components/
├── pubspec.yaml
├── umeros.yaml
└── test/
```

## Building
```bash
umer build --release
umer package --sign-key=mykey
```

## Testing
```bash
umer test --unit
umer test --integration
umer test --ui --device=emulator
```
''',
      'sections': ['Installation', 'Project Structure', 'Building', 'Testing'],
    },
    'plugin-dev': {
      'title': 'Plugin Development',
      'content': '''
# Plugin Development

## Plugin Structure
```dart
class MyPlugin extends UmerPlugin {
  @override
  String get id => 'com.example.myplugin';

  @override
  void onActivate(UmerContext ctx) {
    // Register services
  }
}
```

## Lifecycle
1. **Discovery**: Plugin is scanned from /usr/lib/umerplugins
2. **Load**: Plugin dependencies are resolved
3. **Init**: onActivate is called
4. **Ready**: Plugin is available to applications
5. **Unload**: Cleanup on shutdown

## Publishing
```bash
umer plugin publish --repo=plugins.umeros.org
```
''',
      'sections': ['Plugin Structure', 'Lifecycle', 'Publishing'],
    },
    'qc-intro': {
      'title': 'Introduction to Quantum Computing',
      'content': '''
# Quantum Computing in UmerOS

## Overview
UmerOS includes a built-in quantum computing simulator and API for developing quantum applications.

## Key Concepts

### Qubits
Classical bits are 0 or 1. Qubits can be in superposition:
|ψ⟩ = α|0⟩ + β|1⟩

where |α|² + |β|² = 1

### Superposition
A qubit exists in both states simultaneously until measured.

### Entanglement
Two qubits can be correlated such that measuring one instantly determines the other.

## Getting Started
```dart
import 'package:umer_quantum/umer_quantum.dart';

void main() {
  final qubit = QuantumBit();
  qubit.hadamard(); // Put in superposition
  final result = qubit.measure(); // 0 or 50/50
}
```
''',
      'sections': ['Overview', 'Key Concepts', 'Getting Started'],
    },
    'gates': {
      'title': 'Quantum Gates',
      'content': '''
# Quantum Gates

## Single-Qubit Gates

### Hadamard (H)
Creates superposition from |0⟩ or |1⟩:
```
H|0⟩ = (|0⟩ + |1⟩) / √2
H|1⟩ = (|0⟩ - |1⟩) / √2
```

### Pauli-X (NOT)
Flips |0⟩ to |1⟩ and vice versa.

### Pauli-Z
Phase flip: |1⟩ → -|1⟩

### T Gate
π/8 phase rotation.

## Two-Qubit Gates

### CNOT
Controlled-NOT: flips target if control is |1⟩.

### SWAP
Exchanges two qubits.

### CZ
Controlled-Z: applies Z to target if control is |1⟩.
''',
      'sections': ['Single-Qubit Gates', 'Two-Qubit Gates'],
    },
    'circuits': {
      'title': 'Quantum Circuits',
      'content': '''
# Quantum Circuits

## Circuit Model
Quantum computation proceeds by applying gates to qubits in sequence.

## Example: Bell State
```dart
final q0 = QuantumBit(); // |0⟩
final q1 = QuantumBit(); // |0⟩

circuit.hadamard(q0);
circuit.cnot(q0, q1);

// Now q0 and q1 are entangled
// Measuring one determines the other
```

## Circuit Visualization
```
q0: ─── H ─── ● ───
              │
q1: ───────── ⊕ ───
```

## Depth and Width
- **Depth**: Number of gate layers
- **Width**: Number of qubits used

Minimize depth for faster execution on real hardware.
''',
      'sections': ['Circuit Model', 'Example: Bell State', 'Circuit Visualization', 'Depth and Width'],
    },
    'algorithms': {
      'title': 'Quantum Algorithms',
      'content': '''
# Quantum Algorithms

## Deutsch-Jozsa
Determines if a function is constant or balanced in one query.

## Grover's Search
Searches an unsorted database in O(√N) time.

## Shor's Factorization
Factors large integers exponentially faster than classical methods.

## Quantum Teleportation
Transfers quantum state using entanglement and classical communication.

## Variational Quantum Eigensolver (VQE)
Hybrid quantum-classical algorithm for finding ground state energies.

## Applications in UmerOS
- Cryptography analysis
- Optimization problems
- Machine learning acceleration
- Drug discovery simulation
''',
      'sections': ['Deutsch-Jozsa', 'Grover\'s Search', 'Shor\'s Factorization', 'Quantum Teleportation', 'VQE', 'Applications'],
    },
    'overview': {
      'title': 'Security Overview',
      'content': '''
# Security Overview

## Security Model
UmerOS implements defense in depth:

1. **Kernel hardening**: SELinux, seccomp, ASLR
2. **Application sandboxing**: Each app runs in its own namespace
3. **Encrypted storage**: LUKS full-disk encryption
4. **Secure boot**: Verified boot chain with TPM
5. **Automatic updates**: Critical patches delivered within 24h

## Threat Categories
- Local privilege escalation
- Network attacks
- Supply chain compromise
- Social engineering
- Physical access

## Reporting Vulnerabilities
Email security@umeros.org with PGP encryption.
Bug bounty: \$100 - \$10,000 based on severity.
''',
      'sections': ['Security Model', 'Threat Categories', 'Reporting Vulnerabilities'],
    },
    'encryption': {
      'title': 'Encryption',
      'content': '''
# Encryption

## Full Disk Encryption
LUKS2 with AES-256-XTS:
```bash
umer-crypto encrypt /dev/sda2 --cipher=aes-256-xts-plain64
```

## File-Level Encryption
```bash
umer-crypto encrypt-file secret.txt
# Creates secret.txt.umer
```

## Key Management
- Keys stored in TPM 2.0 chip
- Hardware security module (HSM) support
- Key escrow for enterprise deployments

## TLS/SSL
All network connections use TLS 1.3 by default.
Certificate transparency logging enabled.
''',
      'sections': ['Full Disk Encryption', 'File-Level Encryption', 'Key Management', 'TLS/SSL'],
    },
    'firewall': {
      'title': 'Firewall',
      'content': '''
# Firewall

## Default Policy
- Incoming: DENY all
- Outgoing: ALLOW all
- Forward: DENY all

## Configuration
```bash
# Allow SSH
umer-firewall allow port 22 tcp

# Block IP range
umer-firewall deny 10.0.0.0/8

# Rate limiting
umer-firewall rate-limit port 80 tcp --max=100/s
```

## Zones
- **Public**: Maximum restrictions
- **Internal**: Allows local network
- **Trusted**: Full access
- **DMZ**: Isolated services

## Monitoring
```bash
umer-firewall log --live
umer-firewall stats --top-10
```
''',
      'sections': ['Default Policy', 'Configuration', 'Zones', 'Monitoring'],
    },
    'sandboxing': {
      'title': 'Sandboxing',
      'content': '''
# Application Sandboxing

## UmerBox
Every application runs in an isolated sandbox:
- Separate user namespace
- Read-only system files
- Limited network access
- Controlled device access

## Permissions
Apps request permissions via manifest:
```yaml
permissions:
  - network:outbound
  - filesystem:~/Documents
  - camera
  - microphone
```

## Confinement Profiles
- **Strict**: No system access (default)
- **Moderate**: Read-only system access
- **Unconfined**: Full access (requires approval)

## Auditing
```bash
umer-box audit --app=com.example.myapp
umer-box logs --app=com.example.myapp --tail
```
''',
      'sections': ['UmerBox', 'Permissions', 'Confinement Profiles', 'Auditing'],
    },
    'kernel-api': {
      'title': 'Kernel API',
      'content': '''
# Kernel API

## System Calls
Extended Linux syscalls for UmerOS features:

```c
// Process management
int umer_clone(int flags, void *stack);
int umer_wait(int pid, int *status, int options);

// Filesystem
int umer_overlay_mount(const char *upper, const char *lower, const char *merged);
int umer_snapshot_create(const char *path);

// Security
int umer_sandbox_enter(pid_t pid, const struct umer_sandbox_config *config);
int umer_caps_set(pid_t pid, const cap_t caps);
```

## DBus Interfaces
```xml
<interface name="org.umeros.Kernel">
  <method name="GetSystemInfo">
    <arg direction="out" type="s"/>
  </method>
  <method name="ListProcesses">
    <arg direction="out" type="a(ssu)"/>
  </method>
</interface>
```
''',
      'sections': ['System Calls', 'DBus Interfaces'],
    },
    'network-api': {
      'title': 'Network API',
      'content': '''
# Network API

## Connection Management
```dart
final conn = await UmerNetwork.connect(
  host: 'example.com',
  port: 443,
  protocol: Protocol.tls,
);
```

## Service Discovery
```dart
final services = await UmerNetwork.discover(
  type: '_http._tcp',
  timeout: Duration(seconds: 5),
);
```

## Traffic Shaping
```bash
umer-net shape --interface=wlan0 --limit=10mbit --burst=1mbit
```

## DNS
```dart
final records = await UmerDNS.resolve(
  'example.com',
  type: RecordType.A,
);
```
''',
      'sections': ['Connection Management', 'Service Discovery', 'Traffic Shaping', 'DNS'],
    },
    'ai-api': {
      'title': 'AI API',
      'content': '''
# AI API

## On-Device Inference
```dart
final model = await UmerAI.loadModel('sentiment-v2');
final result = await model.infer('This is great!');
print(result.label); // "positive"
print(result.confidence); // 0.95
```

## Speech Recognition
```dart
final stt = UmerSpeechToText();
final text = await stt.transcribe(audioFile: 'recording.wav');
```

## Image Processing
```dart
final vision = UmerVision();
final objects = await vision.detectObjects(image: 'photo.jpg');
final text = await vision.extractText(image: 'screenshot.png');
```

## Model Hub
Download community models:
```bash
umer-ai hub list
umer-ai hub pull --model=nlp-sentiment-v2
umer-ai hub push --model=my-custom-model
```
''',
      'sections': ['On-Device Inference', 'Speech Recognition', 'Image Processing', 'Model Hub'],
    },
  };

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  String get _currentPageTitle {
    for (final section in _toc.values) {
      final pages = section['pages'] as Map<String, String>;
      if (pages.containsKey(_selectedPage)) {
        return pages[_selectedPage]!;
      }
    }
    return '';
  }

  List<String> get _currentPageSections {
    final content = _pageContent[_selectedPage];
    if (content == null) return [];
    return (content['sections'] as List<String>?) ?? [];
  }

  String get _breadcrumb {
    String sectionTitle = '';
    for (final entry in _toc.entries) {
      final pages = entry.value['pages'] as Map<String, String>;
      if (pages.containsKey(_selectedPage)) {
        sectionTitle = entry.value['title'] as String;
        break;
      }
    }
    return 'Docs / $sectionTitle / $_currentPageTitle';
  }

  void _navigateTo(String section, String page) {
    setState(() {
      _selectedSection = section;
      _selectedPage = page;
      // Expand the section
      (_toc[section]!['expanded'] as ValueNotifier<bool>).value = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final screenWidth = MediaQuery.of(context).size.width;
    final isCompact = screenWidth < 800;

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: Column(
        children: [
          _buildTopBar(context, isDark),
          Expanded(
            child: Row(
              children: [
                // Left sidebar
                if (!isCompact || _sidebarExpanded)
                  _buildLeftSidebar(context, isDark, isCompact),
                // Content
                Expanded(
                  child: _buildContent(context, isDark),
                ),
                // Right TOC
                if (!isCompact && _tocExpanded)
                  _buildRightToc(context, isDark),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopBar(BuildContext context, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey[850] : Theme.of(context).primaryColor,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          // Sidebar toggle
          IconButton(
            icon: Icon(
              _sidebarExpanded ? Icons.menu_open : Icons.menu,
              color: Colors.white,
            ),
            onPressed: () => setState(() => _sidebarExpanded = !_sidebarExpanded),
            tooltip: 'Toggle sidebar',
          ),
          const SizedBox(width: 8),
          // Logo
          const Text(
            '📚 UmerOS Docs',
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(width: 16),
          // Search bar
          Expanded(
            child: Container(
              height: 36,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: TextField(
                controller: _searchController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Search documentation...',
                  hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.6)),
                  prefixIcon: Icon(Icons.search, color: Colors.white.withValues(alpha: 0.6), size: 20),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
                onChanged: (value) {
                  setState(() => _searchQuery = value.toLowerCase());
                },
              ),
            ),
          ),
          const SizedBox(width: 16),
          // Version badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Text(
              'v2.0',
              style: TextStyle(color: Colors.white, fontSize: 12),
            ),
          ),
          const SizedBox(width: 8),
          // TOC toggle
          IconButton(
            icon: Icon(
              _tocExpanded ? Icons.format_list_numbered : Icons.toc,
              color: Colors.white,
            ),
            onPressed: () => setState(() => _tocExpanded = !_tocExpanded),
            tooltip: 'Toggle table of contents',
          ),
        ],
      ),
    );
  }

  Widget _buildLeftSidebar(BuildContext context, bool isDark, bool isCompact) {
    final filteredToc = _searchQuery.isEmpty
        ? _toc
        : Map.fromEntries(
            _toc.entries.where((e) {
              final title = (e.value['title'] as String).toLowerCase();
              final pages = e.value['pages'] as Map<String, String>;
              return title.contains(_searchQuery) ||
                  pages.values.any((p) => p.toLowerCase().contains(_searchQuery));
            }),
          );

    return Container(
      width: isCompact ? 280 : 260,
      decoration: BoxDecoration(
        color: isDark ? Colors.grey[900] : Colors.grey[50],
        border: Border(
          right: BorderSide(color: isDark ? Colors.grey[800]! : Colors.grey[200]!),
        ),
      ),
      child: Column(
        children: [
          // Breadcrumb
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isDark ? Colors.grey[850] : Colors.grey[100],
              border: Border(
                bottom: BorderSide(color: isDark ? Colors.grey[800]! : Colors.grey[200]!),
              ),
            ),
            child: Text(
              _breadcrumb,
              style: TextStyle(
                fontSize: 12,
                color: isDark ? Colors.grey[400] : Colors.grey[600],
              ),
            ),
          ),

          // TOC tree
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: filteredToc.length,
              itemBuilder: (context, index) {
                final entry = filteredToc.entries.elementAt(index);
                return _buildTocSection(entry.key, entry.value, isDark);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTocSection(String sectionKey, Map<String, dynamic> section, bool isDark) {
    final title = section['title'] as String;
    final icon = section['icon'] as IconData;
    final pages = section['pages'] as Map<String, String>;
    final expandedNotifier = section['expanded'] as ValueNotifier<bool>;

    return ValueListenableBuilder<bool>(
      valueListenable: expandedNotifier,
      builder: (context, expanded, _) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ListTile(
              dense: true,
              leading: Icon(icon, size: 20, color: Theme.of(context).primaryColor),
              title: Text(
                title,
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                  color: isDark ? Colors.grey[200] : Colors.grey[800],
                ),
              ),
              trailing: Icon(
                expanded ? Icons.expand_less : Icons.expand_more,
                size: 20,
              ),
              onTap: () {
                setState(() {
                  (_toc[sectionKey]!['expanded'] as ValueNotifier<bool>).value = !expanded;
                });
              },
            ),
            if (expanded)
              ...pages.entries.map((page) {
                final isSelected = _selectedPage == page.key;
                return Padding(
                  padding: const EdgeInsets.only(left: 16),
                  child: ListTile(
                    dense: true,
                    selected: isSelected,
                    selectedTileColor: Theme.of(context).primaryColor.withValues(alpha: 0.1),
                    title: Text(
                      page.value,
                      style: TextStyle(
                        fontSize: 13,
                        color: isSelected
                            ? Theme.of(context).primaryColor
                            : (isDark ? Colors.grey[400] : Colors.grey[600]),
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                    onTap: () => _navigateTo(sectionKey, page.key),
                  ),
                );
              }),
          ],
        );
      },
    );
  }

  Widget _buildContent(BuildContext context, bool isDark) {
    final content = _pageContent[_selectedPage];
    if (content == null) {
      return const Center(child: Text('Select a page from the sidebar'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Page title
          Text(
            content['title']!,
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 16),
          // Edit on GitHub button
          Align(
            alignment: Alignment.centerRight,
            child: OutlinedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.edit, size: 16),
              label: const Text('Edit on GitHub'),
              style: OutlinedButton.styleFrom(
                foregroundColor: isDark ? Colors.grey[400] : Colors.grey[600],
              ),
            ),
          ),
          const Divider(height: 32),
          // Content body
          _renderMarkdown(content['content']!, isDark),
          const SizedBox(height: 48),
          // Navigation
          _buildNavigation(context, isDark),
        ],
      ),
    );
  }

  Widget _renderMarkdown(String text, bool isDark) {
    final lines = text.split('\n');
    final widgets = <Widget>[];
    bool inCodeBlock = false;
    String codeBuffer = '';

    for (final line in lines) {
      if (line.trimRight().endsWith('```') && !inCodeBlock) {
        inCodeBlock = true;
        codeBuffer = '';
        continue;
      }

      if (line.trim() == '```' && inCodeBlock) {
        inCodeBlock = false;
        widgets.add(_buildCodeBlock(codeBuffer.trimRight(), isDark));
        widgets.add(const SizedBox(height: 16));
        codeBuffer = '';
        continue;
      }

      if (inCodeBlock) {
        codeBuffer += '$line\n';
        continue;
      }

      // Headers
      if (line.startsWith('# ')) {
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 24, bottom: 8),
          child: Text(
            line.substring(2),
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
        ));
        continue;
      }
      if (line.startsWith('## ')) {
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 20, bottom: 8),
          child: Text(
            line.substring(3),
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
        ));
        continue;
      }
      if (line.startsWith('### ')) {
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 16, bottom: 6),
          child: Text(
            line.substring(4),
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
        ));
        continue;
      }

      // Table
      if (line.startsWith('|') && line.endsWith('|')) {
        // Collect table rows
        continue;
      }

      // List items
      if (line.trimLeft().startsWith('- ')) {
        final content = line.trimLeft().substring(2);
        widgets.add(Padding(
          padding: const EdgeInsets.only(left: 16, top: 4, bottom: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('• ', style: TextStyle(fontWeight: FontWeight.bold)),
              Expanded(child: _buildInlineText(content, isDark)),
            ],
          ),
        ));
        continue;
      }

      // Numbered list
      final numberedMatch = RegExp(r'^(\d+)\.\s(.+)').firstMatch(line);
      if (numberedMatch != null) {
        final num = numberedMatch.group(1);
        final content = numberedMatch.group(2)!;
        widgets.add(Padding(
          padding: const EdgeInsets.only(left: 16, top: 4, bottom: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('$num. ', style: const TextStyle(fontWeight: FontWeight.bold)),
              Expanded(child: _buildInlineText(content, isDark)),
            ],
          ),
        ));
        continue;
      }

      // Empty line
      if (line.trim().isEmpty) {
        widgets.add(const SizedBox(height: 8));
        continue;
      }

      // Regular paragraph
      widgets.add(Padding(
        padding: const EdgeInsets.only(top: 4, bottom: 4),
        child: _buildInlineText(line, isDark),
      ));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: widgets,
    );
  }

  Widget _buildInlineText(String text, bool isDark) {
    // Handle inline code and bold
    final spans = <TextSpan>[];
    final regex = RegExp(r'`([^`]+)`|\*\*([^*]+)\*\*');
    int lastEnd = 0;

    for (final match in regex.allMatches(text)) {
      if (match.start > lastEnd) {
        spans.add(TextSpan(text: text.substring(lastEnd, match.start)));
      }

      if (match.group(1) != null) {
        // Inline code
        spans.add(TextSpan(
          text: match.group(1),
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 13,
            backgroundColor: isDark ? Colors.grey[800] : Colors.grey[200],
            color: isDark ? Colors.orange[300] : Colors.red[700],
          ),
        ));
      } else if (match.group(2) != null) {
        // Bold
        spans.add(TextSpan(
          text: match.group(2),
          style: const TextStyle(fontWeight: FontWeight.bold),
        ));
      }

      lastEnd = match.end;
    }

    if (lastEnd < text.length) {
      spans.add(TextSpan(text: text.substring(lastEnd)));
    }

    if (spans.isEmpty) {
      return Text(text, style: Theme.of(context).textTheme.bodyMedium);
    }

    return RichText(
      text: TextSpan(
        style: Theme.of(context).textTheme.bodyMedium,
        children: spans,
      ),
    );
  }

  Widget _buildCodeBlock(String code, bool isDark) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey[900] : Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: isDark ? Colors.grey[700]! : Colors.grey[300]!),
      ),
      child: SelectableText(
        code,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 13,
          color: isDark ? Colors.green[300] : Colors.green[800],
        ),
      ),
    );
  }

  Widget _buildRightToc(BuildContext context, bool isDark) {
    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: isDark ? Colors.grey[900] : Colors.grey[50],
        border: Border(
          left: BorderSide(color: isDark ? Colors.grey[800]! : Colors.grey[200]!),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isDark ? Colors.grey[850] : Colors.grey[100],
              border: Border(
                bottom: BorderSide(color: isDark ? Colors.grey[800]! : Colors.grey[200]!),
              ),
            ),
            child: Text(
              'On this page',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 13,
                color: isDark ? Colors.grey[300] : Colors.grey[700],
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: _currentPageSections.length,
              itemBuilder: (context, index) {
                final section = _currentPageSections[index];
                return ListTile(
                  dense: true,
                  title: Text(
                    section,
                    style: TextStyle(
                      fontSize: 12,
                      color: isDark ? Colors.grey[400] : Colors.grey[600],
                    ),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12),
                  onTap: () {
                    // Scroll to section
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavigation(BuildContext context, bool isDark) {
    // Find prev/next pages
    String? prevPage;
    String? nextPage;
    String? prevTitle;
    String? nextTitle;

    bool foundCurrent = false;
    for (final section in _toc.entries) {
      final pages = section.value['pages'] as Map<String, String>;
      for (final page in pages.entries) {
        if (foundCurrent && nextPage == null) {
          nextPage = page.key;
          nextTitle = page.value;
          break;
        }
        if (page.key == _selectedPage) {
          foundCurrent = true;
        }
        if (!foundCurrent) {
          prevPage = page.key;
          prevTitle = page.value;
        }
      }
      if (nextPage != null) break;
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        if (prevPage != null)
          TextButton.icon(
            onPressed: () => _navigateTo(_selectedSection, prevPage!),
            icon: const Icon(Icons.arrow_back, size: 16),
            label: Text(prevTitle!),
          )
        else
          const SizedBox(),
        if (nextPage != null)
          TextButton.icon(
            onPressed: () => _navigateTo(_selectedSection, nextPage!),
            label: Text(nextTitle!),
            icon: const Icon(Icons.arrow_forward, size: 16),
          )
        else
          const SizedBox(),
      ],
    );
  }
}
