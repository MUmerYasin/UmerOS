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
UmerOS - regression tests for H162
===================================

H162 (💭 ``media/cleanup.py``): the module compiled its subdirectory
regex via ``__import__("re")`` — twice — instead of a normal top-level
``import re``:

    _DIR_RE = __import__("re").compile(r"^[a-z]+[0-9]*$", __import__("re").ASCII)

That is an anti-pattern: it defeats static analysis, costs an extra
module lookup per call, and hides the dependency from importers.  The
same import block also carried three unused imports (``os``,
``MediaDescriptor``, ``MediaType``), which are removed alongside.

These tests pin the *code facts* (top-level ``import re``, no
``__import__``, the compiled pattern and its flags, the unchanged
matching semantics, and the removal of the dead imports) — never a
cosmetic ``[FIX Hxxx]`` comment tag.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from media.cleanup import (
    _DIR_RE,
    _is_media_subdir,
    CleanupConfig,
    CleanupResult,
    cleanup_media,
)
from media.mount_manager import MediaConfig

SRC_PATH = Path(__file__).resolve().parent.parent / "media" / "cleanup.py"
SRC = SRC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------

def test_source_uses_top_level_import_re() -> None:
    assert re.search(r"^import re$", SRC, re.MULTILINE), "missing a top-level `import re`"


def test_source_has_no_dunder_import_call() -> None:
    assert "__import__(" not in SRC, "the __import__ anti-pattern is back"


def test_source_has_no_unused_os_import() -> None:
    assert not re.search(r"^import os$", SRC, re.MULTILINE), "unused `import os` reintroduced"


def test_source_has_no_unused_media_types_import() -> None:
    assert "MediaDescriptor" not in SRC
    assert "MediaType" not in SRC


# ---------------------------------------------------------------------------
# Compiled-pattern facts
# ---------------------------------------------------------------------------

def test_dir_re_is_a_compiled_pattern() -> None:
    assert isinstance(_DIR_RE, re.Pattern)


def test_dir_re_pattern_unchanged() -> None:
    assert _DIR_RE.pattern == r"^[a-z]+[0-9]*$"


def test_dir_re_uses_ascii_flag() -> None:
    assert _DIR_RE.flags & re.ASCII, "re.ASCII flag was dropped"


# ---------------------------------------------------------------------------
# Matching semantics (must be unchanged by the refactor)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name",
    ["usb0", "cdrom", "cdrecorder", "zip", "floppy", "usb12", "dvd"],
)
def test_accepts_media_subdir_names(name: str) -> None:
    assert _is_media_subdir(name) is True


@pytest.mark.parametrize(
    "name",
    ["USB0", "usb-1", "", "a1b2", "usb 0", "usb/0", "..", ".hidden"],
)
def test_rejects_non_media_names(name: str) -> None:
    assert _is_media_subdir(name) is False


# ---------------------------------------------------------------------------
# Functional smoke + H161 contract preserved
# ---------------------------------------------------------------------------

def test_cleanup_media_still_runs(tmp_path: Path) -> None:
    cfg = CleanupConfig(
        config=MediaConfig(media_root=tmp_path),
        dry_run=True,
        check_orphans=False,
    )
    (tmp_path / "usb0").mkdir()
    (tmp_path / "not-a-media-dir").mkdir()
    result = cleanup_media(cfg)
    assert isinstance(result, CleanupResult)
    assert result.scanned == 1


def test_selftest_returns_true() -> None:
    from media import cleanup as _m

    assert _m._selftest() is True
