# Umer OS /root

A pure-Python implementation of the
[TLDP /root reference](https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/root.html),
tailored to UmerOS.

## What the TLDP says

The `/root` page focuses on three rules:

1. `/root` is the system administrator's home directory. It is
   **not** under `/home` because `/home` is often on a different
   partition or even another system, and would be inaccessible
   when only `/` is mounted.
2. If root's home cannot be located, it **must default to** `/`.
3. Subdirectories for mail and other applications should not
   appear in `/root`. Mail for admin roles (`root`, `postmaster`,
   `webmaster`) should be forwarded to an appropriate user.

## What this package adds

| File | What it does |
|---|---|
| `home.py` | Resolve root's home from `/etc/passwd` (UID 0), `HOME`, or `/root`, with the FSSTND fallback to `/`. Audit permissions, ownership, discouraged subdirs. Bootstrap the directory. |
| `dotfiles.py` | Materialise the standard set of dotfiles (`.bashrc`, `.bash_profile`, `.profile`, `.bash_logout`, `.vimrc`) with sensible defaults. Tighten history to `0600`. |
| `shell.py` | Build a hardened root environment (`PATH`, `PS1` ending in `#`, `LD_LIBRARY_PATH=""`, `MAILCHECK=0`). Strip dangerous vars like `LD_PRELOAD`. |
| `mail.py` | Manage `~/.forward`, classify entries (local, remote, pipe, file), detect loops, expose the admin role table. |
| `safety.py` | Auditor that flags unsafe `PATH`, `LD_*` injections, permissive `.bash_history`, loose `.ssh` keys, and discouraged user-state subdirs. |
| `passwd.py` | `/etc/passwd` adapter + `CanonicalRootBuilder` so installers and audits all agree on what the root row looks like. |
| `fhs.py` | The single-call FHS / TLDP audit that wires the rest together. |
| `__main__.py` | `python -m root` CLI. |
| `__init__.py` | Public API re-exports. |

## CLI

```powershell
python -m root selftest                 # run every module's self-test
python -m root info                     # one-shot /root summary
python -m root info F:\root             # same, custom path
python -m root audit                    # FHS + safety audit
python -m root safety                   # safety auditor only
python -m root ensure                   # create the home + drop dotfiles
python -m root forward admin@x.com      # set /root/.forward
python -m root dotfiles                 # materialise the standard set
python -m root passwd                   # show the canonical /root row
python -m root help                     # help text
```

## Programmatic use

```python
import root
from root.home import RootHomeManager
from root.dotfiles import RootDotfilesManager
from root.mail import RootMailForwarder
from root.fhs import FHSRootAuditor

# Where does root live?
info = RootHomeManager().audit()
print(info.path, info.resolved_from, info.mode)

# Make sure the standard dotfiles are in place.
RootDotfilesManager(home=info.path).ensure_all(force=True)

# Forward admin mail.
RootMailForwarder(home=info.path).ensure("admin@example.com")

# One-call FHS + safety audit.
auditor = FHSRootAuditor(home=info.path)
report = auditor.audit()
if not report.ok:
    for issue in report.issues:
        print(issue.severity.value, issue.title)
```

## License

Apache 2.0 - same as the rest of Umer OS.
