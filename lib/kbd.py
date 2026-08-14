"""
UmerOS /lib/kbd — Console Keymap / Font / Translation Manager
==============================================================
Implements the FHS subdirectory ``/lib/kbd`` which holds:

  * Keymaps (``*.kmap`` / ``*.map``) — keyboard layout tables
  * Console fonts (``*.psf``, ``*.psfu``)
  * Console translations (``*.trans``) — Unicode → font-index maps
  * ``unimaps``  — direct Unicode → font-position maps
  * ``keymaps/`` subdirectory with per-architecture layouts

These files are loaded at boot by ``loadkeys`` / ``setfont`` to
configure the virtual console.  UmerOS does not have a real VT
subsystem, but it models the catalogue so the console subsystem can
report which keymaps / fonts are available.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

log = logging.getLogger("UmerOS.Lib.Kbd")


class KbdFileKind(str, Enum):
    KEYMAP        = "keymap"
    KEYMAP_EXT    = "keymap_ext"        # extended keymap (include)
    FONT_PSF      = "font_psf"
    FONT_PSFU     = "font_psfu"
    TRANSLATION   = "translation"
    UNIMAP        = "unimap"
    ACM           = "acm"               # application charset map
    DEFAULT_KEYMAP = "default_keymap"


@dataclass
class KbdFile:
    """A single console / keyboard file under /lib/kbd."""
    name: str
    path: str
    kind: KbdFileKind
    size: int = 0
    description: str = ""
    language: str = ""
    variant: str = ""
    arch: str = ""               # x86 / arm64 / ppc / etc
    version: str = "1.0"
    md5: str = ""


_STOCK_KEYMAPS: List[KbdFile] = [
    # ANSI-style US keymaps
    KbdFile("defkeymap.map",  "/lib/kbd/keymaps/i386/qwerty/defkeymap.map",
        KbdFileKind.KEYMAP, size=2_048, description="Default US keymap",
        language="en", variant="us", arch="i386"),
    KbdFile("us.map",         "/lib/kbd/keymaps/i386/qwerty/us.map",
        KbdFileKind.KEYMAP, size=4_096, description="US English (qwerty)",
        language="en", variant="us", arch="i386"),
    KbdFile("uk.map",         "/lib/kbd/keymaps/i386/qwerty/uk.map",
        KbdFileKind.KEYMAP, size=4_096, description="United Kingdom (qwerty)",
        language="en", variant="uk", arch="i386"),
    KbdFile("dvorak.map",     "/lib/kbd/keymaps/i386/dvorak/dvorak.map",
        KbdFileKind.KEYMAP, size=4_096, description="US Dvorak",
        language="en", variant="dvorak", arch="i386"),
    KbdFile("colemak.map",    "/lib/kbd/keymaps/i386/colemak/colemak.map",
        KbdFileKind.KEYMAP, size=4_096, description="Colemak",
        language="en", variant="colemak", arch="i386"),
    KbdFile("de.map",         "/lib/kbd/keymaps/i386/qwertz/de.map",
        KbdFileKind.KEYMAP, size=4_096, description="German (qwertz)",
        language="de", variant="de", arch="i386"),
    KbdFile("fr.map",         "/lib/kbd/keymaps/i386/azerty/fr.map",
        KbdFileKind.KEYMAP, size=4_096, description="French (azerty)",
        language="fr", variant="fr", arch="i386"),
    KbdFile("es.map",         "/lib/kbd/keymaps/i386/qwerty/es.map",
        KbdFileKind.KEYMAP, size=4_096, description="Spanish",
        language="es", variant="es", arch="i386"),
    KbdFile("it.map",         "/lib/kbd/keymaps/i386/qwerty/it.map",
        KbdFileKind.KEYMAP, size=4_096, description="Italian",
        language="it", variant="it", arch="i386"),
    KbdFile("pt.map",         "/lib/kbd/keymaps/i386/qwerty/pt.map",
        KbdFileKind.KEYMAP, size=4_096, description="Portuguese",
        language="pt", variant="pt", arch="i386"),
    KbdFile("ru.map",         "/lib/kbd/keymaps/i386/qwerty/ru.map",
        KbdFileKind.KEYMAP, size=6_144, description="Russian (Cyrillic)",
        language="ru", variant="ru", arch="i386"),
    KbdFile("ua.map",         "/lib/kbd/keymaps/i386/qwerty/ua.map",
        KbdFileKind.KEYMAP, size=6_144, description="Ukrainian",
        language="uk", variant="ua", arch="i386"),
    KbdFile("jp.map",         "/lib/kbd/keymaps/i386/qwerty/jp.map",
        KbdFileKind.KEYMAP, size=8_192, description="Japanese (106)",
        language="ja", variant="jp106", arch="i386"),
    KbdFile("kr.map",         "/lib/kbd/keymaps/i386/qwerty/kr.map",
        KbdFileKind.KEYMAP, size=6_144, description="Korean",
        language="ko", variant="kr", arch="i386"),
    KbdFile("cn.map",         "/lib/kbd/keymaps/i386/qwerty/cn.map",
        KbdFileKind.KEYMAP, size=6_144, description="Chinese Pinyin",
        language="zh", variant="cn", arch="i386"),
    KbdFile("ar.map",         "/lib/kbd/keymaps/i386/qwerty/ar.map",
        KbdFileKind.KEYMAP, size=4_096, description="Arabic",
        language="ar", variant="ar", arch="i386"),
    KbdFile("trq.map",        "/lib/kbd/keymaps/i386/qwerty/trq.map",
        KbdFileKind.KEYMAP, size=4_096, description="Turkish (F)",
        language="tr", variant="f", arch="i386"),
    # ARM
    KbdFile("us-arm.map",     "/lib/kbd/keymaps/arm/qwerty/us.map",
        KbdFileKind.KEYMAP, size=4_096, description="US English (ARM)",
        language="en", variant="us", arch="arm"),
    # PowerPC
    KbdFile("us-mac.map",     "/lib/kbd/keymaps/mac/qwerty/us.map",
        KbdFileKind.KEYMAP, size=4_096, description="US Mac keyboard",
        language="en", variant="us-mac", arch="mac"),
]

_STOCK_FONTS: List[KbdFile] = [
    KbdFile("default8x16.psfu",  "/lib/kbd/consolefonts/default8x16.psfu",
        KbdFileKind.FONT_PSFU, size=4_384, description="Default 8x16 Unicode font"),
    KbdFile("default8x9.psfu",   "/lib/kbd/consolefonts/default8x9.psfu",
        KbdFileKind.FONT_PSFU, size=2_752, description="Default 8x9 Unicode font"),
    KbdFile("Lat2-Terminus16.psfu",
        "/lib/kbd/consolefonts/Lat2-Terminus16.psfu",
        KbdFileKind.FONT_PSFU, size=4_384, description="Terminus 16 (Latin-2)"),
    KbdFile("Lat15-Terminus16.psfu",
        "/lib/kbd/consolefonts/Lat15-Terminus16.psfu",
        KbdFileKind.FONT_PSFU, size=4_384, description="Terminus 16 (Latin-15)"),
    KbdFile("Cyr8x16.psfu",      "/lib/kbd/consolefonts/Cyr8x16.psfu",
        KbdFileKind.FONT_PSFU, size=4_384, description="Cyrillic 8x16"),
    KbdFile("UniCyr8x16.psfu",   "/lib/kbd/consolefonts/UniCyr8x16.psfu",
        KbdFileKind.FONT_PSFU, size=4_384, description="Cyrillic + Unicode 8x16"),
    KbdFile("Arabic16.psfu",     "/lib/kbd/consolefonts/Arabic16.psfu",
        KbdFileKind.FONT_PSFU, size=4_384, description="Arabic 16"),
]

_STOCK_TRANSLATIONS: List[KbdFile] = [
    KbdFile("8859-1_to_uni.trans",
        "/lib/kbd/consoletrans/8859-1_to_uni.trans",
        KbdFileKind.TRANSLATION, size=512,
        description="ISO-8859-1 → Unicode translation"),
    KbdFile("8859-2_to_uni.trans",
        "/lib/kbd/consoletrans/8859-2_to_uni.trans",
        KbdFileKind.TRANSLATION, size=512,
        description="ISO-8859-2 → Unicode translation"),
    KbdFile("8859-15_to_uni.trans",
        "/lib/kbd/consoletrans/8859-15_to_uni.trans",
        KbdFileKind.TRANSLATION, size=512,
        description="ISO-8859-15 → Unicode translation"),
    KbdFile("koi2alt.trans",
        "/lib/kbd/consoletrans/koi2alt.trans",
        KbdFileKind.TRANSLATION, size=256,
        description="KOI8-R → alt encoding"),
    KbdFile("koi8-r_to_uni.trans",
        "/lib/kbd/consoletrans/koi8-r_to_uni.trans",
        KbdFileKind.TRANSLATION, size=512,
        description="KOI8-R → Unicode translation"),
    KbdFile("cp1251_to_uni.trans",
        "/lib/kbd/consoletrans/cp1251_to_uni.trans",
        KbdFileKind.TRANSLATION, size=512,
        description="Windows-1251 → Unicode translation"),
]

_STOCK_UNIMAPS: List[KbdFile] = [
    KbdFile("default.uni",      "/lib/kbd/unimaps/default.uni",
        KbdFileKind.UNIMAP, size=1_024, description="Default Unicode map"),
    KbdFile("latin1.uni",       "/lib/kbd/unimaps/linux/uni-lat1.uni",
        KbdFileKind.UNIMAP, size=512, description="Latin-1"),
    KbdFile("latin2.uni",       "/lib/kbd/unimaps/linux/uni-lat2.uni",
        KbdFileKind.UNIMAP, size=512, description="Latin-2"),
    KbdFile("cyrillic.uni",     "/lib/kbd/unimaps/linux/uni-cyr.uni",
        KbdFileKind.UNIMAP, size=1_024, description="Cyrillic"),
    KbdFile("arabic.uni",       "/lib/kbd/unimaps/linux/uni-arab.uni",
        KbdFileKind.UNIMAP, size=1_024, description="Arabic"),
]


class KbdManager:
    """
    Manages the ``/lib/kbd`` directory tree: keymaps, console fonts,
    translations and unimaps.
    """

    def __init__(self, lib_path: str = "/lib", kbd_path: str = "/lib/kbd") -> None:
        self.lib_path = Path(lib_path)
        self.kbd_path = Path(kbd_path)
        self._files: Dict[str, KbdFile] = {}
        for f in _STOCK_KEYMAPS + _STOCK_FONTS + _STOCK_TRANSLATIONS + _STOCK_UNIMAPS:
            self._files[f.name] = f

    # ── queries ──────────────────────────────────────────────────

    def list_files(self, kind: Optional[KbdFileKind] = None) -> List[KbdFile]:
        if kind is None:
            return list(self._files.values())
        return [f for f in self._files.values() if f.kind == kind]

    def list_keymaps(self) -> List[KbdFile]:
        return self.list_files(KbdFileKind.KEYMAP)

    def list_fonts(self) -> List[KbdFile]:
        return self.list_files(KbdFileKind.FONT_PSFU) + self.list_files(KbdFileKind.FONT_PSF)

    def list_translations(self) -> List[KbdFile]:
        return self.list_files(KbdFileKind.TRANSLATION)

    def list_unimaps(self) -> List[KbdFile]:
        return self.list_files(KbdFileKind.UNIMAP)

    def find(self, name: str) -> Optional[KbdFile]:
        return self._files.get(name)

    def find_by_language(self, language: str) -> List[KbdFile]:
        return [f for f in self._files.values() if f.language == language]

    def find_by_variant(self, variant: str) -> List[KbdFile]:
        return [f for f in self._files.values() if f.variant == variant]

    def find_by_arch(self, arch: str) -> List[KbdFile]:
        return [f for f in self._files.values() if f.arch == arch]

    def default_keymap(self) -> Optional[KbdFile]:
        """Return the recommended default keymap (US English)."""
        return self._files.get("us.map")

    def default_font(self) -> Optional[KbdFile]:
        return self._files.get("default8x16.psfu")

    # ── registration ─────────────────────────────────────────────

    def register(self, file: KbdFile) -> None:
        self._files[file.name] = file

    def unregister(self, name: str) -> bool:
        return self._files.pop(name, None) is not None

    # ── on-disk materialisation ──────────────────────────────────

    def materialise_stubs(self, root: str = "/") -> int:
        """Create stub files on disk so the directory actually exists."""
        target = Path(root) / "lib" / "kbd"
        written = 0
        for f in self._files.values():
            p = target / f.path[len("/lib/kbd/"):]
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                header = f"UmerOS stub: {f.description}\n".encode()
                p.write_bytes(header)
                written += 1
        return written

    # ── summary ──────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        files = list(self._files.values())
        return {
            "total_files": len(files),
            "keymaps": len(self.list_keymaps()),
            "fonts": len(self.list_fonts()),
            "translations": len(self.list_translations()),
            "unimaps": len(self.list_unimaps()),
            "total_size_bytes": sum(f.size for f in files),
            "languages": sorted({f.language for f in files if f.language}),
            "architectures": sorted({f.arch for f in files if f.arch}),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = KbdManager(lib_path=tmpdir, kbd_path=tmpdir)
        summary = mgr.get_summary()
        assert "total_files" in summary, "summary should have total_files"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
