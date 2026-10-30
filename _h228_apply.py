"""H228 applier -- root/mail.py: create root's home at 0700, write .forward at 0600."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("root/mail.py")
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


# --- 1. module-level `os` (it was imported ad hoc inside the method) --------
sub(
    "import logging\nimport re\n",
    "import logging\nimport os\nimport re\n",
    "import os",
)

# --- 2. mode constants ------------------------------------------------------
sub(
    'FORWARD_FILENAME: str = ".forward"\n',
    'FORWARD_FILENAME: str = ".forward"\n\n'
    "#: FHS-recommended mode for root's home directory.\n"
    "HOME_MODE: int = 0o700\n\n"
    "#: ``.forward`` names an address outside the host -- owner-only.\n"
    "FORWARD_MODE: int = 0o600\n",
    "mode constants",
)

# --- 3. ensure(): delegate home creation + file write -----------------------
OLD = '''    def ensure(self, address: str, *, comment: Optional[str] = None) -> ForwardReport:
        """Create or replace the ``.forward`` file with one entry."""
        if not address:
            raise ValueError("address must not be empty")
        lines = []
        if comment:
            lines.append(f"# {comment}")
        lines.append(address)
        text = "\\n".join(lines) + "\\n"
        self.home.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")
        try:
            import stat
            os_chmod = getattr(self.path, "chmod", None)
            if os_chmod is None:
                import os
                os.chmod(self.path, 0o600)
            else:
                os_chmod(0o600)
        except OSError as exc:
            log.warning("could not chmod %s: %s", self.path, exc)
        return self.audit()
'''

NEW = '''    def ensure(self, address: str, *, comment: Optional[str] = None) -> ForwardReport:
        """Create or replace the ``.forward`` file with one entry.

        The root home is created (if missing) with mode ``0700`` and the file
        with mode ``0600``; see :meth:`_ensure_home` and
        :meth:`_write_forward` for why neither relies on the process umask.
        """
        if not address:
            raise ValueError("address must not be empty")
        lines = []
        if comment:
            lines.append(f"# {comment}")
        lines.append(address)
        text = "\\n".join(lines) + "\\n"
        self._ensure_home()
        self._write_forward(text)
        return self.audit()

    def _ensure_home(self) -> None:
        """Create root's home if missing and force it to ``0700``.

        ``Path.mkdir()`` applies the process umask to ``mode``, so a plain
        ``mkdir()`` leaves the directory at ~0755 -- world-readable and
        world-executable, which is wrong for the admin home.  The mode is
        therefore re-applied with an explicit ``chmod`` after creation.

        An existing directory is tightened too: this class only ever manages
        root's home and ``0700`` is the only acceptable mode for it (the
        sibling :class:`RootHomeManager.ensure` behaves the same way).  A
        chmod failure is logged rather than raised -- on a filesystem without
        POSIX permissions the directory is still usable, and
        :meth:`RootSafetyAuditor` reports the mode.
        """
        if not self.home.exists():
            self.home.mkdir(parents=True, exist_ok=True, mode=HOME_MODE)
            log.info("created root home at %s (mode %s)", self.home, oct(HOME_MODE))
        try:
            os.chmod(self.home, HOME_MODE)
        except OSError as exc:
            log.warning("could not chmod %s to %s: %s", self.home, oct(HOME_MODE), exc)

    def _write_forward(self, text: str) -> None:
        """Write ``.forward`` with its final ``0600`` mode from the start.

        Creating the file under the default umask and chmod-ing afterwards
        leaves a window in which ``.forward`` -- which names a delivery address
        outside the host -- is world-readable.  The file is therefore opened
        with the target mode, and re-chmod-ed to cover a pre-existing file
        (``os.open``'s mode argument only applies on creation).
        """
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FORWARD_MODE)
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
        try:
            os.chmod(self.path, FORWARD_MODE)
        except OSError as exc:
            log.warning("could not chmod %s to %s: %s", self.path, oct(FORWARD_MODE), exc)
'''

sub(OLD, NEW, "ensure + helpers")

if src == orig:
    print("ABORT: nothing changed")
    sys.exit(1)

TARGET.write_text(src, encoding="utf-8")

import py_compile

py_compile.compile(str(TARGET), doraise=True)
print("compiles clean")

assert "os_chmod = getattr" not in src, "old chmod dance survived"
assert "mkdir(parents=True, exist_ok=True)" not in src, "unmoded mkdir survived"
print("post-conditions OK")
