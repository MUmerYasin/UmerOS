# Umer OS — User Manual

**Version:** 0.1.0-alpha  
**Audience:** All users — no programming knowledge required  
**Last Updated:** 2026

---

## Table of Contents

1. [What is Umer OS?](#1-what-is-umer-os)
2. [Feature Tiers — What Works Today](#2-feature-tiers)
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
✅ TODAY     — Works right now on your computer, no special hardware needed.
🔬 EXPERIMENTAL — Works but may have occasional issues. Good for tech enthusiasts.
🔮 FUTURE    — Planned feature requiring hardware not yet widely available.
❌ BLOCKED   — Cannot be done due to external restrictions (e.g. Apple locks iPhone).
```

**Examples:**
- The AI assistant → ✅ TODAY (works right now)
- Running Windows .exe files → 🔬 EXPERIMENTAL (needs Wine installed)
- Real quantum computer chips → 🔮 FUTURE (hardware doesn't exist yet for consumers)
- iPhone support → ❌ BLOCKED (Apple's hardware prevents it)

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
| Voice commands | `pip install vosk` |
| Post-quantum crypto | `pip install cryptography` (recommended) |
| Quantum simulation | `pip install numpy` (recommended) |

---

## 4. Getting Started

### Step 1 — Download

Download `UmerOS.zip` from the project page and extract it:

```
UmerOS/               ← This is the main folder
  boot/               ← Bootloader files
  kernel/             ← The heart of the OS
  quantum/            ← Quantum computing layer
  ai/                 ← Artificial intelligence
  security/           ← Security system
  fs/                 ← File system
  ui/                 ← User interface
  installer/          ← Installation tools
  docs/               ← You are reading these!
  tests/              ← Quality testing files
```

### Step 2 — Install Python

If you don't have Python 3.10 or higher:
- **Windows:** Download from https://python.org/downloads — check "Add to PATH"
- **macOS:** `brew install python3` or download from python.org
- **Linux:** `sudo apt install python3.12`

### Step 3 — Install Minimum Dependencies

Open your terminal (Command Prompt on Windows, Terminal on macOS/Linux) and type:

```bash
cd UmerOS
pip install numpy cryptography
```

### Step 4 — Verify Everything Works

```bash
python -m unittest discover -s tests -v
```

You should see output ending with:
```
Ran 305 tests in X.Xs
OK
```

If all 305 tests say OK, Umer OS is working perfectly on your computer. ✅

### Step 5 — Try the Boot Simulation

```bash
python -m boot.bootloader
```

You'll see Umer OS "boot" — checking your system, verifying files, and starting the kernel.

---

## 5. The Desktop Environment

Umer OS has a graphical desktop called the **Fluidic Shell**, built with Kivy.

### Starting the Desktop

```bash
pip install kivy           # install graphics library (one time)
python -m ui.gui           # launch the desktop
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
│  [More apps scroll here...]                                         │
│                                                                     │
│                                                                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  🖥 Terminal   📁 Files   📝 Editor   🌐 Browser                   │  ← Taskbar
└─────────────────────────────────────────────────────────────────────┘
```

### How the AI Adapts Your Desktop

Umer OS watches which apps you use most (all stored locally on your device) and:
- **Pins** your most-used apps to the taskbar automatically (after 5+ opens)
- **Suggests workspaces** — groups of apps you use together
- **Orders the app grid** — most-used apps appear first

> **Privacy note:** This learning happens entirely on your device.
> No usage data is ever sent to any server.

### Voice Commands (If Vosk is installed)

You can talk to Umer OS:

| Say | Result |
|---|---|
| "Open terminal" | Opens the Terminal application |
| "Search for budget" | Searches your files for "budget" |
| "Status" | Shows system health |
| "Help" | Lists available commands |
| "Shutdown" | Safely shuts down Umer OS |

---

## 6. Running Applications

### Native Umer OS Apps ✅ TODAY

Apps built for Umer OS run directly. Use the App Launcher to find and open them.

### Linux / Unix Programs ✅ TODAY

Most Linux command-line programs run directly on Umer OS without any changes.

### Windows Programs (.exe) 🔬 EXPERIMENTAL

Umer OS can run many Windows programs using a built-in compatibility layer:

1. **Install Wine** on your computer: `sudo apt install wine64` (Linux)
2. **Run the Windows program:** The compatibility layer handles it automatically
3. **Not all programs work** — games, antivirus, and system tools often have issues

### Android Apps (.apk) 🔬 EXPERIMENTAL

1. **Enable Developer Options** on your Android device
2. **Connect via USB** with ADB enabled
3. **Install ADB:** `sudo apt install adb` (Linux)
4. The Android container then runs the app via your connected device

### Important Compatibility Notes

| App Type | Support | Notes |
|---|---|---|
| Linux ELF programs | ✅ Full | Native execution |
| Python scripts | ✅ Full | Run directly |
| Windows .exe (simple) | 🔬 Good | Many apps work via Wine |
| Windows .exe (DirectX games) | 🔬 Partial | DXVK helps, not perfect |
| Android .apk | 🔬 Limited | Requires ADB + connected device |
| macOS .app | ❌ Blocked | Apple binary format not supported |
| iOS apps | ❌ Blocked | Apple hardware lock |

---

## 7. File Management (QFS)

The **Quantum Filesystem (QFS)** is Umer OS's built-in storage system. It's smarter than
normal filesystems in three ways:

### 1. Smart Compression (20–50% space saving)

QFS automatically compresses every file using a 3-stage pipeline:
1. **LZMA** — standard high-ratio compression (like 7-Zip)
2. **Delta encoding** — stores only the *changes* between similar files
3. **Deduplication** — if you store the same file twice, QFS stores it only once

**Example:** A folder of 100 text documents that would normally take 50 MB might only use
25–40 MB in QFS.

### 2. Content-Addressable Storage

Each file is addressed by a fingerprint (SHA3-256 hash) of its content, not just its name.
This means:
- **No duplicates** — identical files take zero extra space
- **Corruption detection** — any change to a file's content is immediately detectable
- **Instant comparison** — knowing if two files are identical takes microseconds

### 3. Snapshots (Undo for Your Entire File System)

QFS can take an instant "snapshot" of everything:

```
Before snapshot:    report.txt = "Version 1"
Take snapshot  →   snap_id = qfs.snapshot()
After change:      report.txt = "Version 2"
Restore:           qfs.restore_snapshot(snap_id)
Result:            report.txt = "Version 1" again ✓
```

This is like a "time machine" for all your files. Snapshots are taken automatically
before every system update.

### File Search

QFS indexes the content of all your files and lets you search by keyword:
```
Search "quarterly budget" → finds all files containing those words
```

---

## 8. AI Assistant

Umer OS includes a built-in AI assistant that runs entirely on your device.

### Starting the Assistant

```bash
python -c "
from ai.umer_ai import LocalAIAssistant
ai = LocalAIAssistant()
ai.index_files('.')          # index current folder
print(ai.ask('help'))
print(ai.ask('status'))
"
```

### What It Can Do Today ✅

| Command | What Happens |
|---|---|
| `help` | Lists all available commands |
| `status` | Reports system health |
| `optimize` | Triggers resource rebalancing |
| `quantum` | Shows quantum system status |
| `security` | Reports security status |
| `memory` | Shows memory usage |
| `search <term>` | Finds files containing the term |

### What's Coming 🔮

- **Full natural language understanding** — ask anything in plain English
- **Code assistance** — ask it to explain or fix your code
- **System automation** — "remind me to back up every Friday"
- **Smart file organisation** — "organise my downloads by type"

### Privacy Controls

All AI is off by default for data collection. You control what it learns:

```python
from ai.umer_ai import AIGovernance
gov = AIGovernance()

# Opt-in to specific features
gov.grant_consent("usage_patterns")   # let it learn your habits

# See what you've consented to
print(gov.consent_report())

# Erase everything it learned
gov.clear_all()
```

---

## 9. Security & Privacy

### Zero-Trust Principle

In Umer OS, **nothing is trusted by default**. Every app, every file, every message
must prove it has permission before doing anything.

Think of it like a building with ID card readers on every door:
- A visitor can enter the lobby (run basic code)
- But they need a specific badge to enter the server room (access files)
- And a different badge for the network room (send data)

### What This Means for You

1. **Apps can't spy on each other** — each app runs in its own sandbox
2. **Apps can't read your files** without explicit permission
3. **All system messages are digitally signed** — fake messages are rejected
4. **Your boot process is verified** — tampered system files are detected

### Security Levels

| Level | What It Protects |
|---|---|
| **Capability Manager** | Controls what each app can do (file access, network, GPU...) |
| **IPCBus Signing** | Verifies every message between system components |
| **SecureBoot** | Verifies the OS itself hasn't been tampered with |
| **AI Firewall** | Watches for suspicious app behaviour in real time |
| **Post-Quantum Crypto** | Encrypts data with algorithms safe even from quantum computers |

### Privacy Settings

| Setting | Default | How to Change |
|---|---|---|
| AI data collection | OFF | `gov.grant_consent("feature_name")` |
| Cloud sync | OFF | Enable in Settings |
| Telemetry | OFF | Stays off — Umer OS never collects telemetry |
| File indexing | ON (local only) | Disable in Settings |

---

## 10. Installation on Your Device

> ⚠️ **IMPORTANT:** Read the full warning before installing.
> Installation modifies your device. Always back up your data first.

### The Installation Wizard

When you run the installer, it will:

1. **Show the legal warning** — read it carefully
2. **Ask for your consent** — you must type `I AGREE` (exactly, with a space)
3. **Check your system** — verifies Python version, disk space, etc.
4. **Create a backup** — saves your current boot settings before touching anything
5. **Copy the files** — installs Umer OS to the target location
6. **Install the bootloader** — adds Umer OS to your boot menu
7. **Configure first boot** — sets safe defaults (AI opt-out, etc.)

### Running the Installer

```bash
python installer/installer.py
```

Follow the prompts. The key moment:

```
+======================================================================+
|              UMER OS INSTALLATION - LIABILITY WAIVER                 |
+======================================================================+
| ...full warning text...                                              |
|                                                                      |
|  Type  I AGREE  (exactly) to continue, or Ctrl+C to abort.         |
+======================================================================+

Type  I AGREE  (exactly) to continue, or Ctrl+C to abort: I AGREE
```

### After Installation

After rebooting, you'll see a boot menu:
```
┌─────────────────────────────────────────────────────┐
│  Boot Menu                                          │
│                                                     │
│  → Umer OS 0.1.0-alpha                             │
│    Previous Operating System                        │
│                                                     │
│  Press Enter to select, arrows to move              │
└─────────────────────────────────────────────────────┘
```

---

## 11. Uninstalling / Rollback

Changed your mind? No problem. The installer saved everything before making changes.

### Quick Rollback

```bash
python installer/rollback_tools/restore_bootloader.py
python installer/rollback_tools/restore_partitions.py
```

This restores your computer to exactly how it was before Umer OS was installed.

### Manual Uninstall

1. Boot from your original OS
2. Delete the Umer OS partition or installation folder
3. Restore your original bootloader using the backup in `/opt/umer_backup/`

---

## 12. Troubleshooting

### "Tests fail with ImportError"

```bash
# Make sure you're in the UmerOS directory
cd UmerOS
# Install required dependencies
pip install numpy cryptography
# Try again
python -m unittest discover -s tests -v
```

### "Kivy not found / GUI doesn't start"

```bash
pip install kivy
# If that fails on Linux:
sudo apt install python3-kivy
```

### "Wine not found — can't run .exe"

```bash
# Ubuntu/Debian:
sudo apt install wine64
# Fedora:
sudo dnf install wine
# macOS:
brew install wine-stable
```

### "Quantum tests timeout"

This happens if large amounts of random data are fed to the LZMA compressor.
The tests are designed to use small, compressible data. If you're writing custom tests,
use repeated patterns (`b"A" * 2000`) not random bytes (`os.urandom(10000)`).

### "All tests pass but bootloader fails"

```bash
# Check Python version (must be 3.10+)
python --version
# Run bootloader with verbose output
python -m boot.bootloader 2>&1
```

### Common Error Messages

| Error | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: numpy` | NumPy not installed | `pip install numpy` |
| `PermissionError: PID X lacks capability` | App tried to access something not allowed | Normal — zero-trust working correctly |
| `MemoryError: CASStore full` | QFS storage limit reached | Increase `max_store_bytes` or delete old files |
| `FileNotFoundError: ELF not found` | Tried to run non-existent binary | Check the file path |
| `EnvironmentError: Wine not installed` | .exe run attempted without Wine | Install Wine |

---

## 13. Glossary

| Term | Plain English Explanation |
|---|---|
| **AI Firewall** | A security system that watches what apps are doing and blocks suspicious behaviour |
| **Capability** | A specific permission an app must have to do something (e.g. `fs.read` to read files) |
| **CAS (Content-Addressable Storage)** | Storing files by their content fingerprint instead of their name — prevents duplicates |
| **CRYSTALS-Kyber** | A new type of encryption that is safe even against quantum computers |
| **Delta encoding** | Storing only the *differences* between two versions of a file |
| **Entanglement** | A quantum property where two particles are linked — measuring one instantly affects the other |
| **EWMA** | Exponentially-Weighted Moving Average — a smart way to average recent data giving more weight to recent readings |
| **HAL** | Hardware Abstraction Layer — the part of the OS that talks directly to your hardware |
| **HMAC** | A type of digital signature that proves a message hasn't been tampered with |
| **IPC** | Inter-Process Communication — how different programs send messages to each other |
| **Kernel** | The core of the operating system — manages memory, scheduling, and hardware |
| **LZMA** | A powerful compression algorithm (same one used in 7-Zip) |
| **Post-quantum crypto** | Encryption methods that are safe even from future quantum computers |
| **QPU** | Quantum Processing Unit — a computer chip that uses quantum physics (not yet mainstream) |
| **QFS** | Quantum Filesystem — Umer OS's built-in storage system with smart compression |
| **Sandbox** | An isolated environment where an app can run without affecting the rest of the system |
| **SHA3-256** | A one-way mathematical fingerprint function used to verify file integrity |
| **Snapshot** | An instant copy of your filesystem state that can be restored later |
| **Superposition** | A quantum state where something is in multiple states at once until measured |
| **Zero-trust** | A security model where nothing is trusted by default — everything must be verified |
| **ZNE** | Zero-Noise Extrapolation — a technique to reduce errors in quantum measurements |

---

*Umer OS User Manual — v0.1.0-alpha*  
*For technical documentation, see `developer_guide.md` and `architecture.md`*
