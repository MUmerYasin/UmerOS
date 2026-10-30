# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Umer OS — vendored liboqs <-> Python bindings integration bridge  [EXPERIMENTAL]
================================================================================
Binds the *vendored* ``liboqs/`` C source (the pinned Open Quantum Safe
submodule declared in ``.gitmodules``; see ``THIRD_PARTY_NOTICES.md``) to the
Python post-quantum layer (``quantum/crypto_pqc.py``, which imports the
``liboqs-python`` ``oqs`` bindings declared in ``requirements.txt``).

Historically the vendored C source was dead/unwired — no Python module in the
tree referenced it — so the §4.2 "PQC via ``liboqs``" mandate was satisfied only
on paper. This module makes the relationship explicit and introspectable at
runtime: it reports whether the vendored source is present and which version it
is, whether the ``oqs`` Python bindings are importable and which version they
are, and whether the pin is declared in ``.gitmodules``.

It is *introspection only* — it never builds or loads the C library itself. The
active crypto backend remains owned by :mod:`quantum.crypto_pqc`
(``PostQuantumCrypto.backend`` / ``is_post_quantum``).

Public API:
  - vendored_liboqs_dir()        -> Path | None
  - vendored_version()           -> str | None
  - python_bindings_available()  -> bool
  - python_bindings_version()    -> str | None
  - declared_in_gitmodules()     -> bool
  - integration_status()         -> dict
  - build_instructions()         -> str
  - summarize()                  -> str

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("UmerOS.LiboqsIntegration")

# quantum/liboqs_integration.py -> repo root is the parent of the package dir.
_REPO_ROOT = Path(__file__).resolve().parents[1]
VENDORED_LIBOQS_DIR = _REPO_ROOT / "liboqs"
GITMODULES = _REPO_ROOT / ".gitmodules"
THIRD_PARTY_NOTICES = _REPO_ROOT / "THIRD_PARTY_NOTICES.md"

_VERSION_MAJOR_RE = re.compile(r"set\(\s*OQS_VERSION_MAJOR\s+(\d+)\s*\)")
_VERSION_MINOR_RE = re.compile(r"set\(\s*OQS_VERSION_MINOR\s+(\d+)\s*\)")
_VERSION_PATCH_RE = re.compile(r"set\(\s*OQS_VERSION_PATCH\s+(\d+)\s*\)")


def vendored_liboqs_dir() -> Optional[Path]:
    """Return the vendored ``liboqs/`` source directory, or ``None`` if absent.

    The directory is considered present only when it looks like the OQS C
    source tree (i.e. it carries a top-level ``CMakeLists.txt``).
    """
    d = VENDORED_LIBOQS_DIR
    try:
        if (d / "CMakeLists.txt").is_file():
            return d
    except OSError:  # pragma: no cover - defensive
        pass
    return None


def vendored_version() -> Optional[str]:
    """Return the vendored liboqs version (e.g. ``"0.16.0"``) or ``None``.

    The version is read from ``OQS_VERSION_MAJOR/MINOR/PATCH`` in the vendored
    ``CMakeLists.txt`` — the same variables the upstream build uses.
    """
    d = vendored_liboqs_dir()
    if d is None:
        return None
    try:
        text = (d / "CMakeLists.txt").read_text(encoding="utf-8", errors="ignore")
    except OSError:  # pragma: no cover - defensive
        return None
    major = _VERSION_MAJOR_RE.search(text)
    minor = _VERSION_MINOR_RE.search(text)
    patch = _VERSION_PATCH_RE.search(text)
    if major and minor and patch:
        return f"{major.group(1)}.{minor.group(1)}.{patch.group(1)}"
    return None


def python_bindings_available() -> bool:
    """Return ``True`` if the ``oqs`` (``liboqs-python``) bindings import cleanly.

    A broken wheel can call ``sys.exit(1)`` from its own import, so the guard
    catches ``BaseException`` — a missing/broken optional dependency must
    degrade, never crash the interpreter.
    """
    try:
        import oqs  # type: ignore  # noqa: F401
        return True
    except BaseException:  # pragma: no cover - env dependent  # noqa: BLE001
        return False


def python_bindings_version() -> Optional[str]:
    """Return the ``liboqs-python`` bindings version, or ``None`` if absent."""
    if not python_bindings_available():
        return None
    try:
        import oqs  # type: ignore
        v = getattr(oqs, "__version__", None)
        if v:
            return str(v)
    except BaseException:  # pragma: no cover - env dependent  # noqa: BLE001
        pass
    try:
        from importlib.metadata import version as _pkg_version
        return _pkg_version("liboqs-python")
    except Exception:  # pragma: no cover - env dependent
        return None


def declared_in_gitmodules() -> bool:
    """Return ``True`` if the ``liboqs`` submodule is declared in ``.gitmodules``."""
    try:
        return '[submodule "liboqs"]' in GITMODULES.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - defensive
        return False


def integration_status() -> Dict[str, Any]:
    """Return a full provenance report for the vendored-liboqs integration.

    Keys:
        ``vendored_source_present`` / ``vendored_source_dir`` / ``vendored_version``
            the vendored C source tree.
        ``declared_in_gitmodules``
            whether the submodule pin is declared (H151).
        ``python_bindings_available`` / ``python_bindings_version``
            the ``liboqs-python`` ``oqs`` bindings.
        ``third_party_notice_present``
            whether ``THIRD_PARTY_NOTICES.md`` records the provenance.
    """
    d = vendored_liboqs_dir()
    return {
        "vendored_source_present": d is not None,
        "vendored_source_dir": str(d) if d is not None else None,
        "vendored_version": vendored_version(),
        "declared_in_gitmodules": declared_in_gitmodules(),
        "python_bindings_available": python_bindings_available(),
        "python_bindings_version": python_bindings_version(),
        "third_party_notice_present": THIRD_PARTY_NOTICES.is_file(),
    }


def build_instructions() -> str:
    """Return human-readable steps to wire the vendored C lib into the runtime."""
    return (
        "Vendored liboqs integration\n"
        "---------------------------\n"
        "1. Initialise the pinned submodule (if not already present):\n"
        "     git submodule update --init --recursive liboqs\n"
        "2. Build the vendored C library and install the Python bindings:\n"
        "     cmake -S liboqs -B liboqs/build\n"
        "     cmake --build liboqs/build --parallel\n"
        "     pip install liboqs-python   # links against the installed liboqs\n"
        "3. Verify the runtime backend is post-quantum:\n"
        "     python -c \"from quantum.crypto_pqc import PostQuantumCrypto as P;"
        " print(P().backend)\"\n"
        '   Expected: "liboqs" (otherwise the classical fallback is active).\n'
        "See THIRD_PARTY_NOTICES.md for the pinned revision and license."
    )


def summarize() -> str:
    """Return a one-line integration summary (for logs / status endpoints)."""
    st = integration_status()
    vend = st["vendored_version"] or "absent"
    bind = st["python_bindings_version"] or ("importable" if st["python_bindings_available"] else "absent")
    return (
        f"vendored liboqs={vend} (declared={st['declared_in_gitmodules']}), "
        f"python bindings={bind}"
    )
