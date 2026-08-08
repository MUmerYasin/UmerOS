"""
UmerOS /etc MIME Configuration
================================
Manages MIME type associations and mailcap configuration.

FHS 3.0 entries:
  /etc/mime.types    — MIME type definitions
  /etc/mailcap       — MIME application handling
  /etc/mime.types.d/ — Additional MIME type definitions

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.MimeConfig")


@dataclass
class MimeType:
    """Represents a MIME type definition."""
    mime_type: str
    extensions: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)


@dataclass
class MailcapEntry:
    """Represents a mailcap entry."""
    mime_type: str
    command: str
    test: str = ""
    description: str = ""
    comments: List[str] = field(default_factory=list)


class MimeConfigManager:
    """
    Manages MIME type configuration.

    Handles /etc/mime.types, /etc/mailcap, and /etc/mime.types.d/.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.mime_types_d_path = self.etc_path / "mime.types.d"

    def initialize(self) -> bool:
        """Create all MIME configuration files with defaults."""
        try:
            self._create_mime_types()
            self._create_mailcap()
            self._create_mime_types_d()
            log.info("Initialized MIME configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize MIME config: %s", e)
            return False

    # ── /etc/mime.types ──────────────────────────────────────────────────

    def _create_mime_types(self) -> None:
        """Create /etc/mime.types (MIME type definitions)."""
        filepath = self.etc_path / "mime.types"
        if filepath.exists():
            return
        content = """# /etc/mime.types - MIME type definitions
# UmerOS MIME Type Configuration
# Format: type/subtype  extension1 extension2 ...

# Text types
text/plain                              txt asc
text/html                               html htm
text/css                                css
text/javascript                         js
text/xml                                xml xsl
text/x-python                           py
text/x-perl                             pl
text/x-shellscript                      sh
text/x-c                                c
text/x-c++                              cpp cxx
text/x-java                             java
text/x-markdown                         md markdown
text/x-tex                              tex
text/x-csrc                             c
text/x-chdr                             h

# Image types
image/jpeg                              jpg jpeg jpe
image/png                               png
image/gif                               gif
image/bmp                               bmp
image/svg+xml                           svg
image/tiff                              tiff tif
image/x-icon                            ico
image/x-xbitmap                         xbm
image/x-xpixmap                         xpm

# Audio types
audio/mpeg                              mp3
audio/ogg                               ogg
audio/wav                               wav
audio/x-wav                             wav
audio/x-flac                            flac
audio/mp4                               m4a
audio/aac                               aac
audio/x-ms-wma                          wma

# Video types
video/mpeg                              mpeg mpg mpe
video/mp4                               mp4 m4v
video/quicktime                         mov
video/x-msvideo                         avi
video/x-ms-wmv                          wmv
video/webm                              webm
video/x-flv                             flv
video/3gpp                              3gp

# Application types
application/pdf                         pdf
application/zip                         zip
application/gzip                        gz
application/x-tar                       tar
application/x-bzip2                     bz2
application/x-gzip                      gz
application/x-xz                        xz
application/x-rpm                       rpm
application/x-deb                       deb
application/x-java-archive              jar
application/javascript                  js
application/json                        json
application/xml                         xml
application/xhtml+xml                   xhtml xht
application/epub+zip                    epub
application/rtf                         rtf

# Archive types
application/x-7z-compressed             7z
application/x-rar                       rar
application/x-tar                       tar
application/x-gtar                      gtar

# Office types
application/msword                      doc
application/vnd.openxmlformats-officedocument.wordprocessingml.document  docx
application/vnd.ms-excel                xls
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet  xlsx
application/vnd.ms-powerpoint           ppt
application/vnd.openxmlformats-officedocument.presentationml.presentation  pptx

# Font types
font/ttf                                ttf
font/otf                                otf
font/woff                               woff
font/woff2                              woff2

# Message types
message/rfc822                          eml

# Multipart types
multipart/mixed                         *
multipart/alternative                   *
multipart/related                       *
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/mime.types")

    # ── /etc/mailcap ─────────────────────────────────────────────────────

    def _create_mailcap(self) -> None:
        """Create /etc/mailcap (MIME application handling)."""
        filepath = self.etc_path / "mailcap"
        if filepath.exists():
            return
        content = """# /etc/mailcap - MIME application handling
