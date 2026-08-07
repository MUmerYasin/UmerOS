# Umer OS — User Manual

**Version:** 0.1.0-alpha | **Audience:** All users — no programming knowledge required

---

## Table of Contents

1. [What is Umer OS?](#1-what-is-umer-os)
2. [Feature Tiers](#2-feature-tiers)
3. [System Requirements](#3-system-requirements)
4. [Getting Started in 5 Minutes](#4-getting-started)
5. [The Desktop Environment](#5-desktop)
6. [Running Applications](#6-running-applications)
7. [File Management (QFS)](#7-file-management)
8. [AI Assistant](#8-ai-assistant)
9. [Security & Privacy](#9-security-privacy)
10. [Installation on Your Device](#10-installation)
11. [Uninstalling / Rollback](#11-uninstall)
12. [Troubleshooting](#12-troubleshooting)
13. [Glossary](#13-glossary)

---

## 1. What is Umer OS?

Umer OS is a **new kind of operating system** — the software that runs your computer.
Just like Windows, macOS, or Android, Umer OS controls everything your computer does.

```
┌─────────────────────────────────────────────────────────┐
│                      YOUR COMPUTER                       │
│                                                           │
│   Apps you use (browser, editor, games...)               │
│                        ↕                                 │
│              ┌──────────────────┐                        │
│              │     Umer OS      │  ← controls everything  │
│              └──────────────────┘                        │
│                        ↕                                 │
│         CPU, Memory, Disk, Network, Screen                │
└─────────────────────────────────────────────────────────┘
```

**What makes Umer OS different:**

| Feature | Windows / macOS | Umer OS |
|---|---|---|
| Programming language | C/C++ (very complex) | Python (human-readable) |
| Quantum computing | Not supported | Built-in simulation today; real QPU in future |
| AI built-in | Add-on only | Core part of the system |
| Security model | Trust by default | Zero-trust (everything verified) |
| Storage efficiency | Standard | 20–50% smaller files via smart compression |
| Runs Windows apps | Windows only | Yes (via compatibility layer) |
| Runs Android apps | No | Yes (experimental) |
| Privacy | Mixed | All AI runs on-device — nothing leaves without permission |

> **In plain English:** Umer OS is a computer operating system that uses artificial intelligence
> to run smarter and quantum-inspired mathematics to run safer and more efficiently.

---

## 2. Feature Tiers

Every Umer OS feature has a label so you always know what to expect:

```
✅ TODAY        — Works right now, no special hardware needed.
🔬 EXPERIMENTAL — Works but may have occasional issues.
🔮 FUTURE       — Planned feature requiring hardware not yet widely available.
❌ BLOCKED      — Cannot be done due to external restrictions.
```

| Example | Tier | Why |
|---|---|---|
| The AI assistant | ✅ TODAY | Works right now |
| Running Windows .exe files | 🔬 EXPERIMENTAL | Needs Wine installed |
| Real quantum computer chips | 🔮 FUTURE | Consumer hardware doesn't exist yet |
| iPhone support | ❌ BLOCKED | Apple's hardware prevents it |

---

## 3. System Requirements

### Minimum Requirements

| Component | Minimum | Recommended |
|---|---|---|
| **Operating System** | Any (Windows/macOS/Linux/Android) | Linux or macOS |
| **Python** | 3.10 | 3.12+ |
| **RAM** | 512 MB | 4 GB |
| **Storage** | 200 MB | 2 GB |
| **CPU** | x86_64 or ARM64 | Modern multi-core |
| **Internet** | Not required | Optional (for updates) |
| **GPU** | Not required | Optional (speeds up AI) |

### Optional Software for Extra Features

| Feature | Extra Software Needed |
|---|---|
| Graphical desktop | `pip install kivy` |
| Windows app support | Wine (Linux: `apt install wine64`) |
| Android app support | ADB (`apt install adb`) |
| Post-quantum crypto | `pip install cryptography` (already required) |
| Quantum simulation | `pip install numpy` (already required) |

---

## 4. Getting Started

### Step 1 — Download and Extract

```
UmerOS/               ← Main folder
  boot/               ← Bootloader files
  kernel/             ← The heart of the OS
  quantum/            ← Quantum computing layer
  ai/                 ← Artificial intelligence
  security/           ← Security system
  fs/                 ← File system
  compatibility/      ← Windows/Android app support
  network/            ← Networking
  cloud/              ← Cloud sync stubs
  ui/                 ← Desktop shell
  installer/          ← Installation tools
  packages/           ← Package manager
  docs/               ← You are reading these!
  tests/              ← 431 quality-assurance tests
```

### Step 2 — Install Python

- **Windows:** Download from python.org — check "Add to PATH"
- **macOS:** `brew install python3`
- **Linux:** `sudo apt install python3.12`

### Step 3 — Install Dependencies

```bash
cd UmerOS
pip install numpy cryptography
```

### Step 4 — Verify Everything Works

```bash
python -m unittest discover -s tests -v
```

You should see:
```
Ran 431 tests in X.Xs
OK
```

### Step 5 — Boot Simulation

```bash
python -m boot.bootloader
```

```
  _   _                    ___  ____
 | | | |_ __ ___   ___ _ |   \/ ___|
 | | | | '_ ` _ \ / _ \ '__| |\___ \
 | |_| | | | | | |  __/ |  | | ___) |
  \___/|_| |_| |_|\___|_|  |_||____/

  Umer OS v0.1.0-alpha
✓ Python 3.12.x
✓ Platform: Linux / x86_64
✓ RAM: XXXX MiB
✓ Boot complete
```

---

## 5. The Desktop Environment

Umer OS has a graphical desktop called the **Fluidic Shell**, built with Kivy.

```bash
pip install kivy
python -m ui.gui
```

### Desktop Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⚛ Umer OS    [Search apps...]                          12:34:56   │  ← Top Bar
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  🖥 Terminal    📁 Files     ⚙ Settings    🌐 Browser              │
│                                                                     │
│  📝 Editor     🤖 AI Asst   ⚛ Quantum    🔒 Security              │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  🖥 Terminal   📁 Files   📝 Editor   🌐 Browser                   │  ← Taskbar
└─────────────────────────────────────────────────────────────────────┘
```

### AI-Adaptive Desktop

The AI watches which apps you use most (all stored **locally on your device**) and:
- **Pins** your most-used apps to the taskbar automatically (after 5+ opens)
- **Suggests workspaces** — groups of apps you use together

> **Privacy note:** This learning happens entirely on your device.
> No usage data is ever sent to any server.

---

## 6. Running Applications

| App Type | Support | Notes |
|---|---|---|
| Native Umer OS apps | ✅ Full | Direct execution |
| Linux ELF programs | ✅ Full | Native execution |
| Python scripts | ✅ Full | Run directly |
| Windows .exe (simple) | 🔬 Good | Many apps work via Wine |
| Windows .exe (DirectX games) | 🔬 Partial | Not all games work perfectly |
| Android .apk | 🔬 Limited | Requires ADB + connected device |
| macOS .app | ❌ Blocked | Apple binary format not supported |
| iOS apps | ❌ Blocked | Apple hardware lock |

### Windows Programs (.exe) 🔬

```bash
sudo apt install wine64   # Linux — install Wine first
# Then Umer OS automatically routes .exe launches through Wine
```

### Android Apps (.apk) 🔬

```bash
sudo apt install adb      # install ADB
# Enable Developer Options + USB Debugging on your Android device
# Connect via USB — Umer OS's AndroidContainer handles the rest
```

---

## 7. File Management (QFS)

The **Quantum Filesystem (QFS)** is smarter than normal filesystems in three ways:

### 1. Smart Compression (20–50% space saving)

```
Original file (10,000 bytes)
        │
        ▼
   [ LZMA compress ]  ──►  Compressed (≈4,000 bytes)
        │
        ▼
   [ Store by content fingerprint ]
        │
        ▼
   Duplicate files anywhere on disk → ZERO extra space
```

### 2. Content-Addressable Storage

Each file is addressed by a mathematical fingerprint (SHA3-256) of its content:
- **No duplicates** — identical files take zero extra space
- **Corruption detection** — any change is immediately detectable

### 3. Snapshots (Undo for Your Entire File System)

```
Before snapshot:    report.txt = "Version 1"
Take snapshot  →   snap_id = qfs.snapshot()
After change:      report.txt = "Version 2"
Restore:           qfs.restore_snapshot(snap_id)
Result:            report.txt = "Version 1" again ✓
```

---

## 8. AI Assistant

```bash
python -c "
from ai.umer_ai import LocalAIAssistant
ai = LocalAIAssistant()
ai.index_files('.')
print(ai.ask('help'))
print(ai.ask('status'))
"
```

### Commands Available Today ✅

| Command | What Happens |
|---|---|
| `help` | Lists all available commands |
| `status` | Reports system health |
| `optimize` | Triggers resource rebalancing |
| `quantum` | Shows quantum system status |
| `security` | Reports security status |
| `search <term>` | Finds files containing the term |

### Privacy Controls

```python
from ai.umer_ai import AIGovernance
gov = AIGovernance()
gov.grant_consent("usage_patterns")   # opt-in to a feature
print(gov.consent_report())           # see what you've allowed
gov.clear_all()                       # erase everything it learned
```

---

## 9. Security & Privacy

### Zero-Trust Principle

In Umer OS, **nothing is trusted by default**. Every app, every file, every message
must prove it has permission before doing anything — like ID badges required at every
door in a secure building.

| Security Layer | What It Protects |
|---|---|
| **CapabilityManager** | Controls what each app can do (file access, network, GPU...) |
| **IPCBus HMAC Signing** | Verifies every message between system components |
| **SecureBoot** | Verifies the OS itself hasn't been tampered with |
| **AIFirewall** | Watches for suspicious app behaviour in real time |
| **Post-Quantum Crypto** | Encrypts data safe even from quantum computers |

### Privacy Settings

| Setting | Default | How to Change |
|---|---|---|
| AI data collection | OFF | `gov.grant_consent("feature_name")` |
| Cloud sync | OFF | Requires explicit backend setup |
| Telemetry | OFF | Umer OS never collects telemetry |

---

## 10. Installation on Your Device

> ⚠️ **IMPORTANT:** Installation modifies your device. Always back up your data first.

### What the Installer Does

1. Shows the legal warning
2. Requires you to type `I AGREE` (exactly)
3. Checks your system (Python version, disk space)
4. Creates a backup before touching anything
5. Copies files to the target location
6. Installs the boot entry
7. Configures safe defaults (AI opt-out, etc.)

```bash
python installer/installer.py
```

```
+======================================================================+
|              UMER OS INSTALLATION - LIABILITY WAIVER                 |
+======================================================================+
| ...full warning text...                                              |
+======================================================================+

Type  I AGREE  (exactly) to continue, or Ctrl+C to abort: I AGREE
```

---

## 11. Uninstalling / Rollback

```bash
python installer/rollback_tools/restore_bootloader.py
python installer/rollback_tools/restore_partitions.py
```

This restores your computer to exactly how it was before Umer OS was installed.

---

## 12. Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: numpy` | NumPy not installed | `pip install numpy` |
| `PermissionError: PID X lacks capability` | Normal zero-trust denial | Expected behaviour |
| `MemoryError: CASStore full` | QFS storage limit reached | Increase `max_store_bytes` |
| `EnvironmentError: Wine not installed` | .exe run attempted | `sudo apt install wine64` |
| Tests fail | Wrong Python version | `python --version` (need 3.10+) |

---

## 13. Glossary

| Term | Plain English Explanation |
|---|---|
| **AI Firewall** | Watches app behaviour and blocks suspicious activity |
| **Capability** | A specific permission an app must have to do something |
| **CAS** | Content-Addressable Storage — files stored by fingerprint, not name |
| **CRYSTALS-Kyber** | Encryption safe even against quantum computers |
| **Entanglement** | A quantum property linking two particles' states |
| **HMAC** | A digital signature proving a message wasn't tampered with |
| **IPC** | Inter-Process Communication — programs sending messages |
| **Kernel** | The core of the OS — manages memory, scheduling, hardware |
| **LZMA** | A compression algorithm (same one used in 7-Zip) |
| **QFS** | Quantum Filesystem — Umer OS's storage system |
| **Sandbox** | An isolated space where an app runs without affecting others |
| **Superposition** | A quantum state existing in multiple values at once |
| **Zero-trust** | Nothing trusted by default — everything must be verified |

---

*Umer OS User Manual — v0.1.0-alpha | 431 tests passing*
