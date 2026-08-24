# UmerOS `/tmp` — Temporary Filesystem Hierarchy

---

## 1. Overview & Purpose

The `/tmp` directory contains **temporary files required by running programs**.

### Key Principles from :
1. **Transient Storage:** Programs must **not assume that files or directories in `/tmp` are preserved** between program invocations or system reboots.
2. **Boot / Shutdown Cleanup:** Contents of `/tmp` are typically cleared during the boot or shutdown process, or by automated periodic reapers (`tmpwatch` / `systemd-tmpfiles`).
3. **Difference from `/var/tmp`:**
   - `/tmp`: Short-lived temporary files and sockets, cleared on boot.
   - `/var/tmp`: Preserved across system reboots for multi-session temporary files.
4. **Standard Socket Skeletons (Mode 1777):**
   - `/tmp/.X11-unix` — X11 display communication sockets
   - `/tmp/.ICE-unix` — Inter-Client Exchange sockets
   - `/tmp/.font-unix` — Font server sockets
   - `/tmp/.rpc-unix` — RPC sockets
   - `/tmp/.Test-unix` — Testing & mock sockets
   - `/tmp/user/<uid>` — Isolated per-user runtime temporary directories (Mode 0700)
5. **Security & Sticky Bit (+t / Mode 1777):**
   - `/tmp` has permissions `1777` (`drwxrwxrwt`).
   - The **Sticky Bit** ensures that only the file owner, directory owner (root), or privileged processes can delete or rename files in `/tmp`.

---

## 2. Architecture & Modules

| Module | Description |
|---|---|
| `fhs.py` | protected socket directories, validation of `/tmp` root and permissions. |
| `hierarchy.py` | Directory provisioning, standard socket skeleton bootstrap (`.X11-unix`, etc.), user runtime dirs (`/tmp/user/<uid>`). |
| `secure_io.py` | Race-free atomic temporary file & directory creation (`O_CREAT | O_EXCL`, `0600`/`0700` modes), `mktemp` utility, context managers (`SecureTempFile`, `SecureTempDir`). |
| `lockfile.py` | Transient process lockfile system (`.lock`), atomic PID metadata recording, stale lock detection. |
| `reaper.py` | Automated garbage collection (`tmpwatch` / `systemd-tmpfiles`), age-based pruning, boot-time wipe, and quota high-water mark pruning. |
| `permissions.py` | Security auditor, sticky-bit enforcement, world-writable file vulnerability checks. |
| `tmpfs.py` | High-performance in-memory virtual temporary filesystem (RAM-disk) with byte quotas and disk sync. |
| `manager.py` | Master `TmpManager` coordinator and top-level helper functions. |
| `cli.py` | Command-line management tool `tmp_ctl` (`list`, `mktemp`, `clean`, `boot-clean`, `locks`, `audit`, `summary`, `bootstrap`). |
| `test_tmp.py` | Standalone test suite covering all modules. |

---

## 3. Python API Usage

```python
from tmp import (
    TmpManager,
    SecureTempFile,
    SecureTempDir,
    ProcessLock,
    mktemp,
    get_temp_file,
    clean_temp,
)

# 1. Initialize master coordinator
mgr = TmpManager()

# 2. Create atomic secure temporary file (Mode 0600)
temp_file = mgr.create_temp_file(prefix="session_", suffix=".dat", content="secret payload")
print(f"Created secure file: {temp_file}")

# 3. Context manager for auto-cleanup
with SecureTempFile(content="ephemeral data") as tf:
    print(f"Using ephemeral file: {tf}")
# tf is automatically unlinked on exit

# 4. Acquire process lock
with ProcessLock("data_sync"):
    print("Process has exclusive lock across UmerOS")

# 5. Run reaper cleanup (e.g. prune files older than 10 days)
report = clean_temp(max_age_seconds=864000)
print(report.summary())
```

---

## 4. Command-Line Interface (`tmp_ctl`)

```bash
# List all entries in /tmp
python -m tmp.cli list

# Create a secure temporary file (POSIX mktemp)
python -m tmp.cli mktemp app.XXXXXXXXXX

# Create a secure temporary directory
python -m tmp.cli mktemp -d

# Clean files older than 86400 seconds (1 day)
python -m tmp.cli clean --max-age 86400

# Simulate boot-time wipe of /tmp
python -m tmp.cli boot-clean --dry-run

# List active process locks
python -m tmp.cli locks

# Run FHS & Security Audit
python -m tmp.cli audit

# View storage summary
python -m tmp.cli summary

# Bootstrap standard socket skeletons
python -m tmp.cli bootstrap
```

---

## 5. Testing

Run standalone test suite:
```bash
python tmp/test_tmp.py
```
Or via pytest:
```bash
pytest tests/test_tmp.py
```