# UmerOS Mailcap Configuration
# See mailcap(5) for details.
# Format: type/subtype; command [; parameter=value ...]

# Text types
text/plain; cat %s
text/html; firefox %s
text/html; xdg-open %s
text/css; cat %s
text/javascript; cat %s

# Image types
image/jpeg; eog %s
image/png; eog %s
image/gif; eog %s
image/svg+xml; inkscape %s
image/bmp; eog %s

# Audio types
audio/mpeg; mpv %s
audio/ogg; mpv %s
audio/wav; mpv %s
audio/x-flac; mpv %s

# Video types
video/mpeg; mpv %s
video/mp4; mpv %s
video/quicktime; mpv %s
video/x-msvideo; mpv %s
video/webm; mpv %s

# Application types
application/pdf; xdg-open %s
application/zip; file-roller %s
application/gzip; file-roller %s
application/x-tar; file-roller %s
application/x-7z-compressed; file-roller %s
application/x-rar; file-roller %s
application/json; python3 -m json.tool %s
application/xml; cat %s

# Office types
application/msword; libreoffice %s
application/vnd.openxmlformats-officedocument.wordprocessingml.document; libreoffice %s
application/vnd.ms-excel; libreoffice %s
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; libreoffice %s
application/vnd.ms-powerpoint; libreoffice %s
application/vnd.openxmlformats-officedocument.presentationml.presentation; libreoffice %s

# Font types
font/ttf; font-viewer %s
font/otf; font-viewer %s
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/mailcap")

    # ── /etc/mime.types.d/ ───────────────────────────────────────────────

    def _create_mime_types_d(self) -> None:
        """Create /etc/mime.types.d/ directory with base configuration."""
        self.mime_types_d_path.mkdir(parents=True, exist_ok=True)
        base = self.mime_types_d_path / "base.types"
        if not base.exists():
            content = """# /etc/mime.types.d/base.types
# Base MIME type definitions

# Text
text/plain                              txt
text/html                               html htm
text/css                                css
text/javascript                         js

# Image
image/jpeg                              jpg jpeg
image/png                               png
image/gif                               gif
image/svg+xml                           svg

# Audio
audio/mpeg                              mp3
audio/ogg                               ogg
audio/wav                               wav

# Video
video/mp4                               mp4
video/mpeg                              mpeg
video/quicktime                         mov
video/webm                              webm

# Application
application/pdf                         pdf
application/json                        json
application/xml                         xml
application/zip                         zip
"""
            base.write_text(content, encoding="utf-8")
            log.debug("Created /etc/mime.types.d/base.types")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_mime_types(self) -> List[MimeType]:
        """Parse /etc/mime.types into a list of MIME type definitions."""
        filepath = self.etc_path / "mime.types"
        if not filepath.exists():
            return []
        types = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                types.append(MimeType(
                    mime_type=parts[0],
                    extensions=parts[1:],
                ))
        return types

    def parse_mailcap(self) -> List[MailcapEntry]:
        """Parse /etc/mailcap into a list of mailcap entries."""
        filepath = self.etc_path / "mailcap"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(";")
            if len(parts) >= 2:
                mime_type = parts[0].strip()
                command = parts[1].strip()
                test = ""
                for part in parts[2:]:
                    if part.strip().startswith("test="):
                        test = part.strip().split("=", 1)[1]
                entries.append(MailcapEntry(
                    mime_type=mime_type,
                    command=command,
                    test=test,
                ))
        return entries

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of MIME configuration."""
        return {
            "mime_types_exists": (self.etc_path / "mime.types").exists(),
            "mailcap_exists": (self.etc_path / "mailcap").exists(),
            "mime_types_d_exists": self.mime_types_d_path.exists(),
        }
