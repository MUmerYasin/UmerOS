

---

## 1. Overview & Purpose

The `/sources` subsystem implements the entire reference corpus, standards specifications, System V signal table, architecture glossary, and source tree manager for UmerOS.

### Key Pillars:
1. **Official Bibliography & Citation Registry (Appendix B):**
   - Catalog of classic Unix architecture texts (Kernighan & Pike, John Lions, Lars Wirzenius, Ellen Siever).
   - Standards specifications (FHS, FSSTND, DevFS, SELinux).
   - Export capabilities in BibTeX, Markdown, and JSON.
2. **UNIX System V & POSIX Signals Engine (Appendix A):**
   - Full signal definitions (Signals 1 to 31: `SIGHUP` through `SIGSYS`).
   - Default actions (`TERM`, `CORE`, `IGN`, `STOP`, `CONT`).
   - Uncatchable signal enforcement (`SIGKILL` and `SIGSTOP`).
   - Custom handler registration, masking, and inter-process dispatching.
3. **Architecture Glossary (Glossary):**
   - Comprehensive dictionary covering 50+ foundational Linux/Unix concepts (`ARPA`, `BASH`, `core`, `daemon`, `devfs`, `EXT2/3`, `FHS`, `inode`, `initrd`, `IPC`, `mount point`, `PAM`, `PID`, `POSIX`, `procfs`, `runlevel`, `SELinux`, `sticky bit`, `VFS`, `zombie`).
4. **Kernel Documentation Specifications Parser:**
   - ProcFS reference model (`/usr/src/linux/Documentation/filesystems/proc.txt`).
   - Initrd two-stage boot specification (`/usr/src/linux/Documentation/initrd.txt`).
   - System V runlevels specification (`/usr/share/doc/sysvinit/README.runlevels.gz`).
5. **Source Tree & Package Hierarchy (`/usr/src`):**
   - Kernel source tree layout (`Documentation`, `include`, `drivers`, `fs`, `kernel`, `arch`).
   - Package source repository layout (`SOURCES`, `SPECS`, `BUILD`, `RPMS`, `SRPMS`).
   - Source code search & symbol lookup.

---

## 2. Architecture & Modules

| Module | Description |
|---|---|
| `bibliography.py` | Bibliography registry, canonical citations, BibTeX / Markdown export. |
| `signals.py` | Complete System V & POSIX signals (1-31), default actions, handler dispatching. |
| `glossary.py` | Linux Filesystem Hierarchy glossary entries, definitions, category search. |
| `specs_parser.py` | Kernel doc parser for `proc.txt`, `initrd.txt`, and `sysvinit runlevels`. |
| `source_tree.py` | Source tree provisioning for `/usr/src` and source code search. |
| `manager.py` | Master `SourcesManager` unified search and controller. |
| `cli.py` | Command-line management tool `sources_ctl`. |
| `test_sources.py` | Standalone test suite. |

---

## 3. Python API Usage

```python
from sources import (
    SourcesManager,
    BibliographyRegistry,
    SignalDispatcher,
    GlossaryRegistry,
    KernelDocsRegistry,
)

# 1. Initialize master coordinator
mgr = SourcesManager()

# 2. Search across bibliography, glossary, signals, and kernel docs
results = mgr.search_all("initrd")
print(f"Total Matches: {results['total_matches']}")

# 3. Export bibliography in BibTeX format
bibtex = mgr.bibliography.export(format_type="bibtex")
print(bibtex)

# 4. Dispatch System V signals with custom callbacks
dispatcher = mgr.signals
dispatcher.register_handler("SIGUSR1", lambda sig, ctx: print("Received SIGUSR1"))
dispatcher.send_signal(pid=1001, signum="SIGUSR1")

# 5. Look up glossary terms
entry = mgr.glossary.get("inode")
print(f"{entry.term}: {entry.definition}")

# 6. Read kernel documentation specifications
proc_doc = KernelDocsRegistry.get_doc("proc.txt")
print(proc_doc["summary"])
```

---

## 4. Command-Line Interface (`sources_ctl`)

```bash
# List all bibliography sources
python -m sources.cli list

# Show full details and BibTeX for a citation
python -m sources.cli show kernighan1984unix

# Unified search across sources, glossary, signals, and docs
python -m sources.cli search kernel

# Inspect System V signals
python -m sources.cli signals
python -m sources.cli signals SIGSEGV

# Look up glossary definitions
python -m sources.cli glossary FHS

# View kernel documentation specifications
python -m sources.cli kernel-doc proc.txt
python -m sources.cli kernel-doc initrd.txt

# Export bibliography
python -m sources.cli export --format bibtex
```

---

## 5. Testing

Run standalone test suite:
```bash
python sources/test_sources.py
```
Or via pytest:
```bash
pytest tests/test_sources.py
```
