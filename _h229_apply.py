"""H229 applier -- root/passwd.py: write the .bak copy owner-only."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("root/passwd.py")
src = TARGET.read_text(encoding="utf-8")
orig = src


def sub(old: str, new: str, label: str) -> None:
    global src
    n = src.count(old)
    if n != 1:
        print(f"ABORT [{label}]: expected 1 occurrence, found {n}")
        sys.exit(1)
    src = src.replace(old, new)
    print(f"OK [{label}]")


# --- 1. mode constants ------------------------------------------------------
sub(
    'log = logging.getLogger("UmerOS.Root.Passwd")\n',
    'log = logging.getLogger("UmerOS.Root.Passwd")\n\n'
    "#: ``/etc/passwd`` is world-readable by design -- it holds no hashes (those\n"
    "#: live in ``/etc/shadow``) and every program needs to resolve names.\n"
    "PASSWD_MODE: int = 0o644\n\n"
    "#: The ``.bak`` copy is the same account database and has no operational\n"
    "#: reason to be readable, so it is owner-only.\n"
    "BACKUP_MODE: int = 0o600\n",
    "mode constants",
)

# --- 2. write(): delegate the backup, use PASSWD_MODE ----------------------
OLD = '''        gate.require(CAP_SYS_ADMIN)
        if backup and self.path.is_file():
            bak = self.path.with_suffix(self.path.suffix + ".bak")
            bak.write_bytes(self.path.read_bytes())
        body = "\\n".join(e.as_line() for e in entries) + "\\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(body, encoding="utf-8")
        try:
            self.path.chmod(0o644)
        except OSError:
            pass
'''

NEW = '''        gate.require(CAP_SYS_ADMIN)
        if backup and self.path.is_file():
            self._write_backup()
        body = "\\n".join(e.as_line() for e in entries) + "\\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(body, encoding="utf-8")
        try:
            self.path.chmod(PASSWD_MODE)
        except OSError as exc:
            log.warning("could not chmod %s to %s: %s", self.path, oct(PASSWD_MODE), exc)

    def _write_backup(self) -> Path:
        """Copy the current file to ``<path>.bak`` with owner-only permissions.

        ``Path.write_bytes`` creates the copy under the process umask, which
        typically leaves ``/etc/passwd.bak`` at 0644 -- world-readable.  The
        contents are the same account database (names, UIDs, GECOS, home
        directories, shells), and although there are no hashes in it, a backup
        has no operational reason to be readable and tends to outlive the edit
        that created it, so it is written at ``BACKUP_MODE`` instead.

        The copy stays beside its source: a restore is then a rename, and the
        conventional ``/etc/passwd.bak`` location keeps it auditable.  The
        containing directory's mode is the caller's responsibility.

        Returns:
            The path of the backup that was written.
        """
        bak = self.path.with_suffix(self.path.suffix + ".bak")
        payload = self.path.read_bytes()
        fd = os.open(bak, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, BACKUP_MODE)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        try:
            os.chmod(bak, BACKUP_MODE)
        except OSError as exc:
            log.warning("could not chmod %s to %s: %s", bak, oct(BACKUP_MODE), exc)
        log.info("backed up %s to %s", self.path, bak)
        return bak
'''

sub(OLD, NEW, "write + _write_backup")

if src == orig:
    print("ABORT: nothing changed")
    sys.exit(1)

TARGET.write_text(src, encoding="utf-8")

import py_compile

py_compile.compile(str(TARGET), doraise=True)
print("compiles clean")

assert "bak.write_bytes(" not in src, "old umask backup write survived"
assert "self.path.chmod(0o644)" not in src, "hardcoded passwd mode survived"
print("post-conditions OK")
