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
Regression test for packages/umer_pkg.py YELLOW finding H204.

Extraction must not materialize hostile archive members as links, and member
modes must never be applied verbatim.  ``filter="data"`` (Python >= 3.12,
which setup.py requires) already refuses links escaping the destination and
strips setuid bits; this pins the version-independent ``_safe_tar_members``
guard that holds the same policy where ``filter=`` is unavailable, plus the
``build()`` side never archiving through a symlink.
"""

from __future__ import annotations

import io
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import packages.umer_pkg as up                              # noqa: E402
from packages.umer_pkg import UmerPackageManager            # noqa: E402

POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="POSIX symlink semantics / mode bits"
)


def _archive(members) -> bytes:
    """Build a .umerpkg-shaped tar.gz: manifest.json + the given members.

    members: list of (name, kind, payload, mode) where kind is one of
    "file" / "sym" / "lnk" / "fifo".
    """
    import json

    buf = io.BytesIO()
    manifest = json.dumps(
        {"name": "demo", "version": "1.0.0", "description": "h204"}
    ).encode()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        tar.addfile(info, io.BytesIO(manifest))
        for name, kind, payload, mode in members:
            m = tarfile.TarInfo(name)
            m.mode = mode
            if kind == "file":
                data = payload.encode()
                m.size = len(data)
                tar.addfile(m, io.BytesIO(data))
            elif kind == "sym":
                m.type = tarfile.SYMTYPE
                m.linkname = payload
                tar.addfile(m)
            elif kind == "lnk":
                m.type = tarfile.LNKTYPE
                m.linkname = payload
                tar.addfile(m)
            elif kind == "fifo":
                m.type = tarfile.FIFOTYPE
                tar.addfile(m)
            else:  # pragma: no cover - test-author guard
                raise AssertionError(f"unknown member kind {kind!r}")
    return buf.getvalue()


def _members_of(data: bytes):
    buf = io.BytesIO(data)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        return list(tar.getmembers())


def _selected(data: bytes, prefix: str = "files/"):
    """Names _safe_tar_members keeps (fresh read each time)."""
    buf = io.BytesIO(data)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        return [m.name for m in up._safe_tar_members(tar, prefix)]


# ---------------------------------------------------------------------------
# Unit level: the version-independent member guard
# ---------------------------------------------------------------------------

class TestSafeTarMembersH204:
    def test_h194_tar_slip_still_dropped(self):
        data = _archive([
            ("files/ok.txt", "file", "ok", 0o644),
            ("files/../../escape.txt", "file", "pwn", 0o644),
            ("/abs/evil.txt", "file", "pwn", 0o644),
        ])
        assert _selected(data) == ["files/ok.txt"]

    def test_absolute_symlink_dropped(self):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/link", "sym", "/etc/shadow", 0o777),
            ("files/win", "sym", "C:/Windows/System32/evil", 0o777),
            ("files/unc", "sym", "//server/share/evil", 0o777),
        ])
        assert _selected(data) == ["files/regular.txt"]

    def test_symlink_escaping_prefix_dropped(self):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/inward", "sym", "../sibling", 0o777),
            ("files/deep", "sym", "files/../../x", 0o777),
        ])
        assert _selected(data) == ["files/regular.txt"]

    def test_symlink_inside_prefix_kept(self):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/a", "sym", "files/regular.txt", 0o777),
            ("files/b", "sym", "regular.txt", 0o777),
        ])
        assert _selected(data) == [
            "files/regular.txt", "files/a", "files/b",
        ]

    def test_hardlink_to_selected_member_kept(self):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/hard", "lnk", "files/regular.txt", 0o644),
        ])
        assert _selected(data) == ["files/regular.txt", "files/hard"]

    def test_hardlink_to_unknown_or_foreign_member_dropped(self):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/hard", "lnk", "files/missing.txt", 0o644),
            ("files/foreign", "lnk", "manifest.json", 0o644),
        ])
        assert _selected(data) == ["files/regular.txt"]

    def test_special_files_dropped(self):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/pipe", "fifo", "", 0o644),
        ])
        assert _selected(data) == ["files/regular.txt"]

    def test_unsafe_mode_bits_clamped(self):
        data = _archive([
            ("files/suid", "file", "x", 0o4755),
            ("files/sgid", "file", "x", 0o2755),
            ("files/sticky", "file", "x", 0o1755),
            ("files/worldwrite", "file", "x", 0o666),
            ("files/normal", "file", "x", 0o644),
            ("files/dir", "file", "x", 0o777),
        ])
        buf = io.BytesIO(data)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            modes = {m.name: m.mode for m in up._safe_tar_members(tar, "files/")}
        assert modes == {
            "files/suid": 0o755,
            "files/sgid": 0o755,
            "files/sticky": 0o755,
            "files/worldwrite": 0o644,
            "files/normal": 0o644,
            "files/dir": 0o755,
        }

    def test_no_filter_extraction_refuses_link_and_escapes_nothing(self, tmp_path,
                                                                  monkeypatch):
        """With extractall's filter= disabled (simulating Python < 3.12), the
        guard alone must stop the escaping symlink from being created."""
        monkeypatch.setattr(up, "_FILTER_KW", {})
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/link", "sym", str(tmp_path / "outside"), 0o777),
        ])
        dest = tmp_path / "dest"
        dest.mkdir()
        buf = io.BytesIO(data)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            members = up._safe_tar_members(tar, "files/")
            tar.extractall(path=str(dest), members=members, **up._FILTER_KW)
        assert not (dest / "files" / "link").exists()
        assert not (dest / "files" / "link").is_symlink()


# ---------------------------------------------------------------------------
# Install level: end-to-end through _install_single
# ---------------------------------------------------------------------------

class _Env:
    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.registry = root / "registry"
        self.install_dir = root / "installed"
        self.cache = root / "cache"
        self.registry.mkdir(parents=True, exist_ok=True)
        self.mgr = UmerPackageManager(
            install_dir=str(self.install_dir),
            registry_dir=str(self.registry),
            cache_dir=str(self.cache),
        )
        # Isolate the extraction path from the signature gate (covered by the
        # H196 tests); these archives are hand-built, not signed.
        self.mgr._verify_package = lambda path: True  # type: ignore[assignment]

    def install(self, data: bytes) -> bool:
        arch = self.registry / "demo-1.0.0.umerpkg"
        arch.write_bytes(data)
        return self.mgr._install_single("demo", str(arch))

    @property
    def dest(self) -> Path:
        return self.install_dir / "demo"

    def cleanup(self) -> None:
        self._tmp.cleanup()


@pytest.fixture
def env():
    e = _Env()
    yield e
    e.cleanup()


class TestInstallExtractionH204:
    def test_escaping_symlink_never_materializes(self, env):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/link", "sym", "/etc/shadow", 0o777),
        ])
        assert env.install(data) is True
        assert (env.dest / "files" / "regular.txt").read_text() == "hi"
        assert not (env.dest / "files" / "link").exists()
        assert not (env.dest / "files" / "link").is_symlink()

    def test_fifo_never_materializes(self, env):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/pipe", "fifo", "", 0o644),
        ])
        assert env.install(data) is True
        assert not (env.dest / "files" / "pipe").exists()

    @POSIX_ONLY
    def test_setuid_bit_not_restored(self, env):
        data = _archive([("files/suid", "file", "x", 0o4755)])
        assert env.install(data) is True
        mode = (env.dest / "files" / "suid").stat().st_mode
        assert not (mode & 0o7000), f"setuid/setgid/sticky survived: {oct(mode)}"

    @POSIX_ONLY
    def test_world_write_bit_not_restored(self, env):
        data = _archive([("files/ww", "file", "x", 0o666)])
        assert env.install(data) is True
        mode = (env.dest / "files" / "ww").stat().st_mode
        assert not (mode & 0o022), f"group/other write survived: {oct(mode)}"

    @POSIX_ONLY
    def test_in_prefix_symlink_allowed_and_contained(self, env):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/a", "sym", "regular.txt", 0o777),
        ])
        assert env.install(data) is True
        link = env.dest / "files" / "a"
        assert link.is_symlink()
        assert link.read_text() == "hi"

    def test_in_archive_hardlink_allowed(self, env):
        data = _archive([
            ("files/regular.txt", "file", "hi", 0o644),
            ("files/hard", "lnk", "files/regular.txt", 0o644),
        ])
        assert env.install(data) is True
        assert (env.dest / "files" / "hard").read_text() == "hi"


# ---------------------------------------------------------------------------
# build(): never archive through a symlink
# ---------------------------------------------------------------------------

class TestBuildSkipsSymlinks:
    @POSIX_ONLY
    def test_symlinked_source_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "real.txt").write_text("real", encoding="utf-8")
            secret = Path(tmp) / "secret.txt"
            secret.write_text("TOPSECRET", encoding="utf-8")
            os.symlink(secret, src / "sneaky.txt")

            mgr = UmerPackageManager()
            archive = mgr.build(
                source_dir=str(src),
                manifest={"name": "demo", "version": "1.0.0",
                          "description": "h204"},
                output_dir=tmp,
                signing_key=None,
                key_id=None,
            )
            with tarfile.open(archive, "r:gz") as tar:
                names = tar.getnames()
            assert "files/real.txt" in names
            assert "files/sneaky.txt" not in names
            # and the secret content is nowhere in the archive
            with tarfile.open(archive, "r:gz") as tar:
                for m in tar.getmembers():
                    if m.isreg():
                        fh = tar.extractfile(m)
                        assert b"TOPSECRET" not in (fh.read() if fh else b"")
