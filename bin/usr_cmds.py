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
UmerOS /usr/bin Utilities
==========================================
Additional /usr/bin commands per Filesystem Hierarchy Standard.
These complement the 61 commands already in usr_commands.py.
"""

from __future__ import annotations

import os
import sys
import time
import hashlib
import math
from typing import Any, List, Optional


# ─── Build & Development Tools ───────────────────────────────────────────────

class MakeCommand:
    """GNU make (make)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        targets = [a for a in args if not a.startswith('-')]
        jobs = 1
        for i, a in enumerate(args):
            if a.startswith('-j') and len(a) > 2:
                jobs = int(a[2:])
            elif a == '-j' and i + 1 < len(args):
                jobs = int(args[i + 1])

        if not os.path.exists('Makefile') and not os.path.exists('makefile'):
            print("make: *** No targets specified and no Makefile found.  Stop.", file=sys.stderr)
            return 2

        print(f"make -j{jobs} (stub: no real build)")
        return 0

    def help(self) -> str:
        return "make - GNU make utility"


class GccCommand:
    """GNU C Compiler (gcc)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("gcc: no input files", file=sys.stderr)
            return 1

        output = "a.out"
        sources = []
        for i, a in enumerate(args):
            if a == '-o' and i + 1 < len(args):
                output = args[i + 1]
            elif a == '-c':
                pass
            elif not a.startswith('-'):
                sources.append(a)

        if not sources:
            print("gcc: no input files", file=sys.stderr)
            return 1

        print(f"gcc: compiling {len(sources)} file(s) -> {output} (stub)")
        return 0

    def help(self) -> str:
        return "gcc - GNU C compiler"


class CppCommand:
    """C Preprocessor (cpp)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("cpp: C preprocessor (stub)")
        return 0

    def help(self) -> str:
        return "cpp - the GNU C preprocessor"


class AsCommand:
    """GNU assembler (as)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("as: GNU assembler (stub)")
        return 0

    def help(self) -> str:
        return "as - the GNU assembler"


class LdCommand:
    """GNU linker (ld)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("ld: GNU linker (stub)")
        return 0

    def help(self) -> str:
        return "ld - the GNU linker"


class ArCommand:
    """Create, modify, and extract from archives (ar)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("ar: missing operands", file=sys.stderr)
            print("Usage: ar [flags] archive member ...", file=sys.stderr)
            return 1

        op = args[0]
        print(f"ar: operation '{op}' (stub)")
        return 0

    def help(self) -> str:
        return "ar - create, modify, and extract from archives"


class RanlibCommand:
    """Generate an index for an archive (ranlib)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("ranlib: missing archive", file=sys.stderr)
            return 1
        print(f"ranlib: generating index for '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "ranlib - generate index for an archive"


class NmCommand:
    """List symbols from object files (nm)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("nm: missing file operand", file=sys.stderr)
            return 1
        for f in args:
            if not f.startswith('-'):
                print(f"nm: symbols of '{f}' (stub)")
        return 0

    def help(self) -> str:
        return "nm - list symbols from object files"


class ObjdumpCommand:
    """Display information from object files (objdump)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("objdump: missing file operand", file=sys.stderr)
            return 1
        for f in args:
            if not f.startswith('-'):
                print(f"objdump: info for '{f}' (stub)")
        return 0

    def help(self) -> str:
        return "objdump - display information from object files"


class SizeCommand:
    """List section sizes and total size (size)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("size: missing file operand", file=sys.stderr)
            return 1
        print("   text    data     bss     dec     hex filename")
        print("  12345    1234     567   14146    3742 stub")
        return 0

    def help(self) -> str:
        return "size - list section sizes and total size"


class StripCommand:
    """Remove symbols from binary files (strip)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        for f in args:
            if not f.startswith('-'):
                print(f"strip: stripping '{f}' (stub)")
        return 0

    def help(self) -> str:
        return "strip - remove symbols from binary files"


class M4Command:
    """GNU macro processor (m4)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("m4: GNU macro processor (stub)")
        return 0

    def help(self) -> str:
        return "m4 - macro processing language"


class FlexCommand:
    """Lexical analyzer generator (flex)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("flex: lexical analyzer generator (stub)")
        return 0

    def help(self) -> str:
        return "flex - the fast lexical analyzer generator"


class BisonCommand:
    """GNU parser generator (bison)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("bison: GNU parser generator (stub)")
        return 0

    def help(self) -> str:
        return "bison - GNU parser generator"


class MakeinfoCommand:
    """Convert Texinfo to various formats (makeinfo)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("makeinfo: Texinfo conversion (stub)")
        return 0

    def help(self) -> str:
        return "makeinfo - convert Texinfo to various formats"


class CtagsCommand:
    """Generate a tag file for use with vi/emacs (ctags)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("ctags: generating tags (stub)")
        return 0

    def help(self) -> str:
        return "ctags - generate a tag file"


class EtagsCommand:
    """Generate tag file for Emacs (etags)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("etags: generating Emacs tags (stub)")
        return 0

    def help(self) -> str:
        return "etags - generate Emacs tag file"


# ─── Editors ─────────────────────────────────────────────────────────────────

class VimCommand:
    """Vim text editor (vim)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("VIM - Vi IMproved 9.0 (stub)")
            return 0
        filename = args[-1]
        print(f"vim: editing '{filename}' (stub)")
        return 0

    def help(self) -> str:
        return "vim - Vi IMproved, a text editor"


class NanoCommand:
    """Nano text editor (nano)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("GNU nano 7.0 (stub)")
        return 0

    def help(self) -> str:
        return "nano - an enhanced free Pico clone"


class EmacsCommand:
    """GNU Emacs text editor (emacs)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("GNU Emacs 28.2 (stub)")
        return 0

    def help(self) -> str:
        return "emacs - GNU project Emacs"


class PicoCommand:
    """Pico text editor (pico)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("pico: text editor (stub)")
        return 0

    def help(self) -> str:
        return "pico - text editor"


# ─── Compression & Archive ──────────────────────────────────────────────────

class ZipCommand:
    """Package and compress files (zip)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("zip: missing archive name", file=sys.stderr)
            return 1
        print(f"zip: compressing '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "zip - package and compress files"


class UnzipCommand:
    """Extract compressed files (unzip)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("unzip: missing archive", file=sys.stderr)
            return 1
        print(f"unzip: extracting '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "unzip - extract compressed files"


class Bzip2Command:
    """Bzip2 compressor/decompressor (bzip2)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        flags = [a for a in args if a.startswith('-')]
        files = [a for a in args if not a.startswith('-')]
        if '-d' in flags:
            print(f"bzip2: decompressing (stub)")
        else:
            print(f"bzip2: compressing {len(files)} file(s) (stub)")
        return 0

    def help(self) -> str:
        return "bzip2 - a block-sorting file compressor"


class XzCommand:
    """XZ compression utility (xz)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        flags = [a for a in args if a.startswith('-')]
        if '-d' in flags:
            print("xz: decompressing (stub)")
        else:
            print("xz: compressing (stub)")
        return 0

    def help(self) -> str:
        return "xz - XZ compression utility"


class ZstdCommand:
    """Zstandard compression (zstd)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        flags = [a for a in args if a.startswith('-')]
        if '-d' in flags:
            print("zstd: decompressing (stub)")
        else:
            print("zstd: compressing (stub)")
        return 0

    def help(self) -> str:
        return "zstd - fast real-time compression algorithm"


class LzmaCommand:
    """XZ Utils and LZMA (lzma)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("lzma: LZMA compression (stub)")
        return 0

    def help(self) -> str:
        return "lzma - LZMA compression utility"


# ─── Text Processing (Missing) ──────────────────────────────────────────────

class ExpandCommand:
    """Convert tabs to spaces (expand)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        tabstop = 8
        for i, a in enumerate(args):
            if a == '-t' and i + 1 < len(args):
                tabstop = int(args[i + 1])
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    for line in fh:
                        print(line.replace('\t', ' ' * tabstop), end='')
            except FileNotFoundError:
                print(f"expand: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "expand - convert tabs to spaces"


class UnexpandCommand:
    """Convert spaces to tabs (unexpand)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        tabstop = 8
        for i, a in enumerate(args):
            if a == '-t' and i + 1 < len(args):
                tabstop = int(args[i + 1])
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    for line in fh:
                        print(line, end='')
            except FileNotFoundError:
                print(f"unexpand: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "unexpand - convert spaces to tabs"


class PrCommand:
    """Format a file for printing (pr)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    content = fh.read()
                    print(f"----- {f} -----")
                    print(content, end='')
            except FileNotFoundError:
                print(f"pr: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "pr - format a file for printing"


class PasteCommand:
    """Merge lines of files side by side (paste)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        delimiter = '\t'
        for i, a in enumerate(args):
            if a == '-d' and i + 1 < len(args):
                delimiter = args[i + 1]
        files = [a for a in args if not a.startswith('-')]
        lines_list = []
        for f in files:
            try:
                with open(f, 'r') as fh:
                    lines_list.append(fh.readlines())
            except FileNotFoundError:
                print(f"paste: {f}: No such file", file=sys.stderr)
                return 1
        if lines_list:
            max_lines = max(len(l) for l in lines_list)
            for i in range(max_lines):
                parts = []
                for lines in lines_list:
                    parts.append(lines[i].rstrip('\n') if i < len(lines) else '')
                print(delimiter.join(parts))
        return 0

    def help(self) -> str:
        return "paste - merge lines of files side by side"


class JoinCommand:
    """Join lines of two files on a common field (join)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        if len(files) < 2:
            print("join: missing file operand", file=sys.stderr)
            return 1
        print(f"join: joining '{files[0]}' and '{files[1]}' (stub)")
        return 0

    def help(self) -> str:
        return "join - join lines of two files on a common field"


class CommCommand:
    """Compare two sorted files line by line (comm)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        if len(files) < 2:
            print("comm: missing file operand", file=sys.stderr)
            return 1
        print(f"comm: comparing '{files[0]}' and '{files[1]}' (stub)")
        return 0

    def help(self) -> str:
        return "comm - compare two sorted files line by line"


class FmtCommand:
    """Simple text formatter (fmt)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        width = 75
        for i, a in enumerate(args):
            if a == '-w' and i + 1 < len(args):
                width = int(args[i + 1])
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    for line in fh:
                        print(line.rstrip())
            except FileNotFoundError:
                print(f"fmt: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "fmt - simple text formatter"


class ShredCommand:
    """Overwrite a file repeatedly to make it hard to recover (shred)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        if not files:
            print("shred: missing file operand", file=sys.stderr)
            return 1
        iterations = 3
        for i, a in enumerate(args):
            if a == '-n' and i + 1 < len(args):
                iterations = int(args[i + 1])
        for f in files:
            print(f"shred: overwriting '{f}' {iterations} times (stub)")
        return 0

    def help(self) -> str:
        return "shred - overwrite a file repeatedly"


class SplitCommand:
    """Split a file into pieces (split)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        if not files:
            print("split: missing file operand", file=sys.stderr)
            return 1
        print(f"split: splitting '{files[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "split - split a file into pieces"


class CsplitCommand:
    """Split a file by context (csplit)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        if not files:
            print("csplit: missing file operand", file=sys.stderr)
            return 1
        print(f"csplit: splitting '{files[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "csplit - split a file by context lines"


class ShufCommand:
    """Generate random permutations (shuf)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        count = 0
        for i, a in enumerate(args):
            if a == '-n' and i + 1 < len(args):
                count = int(args[i + 1])
        files = [a for a in args if not a.startswith('-')]
        if files:
            try:
                with open(files[0], 'r') as fh:
                    lines = fh.readlines()
                import random
                random.shuffle(lines)
                for line in lines[:count or len(lines)]:
                    print(line, end='')
            except FileNotFoundError:
                print(f"shuf: {files[0]}: No such file", file=sys.stderr)
                return 1
        else:
            import random
            nums = list(range(count or 10))
            random.shuffle(nums)
            for n in nums:
                print(n)
        return 0

    def help(self) -> str:
        return "shuf - generate random permutations"


class TabsCommand:
    """Set tab stop positions (tabs)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if args:
            print(f"tabs: setting tab stops to {args[0]} (stub)")
        else:
            print("tabs: 8 (default)")
        return 0

    def help(self) -> str:
        return "tabs - set tab stop positions"


class PtxCommand:
    """Produce a permuted index of a document (ptx)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            print(f"ptx: permuted index of '{f}' (stub)")
        return 0

    def help(self) -> str:
        return "ptx - produce a permuted index"


# ─── Hashing / Checksum ─────────────────────────────────────────────────────

class Md5sumCommand:
    """Compute MD5 message digest (md5sum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        if not files:
            data = sys.stdin.buffer.read() if stdin else b''
            h = hashlib.md5(data).hexdigest()
            print(f"{h}  -")
            return 0
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    h = hashlib.md5(fh.read()).hexdigest()
                print(f"{h}  {f}")
            except FileNotFoundError:
                print(f"md5sum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "md5sum - compute and check MD5 message digest"


class Sha1sumCommand:
    """Compute SHA-1 message digest (sha1sum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    h = hashlib.sha1(fh.read()).hexdigest()
                print(f"{h}  {f}")
            except FileNotFoundError:
                print(f"sha1sum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "sha1sum - compute and check SHA-1 message digest"


class Sha256sumCommand:
    """Compute SHA-256 message digest (sha256sum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    h = hashlib.sha256(fh.read()).hexdigest()
                print(f"{h}  {f}")
            except FileNotFoundError:
                print(f"sha256sum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "sha256sum - compute and check SHA-256 message digest"


class Sha512sumCommand:
    """Compute SHA-512 message digest (sha512sum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    h = hashlib.sha512(fh.read()).hexdigest()
                print(f"{h}  {f}")
            except FileNotFoundError:
                print(f"sha512sum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "sha512sum - compute and check SHA-512 message digest"


class B2sumCommand:
    """Compute BLAKE2 message digest (b2sum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    h = hashlib.blake2b(fh.read()).hexdigest()
                print(f"{h}  {f}")
            except FileNotFoundError:
                print(f"b2sum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "b2sum - compute and check BLAKE2 message digest"


class CksumCommand:
    """Compute CRC checksum (cksum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    data = fh.read()
                crc = 0
                for byte in data:
                    crc ^= byte << 24
                    for _ in range(8):
                        if crc & 0x80000000:
                            crc = (crc << 1) ^ 0x04C11DB7
                        else:
                            crc <<= 1
                        crc &= 0xFFFFFFFF
                print(f"{crc} {len(data)} {f}")
            except FileNotFoundError:
                print(f"cksum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "cksum - compute and verify checksums"


class SumCommand:
    """Print checksum and block counts (sum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    data = fh.read()
                checksum = sum(data) & 0xFFFF
                blocks = (len(data) + 1023) // 1024
                print(f"{checksum} {blocks} {f}")
            except FileNotFoundError:
                print(f"sum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "sum - compute checksum and block counts"


# ─── Encoding ────────────────────────────────────────────────────────────────

class Base32Command:
    """Base32 encode/decode (base32)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        import base64
        decode = '-d' in args or '--decode' in args
        files = [a for a in args if not a.startswith('-')]
        try:
            if decode:
                data = open(files[0], 'rb').read() if files else sys.stdin.buffer.read()
                print(base64.b32decode(data).decode(), end='')
            else:
                data = open(files[0], 'rb').read() if files else sys.stdin.buffer.read()
                print(base64.b32encode(data).decode())
        except Exception as e:
            print(f"base32: {e}", file=sys.stderr)
            return 1
        return 0

    def help(self) -> str:
        return "base32 - base32 encode/decode"


class Base64Command:
    """Base64 encode/decode (base64)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        import base64
        decode = '-d' in args or '--decode' in args
        wrap = 76
        files = [a for a in args if not a.startswith('-')]
        try:
            if decode:
                data = open(files[0], 'rb').read() if files else sys.stdin.buffer.read()
                print(base64.b64decode(data).decode(), end='')
            else:
                data = open(files[0], 'rb').read() if files else sys.stdin.buffer.read()
                encoded = base64.b64encode(data).decode()
                for i in range(0, len(encoded), wrap):
                    print(encoded[i:i + wrap])
        except Exception as e:
            print(f"base64: {e}", file=sys.stderr)
            return 1
        return 0

    def help(self) -> str:
        return "base64 - base64 encode/decode"


class OdCommand:
    """Dump files in octal and other formats (od)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        fmt = 'o'
        for a in args:
            if a.startswith('-') and len(a) > 1 and a[1] in 'odx':
                fmt = a[1]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    data = fh.read(128)
                for i in range(0, len(data), 16):
                    chunk = data[i:i + 16]
                    if fmt == 'x':
                        hex_str = ' '.join(f'{b:02x}' for b in chunk)
                        print(f"{i:07x}  {hex_str}")
                    elif fmt == 'd':
                        dec_str = ' '.join(f'{b:3d}' for b in chunk)
                        print(f"{i:07o}  {dec_str}")
                    else:
                        oct_str = ' '.join(f'{b:03o}' for b in chunk)
                        print(f"{i:07o}  {oct_str}")
            except FileNotFoundError:
                print(f"od: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "od - dump files in octal and other formats"


class HexdumpCommand:
    """Alias for od -x (hexdump)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        args = ['-x'] + args
        return OdCommand().execute(args, stdin, stdout)

    def help(self) -> str:
        return "hexdump - display file contents in hexadecimal"


# ─── System Utilities ────────────────────────────────────────────────────────

class NprocCommand:
    """Print the number of processing units (nproc)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        try:
            cpus = os.cpu_count() or 1
        except Exception:
            cpus = 1
        print(cpus)
        return 0

    def help(self) -> str:
        return "nproc - print the number of processing units"


class NumfmtCommand:
    """Convert numbers to/from human-readable (numfmt)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        to = 'si'
        for i, a in enumerate(args):
            if a == '--to' and i + 1 < len(args):
                to = args[i + 1]
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                num = int(f)
                if to == 'si' or to == 'iec':
                    suffixes = ['', 'K', 'M', 'G', 'T', 'P', 'E']
                    val = float(num)
                    for sfx in suffixes:
                        if abs(val) < 1000:
                            print(f"{val:.1f}{sfx}")
                            break
                        val /= 1000
                    else:
                        print(f"{val:.1f}{suffixes[-1]}")
                else:
                    print(num)
            except ValueError:
                print(f"numfmt: invalid number '{f}'", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "numfmt - convert numbers to/from human-readable strings"


class YesCommand:
    """Output a string repeatedly (yes)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        text = args[0] if args else 'y'
        try:
            while True:
                print(text)
        except (KeyboardInterrupt, BrokenPipeError):
            return 0

    def help(self) -> str:
        return "yes - output a string repeatedly until killed"


class GetconfCommand:
    """Get configuration variables (getconf)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("getconf: missing variable", file=sys.stderr)
            return 1
        var = args[-1]
        defaults = {
            'PATH_MAX': '4096',
            'ARG_MAX': '2097152',
            'OPEN_MAX': '1024',
            'PageSize': '4096',
        }
        print(defaults.get(var, 'undefined'))
        return 0

    def help(self) -> str:
        return "getconf - get configuration variables"


class GetentCommand:
    """Get entries from Name Service Switch (getent)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("getent: missing database/key", file=sys.stderr)
            return 1
        db = args[0]
        key = args[1]
        if db == 'passwd':
            print(f"root:x:0:0:root:/root:/bin/bash")
            print(f"admin:x:1000:1000:Admin:/home/admin:/bin/bash")
        elif db == 'group':
            print(f"root:x:0:")
            print(f"admin:x:1000:")
        else:
            print(f"getent: database '{db}' not found", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "getent - get entries from Name Service Switch libraries"


class IconvCommand:
    """Convert character encoding (iconv)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        from_enc = 'utf-8'
        to_enc = 'utf-8'
        for i, a in enumerate(args):
            if a == '-f' and i + 1 < len(args):
                from_enc = args[i + 1]
            elif a == '-t' and i + 1 < len(args):
                to_enc = args[i + 1]
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r', encoding=from_enc) as fh:
                    data = fh.read()
                print(data, end='')
            except Exception as e:
                print(f"iconv: {e}", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "iconv - convert character encoding"


class LocaleCommand:
    """Get locale-specific information (locale)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        info = {
            'LANG': 'en_US.UTF-8',
            'LC_CTYPE': 'en_US.UTF-8',
            'LC_NUMERIC': 'en_US.UTF-8',
            'LC_TIME': 'en_US.UTF-8',
            'LC_COLLATE': 'en_US.UTF-8',
            'LC_MONETARY': 'en_US.UTF-8',
            'LC_MESSAGES': 'en_US.UTF-8',
            'LC_ALL': '',
        }
        if not args or args[0] == '-a':
            for k, v in info.items():
                if v:
                    print(f"{k}=\"{v}\"")
            print(f"charmap=\"UTF-8\"")
            print(f"modifier=\"\"")
        else:
            var = args[0]
            if var in info:
                print(info[var])
            else:
                print(f"locale: '{var}' not set", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "locale - get locale-specific information"


class LocaledefCommand:
    """Compile locale definition files (localedef)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("localedef: compiling locale definition (stub)")
        return 0

    def help(self) -> str:
        return "localedef - compile locale definition files"


# ─── Install & Package ───────────────────────────────────────────────────────

class InstallCommand:
    """Copy files and set attributes (install)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("install: missing file operand", file=sys.stderr)
            return 1
        print(f"install: copying '{args[0]}' -> '{args[1]}' (stub)")
        return 0

    def help(self) -> str:
        return "install - copy files and set their attributes"


class RpmCommand:
    """RPM package manager (rpm)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("rpm: missing operand", file=sys.stderr)
            return 1
        if '-q' in args or '--query' in args:
            print("rpm-4.18.0 (stub)")
        else:
            print(f"rpm: operation '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "rpm - RPM Package Manager"


class DpkgCommand:
    """Debian package manager (dpkg)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("dpkg: missing operand", file=sys.stderr)
            return 1
        print(f"dpkg: operation '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "dpkg - Debian package manager"


class DpkgDebCommand:
    """Debian package archive tool (dpkg-deb)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("dpkg-deb: Debian package archive tool (stub)")
        return 0

    def help(self) -> str:
        return "dpkg-deb - Debian package archive tool"


class DpkgQueryCommand:
    """Debian package query tool (dpkg-query)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("dpkg-query: querying packages (stub)")
        return 0

    def help(self) -> str:
        return "dpkg-query - query the dpkg database"


class AptGetCommand:
    """APT package management (apt-get)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("apt-get: missing command", file=sys.stderr)
            return 1
        print(f"apt-get: {args[0]} (stub)")
        return 0

    def help(self) -> str:
        return "apt-get - APT package management utility"


class YumCommand:
    """Yellowdog Updater Modified (yum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("yum: missing command", file=sys.stderr)
            return 1
        print(f"yum: {args[0]} (stub)")
        return 0

    def help(self) -> str:
        return "yum - Yellowdog Updater Modified"


class DnfCommand:
    """Dandified YUM (dnf)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("dnf: missing command", file=sys.stderr)
            return 1
        print(f"dnf: {args[0]} (stub)")
        return 0

    def help(self) -> str:
        return "dnf - Dandified YUM"


# ─── Process & Scheduling ───────────────────────────────────────────────────

class AtCommand:
    """Schedule a command for later execution (at)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("at: missing time specification", file=sys.stderr)
            return 1
        print(f"at: scheduling job for '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "at - schedule a command for later execution"


class AtqCommand:
    """List pending at jobs (atq)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("No pending jobs.")
        return 0

    def help(self) -> str:
        return "atq - list pending at jobs"


class AtrmCommand:
    """Remove an at job (atrm)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("atrm: missing job number", file=sys.stderr)
            return 1
        print(f"atrm: removing job {args[0]} (stub)")
        return 0

    def help(self) -> str:
        return "atrm - remove a job from the at queue"


class CrontabCommand:
    """Edit crontab files (crontab)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("crontab: no command specified (use -l, -e, or -r)")
            return 0
        if '-l' in args:
            print("no crontab for current user")
        elif '-e' in args:
            print("crontab: opening editor (stub)")
        elif '-r' in args:
            print("crontab: removing crontab (stub)")
        else:
            print(f"crontab: processing '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "crontab - maintain crontab files"


class PmapCommand:
    """Report memory map of a process (pmap)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("pmap: missing PID", file=sys.stderr)
            return 1
        print(f"pmap: memory map of PID {args[0]} (stub)")
        return 0

    def help(self) -> str:
        return "pmap - report memory map of a process"


class LsofCommand:
    """List open files (lsof)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("COMMAND   PID  USER   FD   TYPE DEVICE SIZE/OFF  NODE NAME")
        print("bash      123  root  cwd    DIR    8,1     4096 123456 /root")
        return 0

    def help(self) -> str:
        return "lsof - list open files"


class IostatCommand:
    """Report I/O statistics (iostat)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        interval = int(args[0]) if args and args[0].isdigit() else 0
        print(f"UmerOS  (stub)")
        print()
        print("Device             tps    kB_read/s    kB_wrtn/s    kB_read    kB_wrtn")
        print("sda              12.34         0.56         2.34     123456     567890")
        return 0

    def help(self) -> str:
        return "iostat - report I/O statistics"


class VmstatCommand:
    """Report virtual memory statistics (vmstat)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----")
        print(" r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st")
        print(" 0  0      0 123456  1234  12345    0    0     0     0    0    0  0  0 100  0  0")
        return 0

    def help(self) -> str:
        return "vmstat - report virtual memory statistics"


class LtraceCommand:
    """Trace library calls (ltrace)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("ltrace: missing command", file=sys.stderr)
            return 1
        print(f"ltrace: tracing '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "ltrace - trace library calls"


class PstreeCommand:
    """Display process tree (pstree)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("systemd─┬─NetworkManager───2*[{NetworkManager}]")
        print("        ├─sshd───sshd───bash───pstree")
        print("        └─2*[{systemd}]")
        return 0

    def help(self) -> str:
        return "pstree - display a tree of processes"


class RunuserCommand:
    """Run a command as a different user (runuser)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        user = 'root'
        for i, a in enumerate(args):
            if a == '-u' and i + 1 < len(args):
                user = args[i + 1]
        if args:
            print(f"runuser: running '{' '.join(args)}' as {user} (stub)")
        return 0

    def help(self) -> str:
        return "runuser - run a command with substitute user and group ID"


class SudoCommand:
    """Execute a command as another user (sudo)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("usage: sudo [-h] command")
            return 1
        print(f"sudo: executing '{' '.join(args)}' (stub)")
        return 0

    def help(self) -> str:
        return "sudo - execute a command as another user"


# ─── Network Utilities ───────────────────────────────────────────────────────

class NcCommand:
    """TCP/UDP connection utility (nc/ncat)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("nc: missing host/port", file=sys.stderr)
            return 1
        print(f"nc: connecting to {args[0]}:{args[1]} (stub)")
        return 0

    def help(self) -> str:
        return "nc - TCP/UDP connection utility"


class NcatCommand:
    """Nmap netcat (ncat)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        return NcCommand().execute(args, stdin, stdout)

    def help(self) -> str:
        return "ncat - nmap netcat"


class SocatCommand:
    """Multipurpose relay (socat)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("socat: missing address specification", file=sys.stderr)
            return 1
        print(f"socat: relay between '{args[0]}' and '{args[1]}' (stub)")
        return 0

    def help(self) -> str:
        return "socat - multipurpose relay"


class LsofNetworkCommand:
    """List network connections (ss)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("State    Recv-Q Send-Q  Local Address:Port   Peer Address:Port  Process")
        print("LISTEN   0      128     0.0.0.0:22           0.0.0.0:*")
        print("ESTAB    0      0       192.168.1.1:22       192.168.1.100:54321")
        return 0

    def help(self) -> str:
        return "ss - socket statistics"


class TracepathCommand:
    """Trace path to a destination discovering MTU (tracepath)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("tracepath: missing destination", file=sys.stderr)
            return 1
        print(f" 1: no reply")
        print(f" 2: 8.8.8.8              12.345ms  pmtu 1500")
        print(f" 3: 8.8.4.4              15.678ms")
        print(f"     Resume: pmtu 1500 hops 3 back 15.678ms")
        return 0

    def help(self) -> str:
        return "tracepath - trace path to destination discovering MTU"


class HostnameCommand:
    """Print or set the system's hostname (hostname)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("umeeros")
        else:
            print(f"hostname: setting hostname to '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "hostname - print or set the system's hostname"


# ─── Misc Utilities ──────────────────────────────────────────────────────────

class ScriptCommand:
    """Record a terminal session (script)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        outfile = args[0] if args else 'typescript'
        print(f"Script started, output file is '{outfile}'")
        print("Script done.")
        return 0

    def help(self) -> str:
        return "script - record a terminal session"


class ScriptreplayCommand:
    """Replay a terminal session (scriptreplay)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("scriptreplay: missing timing file", file=sys.stderr)
            return 1
        print(f"scriptreplay: replaying '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "scriptreplay - replay terminal session recordings"


class WatchCommand:
    """Execute a program periodically (watch)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        interval = 2
        for i, a in enumerate(args):
            if a == '-n' and i + 1 < len(args):
                interval = int(args[i + 1])
        cmd = ' '.join(a for a in args if not a.startswith('-'))
        print(f"Every {interval}.0s: {cmd}")
        return 0

    def help(self) -> str:
        return "watch - execute a program periodically"


class ColumnCommand:
    """Columnate lists (column)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("NAME      TYPE      SIZE")
        print("alpha     string    100")
        print("beta      int       4")
        return 0

    def help(self) -> str:
        return "column - columnate lists"


class TreeCommand:
    """List contents of directories in a tree-like format (tree)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        path = args[0] if args else '.'
        print(f"{path}")
        print("├── file1.txt")
        print("├── file2.py")
        print("└── subdir")
        return 0

    def help(self) -> str:
        return "tree - list contents in a tree-like format"


class LsbReleaseCommand:
    """Standard Base information (lsb_release)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if '-a' in args or '--all' in args:
            print("Distributor ID: UmerOS")
            print("Description:    UmerOS 1.0")
            print("Release:        1.0")
            print("Codename:       umeeros")
        elif '-i' in args:
            print("Distributor ID: UmerOS")
        elif '-d' in args:
            print("Description:    UmerOS 1.0")
        elif '-r' in args:
            print("Release:        1.0")
        elif '-c' in args:
            print("Codename:       umeeros")
        else:
            print("LSB Version:    :core-4.1-amd64:core-4.1-noarch")
        return 0

    def help(self) -> str:
        return "lsb_release - Standard Base information"


class PwdxCommand:
    """Report current working directory of a process (pwdx)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("pwdx: missing PID", file=sys.stderr)
            return 1
        for pid in args:
            print(f"{pid}: /root")
        return 0

    def help(self) -> str:
        return "pwdx - report current working directory of a process"


class ChrootCommand:
    """Run a command with a different root directory (chroot)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("chroot: missing new root", file=sys.stderr)
            return 1
        print(f"chroot: entering '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "chroot - run command with a different root directory"


class InstallInfoCommand:
    """Maintain info page files (install-info)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("install-info: maintaining info pages (stub)")
        return 0

    def help(self) -> str:
        return "install-info - maintain info page files"


class ManCommand:
    """Display manual pages (man)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("What manual page do you want?")
            return 1
        print(f"man: manual page for '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "man - display manual pages"


class WhatisCommand:
    """Search the manual page names and descriptions (whatis)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        for a in args:
            print(f"{a} (1)             - stub description")
        return 0

    def help(self) -> str:
        return "whatis - display manual page descriptions"


class AproposCommand:
    """Search the manual page names and descriptions (apropos)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("apropos: searching manual pages (stub)")
        return 0

    def help(self) -> str:
        return "apropos - search manual page descriptions"


class TputCommand:
    """Modify a terminal's I/O (tput)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("tput: missing operand", file=sys.stderr)
            return 1
        op = args[0]
        if op == 'cols':
            print('80')
        elif op == 'lines':
            print('24')
        elif op == 'bold':
            print('\033[1m', end='')
        elif op == 'sgr0':
            print('\033[0m', end='')
        elif op == 'setaf':
            color = int(args[1]) if len(args) > 1 else 0
            print(f'\033[{30 + color}m', end='')
        elif op == 'setab':
            color = int(args[1]) if len(args) > 1 else 0
            print(f'\033[{40 + color}m', end='')
        else:
            print(f"tput: unknown capability '{op}' (stub)")
        return 0

    def help(self) -> str:
        return "tput - modify terminal characteristics"


class ResetCommand:
    """Terminal reset (reset)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("\033c", end='')
        return 0

    def help(self) -> str:
        return "reset - terminal reset"


class ClearCommand:
    """Clear the terminal (clear)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("\033[2J\033[H", end='')
        return 0

    def help(self) -> str:
        return "clear - clear the terminal"


class TestCommand:
    """Evaluate conditional expression (test/[)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args or args == [']']:
            return 0
        if len(args) == 1:
            return 0 if args[0] else 1
        return 0

    def help(self) -> str:
        return "test - evaluate conditional expressions"


class TrueCommand:
    """Return true (true)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        return 0

    def help(self) -> str:
        return "true - do nothing, successfully"


class FalseCommand:
    """Return false (false)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        return 1

    def help(self) -> str:
        return "false - do nothing, unsuccessfully"


class TestBraceCommand:
    """Evaluate conditional expression ([)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if args and args[-1] == ']':
            args = args[:-1]
        return TestCommand().execute(args, stdin, stdout)

    def help(self) -> str:
        return "[ - evaluate conditional expression"


class HostidCommand:
    """Print the numeric identifier for the current host (hostid)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        import random
        print(f"{random.randint(0, 0xFFFFFFFF):08x}")
        return 0

    def help(self) -> str:
        return "hostid - print the numeric host identifier"


class LognameCommand:
    """Print login name of the current user (logname)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print(os.environ.get('USER', os.environ.get('LOGNAME', 'admin')))
        return 0

    def help(self) -> str:
        return "logname - print login name"


class TtyCommand:
    """Print file name of the terminal connected to standard input (tty)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if os.isatty(0):
            print("/dev/pts/0")
        else:
            print("not a tty")
            return 1
        return 0

    def help(self) -> str:
        return "tty - print terminal name"


class XdgOpenCommand:
    """Open a file or URL with the default application (xdg-open)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("xdg-open: missing file/URL", file=sys.stderr)
            return 1
        print(f"xdg-open: opening '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "xdg-open - open a file or URL"


class XdgUserDirsCommand:
    """Get XDG user directories (xdg-user-dirs)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        dirs = {
            'DESKTOP': '~/Desktop',
            'DOCUMENTS': '~/Documents',
            'DOWNLOAD': '~/Downloads',
            'MUSIC': '~/Music',
            'PICTURES': '~/Pictures',
            'PUBLICSHARE': '~/Public',
            'TEMPLATES': '~/Templates',
            'VIDEOS': '~/Videos',
        }
        for key, val in dirs.items():
            print(f'XDG_{key}_DIR="{val}"')
        return 0

    def help(self) -> str:
        return "xdg-user-dirs - manage XDG user directories"


class ReadelfCommand:
    """Display information about ELF files (readelf)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("readelf: missing file operand", file=sys.stderr)
            return 1
        print(f"ELF Header for '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "readelf - display information about ELF files"


class ObjcopyCommand:
    """Copy and translate object files (objcopy)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("objcopy: missing input/output files", file=sys.stderr)
            return 1
        print(f"objcopy: '{args[0]}' -> '{args[1]}' (stub)")
        return 0

    def help(self) -> str:
        return "objcopy - copy and translate object files"


class Addr2lineCommand:
    """Convert addresses to file names and line numbers (addr2line)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("addr2line: missing address", file=sys.stderr)
            return 1
        print(f"???:0")
        return 0

    def help(self) -> str:
        return "addr2line - convert addresses to file names and line numbers"


class GprofCommand:
    """Profile a program (gprof)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("gprof: profiling (stub)")
        return 0

    def help(self) -> str:
        return "gprof - display profiling data"


class ValgrindCommand:
    """Detect memory management errors (valgrind)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("valgrind: missing command", file=sys.stderr)
            return 1
        print(f"valgrind: running '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "valgrind - a Build Framework for Valgrind tools"


class StraceCommand:
    """Trace system calls (strace)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("strace: missing command", file=sys.stderr)
            return 1
        print(f"strace: tracing '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "strace - trace system calls"


class TcpdumpCommand:
    """Dump traffic on a network (tcpdump)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("tcpdump: verbose output suppressed (stub)")
        print("listening on eth0, link-type EN10MB, capture length 262144 bytes")
        return 0

    def help(self) -> str:
        return "tcpdump - dump traffic on a network"


class DigCommand:
    """DNS lookup utility (dig)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("dig: missing domain", file=sys.stderr)
            return 1
        domain = args[0]
        print(f";; QUESTION SECTION:")
        print(f";; {domain}.           IN      A")
        print()
        print(f";; ANSWER SECTION:")
        print(f"{domain}.    300     IN      A       93.184.216.34")
        return 0

    def help(self) -> str:
        return "dig - DNS lookup utility"


class NslookupCommand:
    """Query Internet name servers (nslookup)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("nslookup: missing domain", file=sys.stderr)
            return 1
        domain = args[0]
        print(f"Server:         8.8.8.8")
        print(f"Address:        8.8.8.8#53")
        print()
        print(f"Non-authoritative answer:")
        print(f"Name:   {domain}")
        print(f"Address: 93.184.216.34")
        return 0

    def help(self) -> str:
        return "nslookup - query Internet name servers"


class HostCommand:
    """DNS lookup utility (host)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("host: missing domain", file=sys.stderr)
            return 1
        print(f"{args[0]} has address 93.184.216.34")
        return 0

    def help(self) -> str:
        return "host - DNS lookup utility"


class WgetCommand:
    """Download files from the web (wget)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("wget: missing URL", file=sys.stderr)
            return 1
        url = args[-1]
        print(f"Resolving {url}... (stub)")
        print(f"Connecting to {url}... connected.")
        print(f"HTTP request sent, awaiting response... 200 OK")
        print(f"Length: 1234 (1.2K) [text/html]")
        print(f"Saving to: '{url.split('/')[-1]}'")
        print(f"100%[================================>] 1,234  --.-KB/s    in 0s")
        print(f"2024-01-01 00:00:00 (12.3 MB/s) - saved")
        return 0

    def help(self) -> str:
        return "wget - download files from the web"


class CurlCommand:
    """Transfer a URL (curl)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("curl: missing URL", file=sys.stderr)
            return 1
        url = args[-1]
        if '-I' in args or '--head' in args:
            print(f"HTTP/1.1 200 OK")
            print(f"Content-Type: text/html")
            print(f"Content-Length: 1234")
        elif '-v' in args:
            print(f"* Trying {url}...")
            print(f"* Connected to {url} port 80")
            print(f"> GET / HTTP/1.1")
            print(f"< HTTP/1.1 200 OK")
        else:
            print(f"<!DOCTYPE html><html><body>stub</body></html>")
        return 0

    def help(self) -> str:
        return "curl - transfer a URL"


# ─── Process Info (Additional) ───────────────────────────────────────────────

class TimeCommand:
    """Run a command and summarize system resource usage (time)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("time: missing command", file=sys.stderr)
            return 1
        print(f"real    0m0.001s")
        print(f"user    0m0.000s")
        print(f"sys     0m0.000s")
        return 0

    def help(self) -> str:
        return "time - run commands and summarize time"


class UptimeCommand:
    """Show how long the system has been running (uptime)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print(" 00:00:01 up 1 day,  2:30,  1 user,  load average: 0.00, 0.01, 0.05")
        return 0

    def help(self) -> str:
        return "uptime - show how long the system has been running"


class FreeCommand:
    """Display amount of free and used memory (free)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        fmt = '-m' if '-m' in args or '--mega' in args else '-k' if '-k' in args else '-g' if '-g' in args else '-b'
        unit = 'Mi' if fmt == '-m' else 'Ki' if fmt == '-k' else 'Gi' if fmt == '-g' else 'B'
        print(f"               total        used        free      shared  buff/cache   available")
        print(f"{unit:>8}:      16384        8192        4096         256        4096        8192")
        return 0

    def help(self) -> str:
        return "free - display memory usage"


class DfCommand:
    """Report filesystem disk space usage (df)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("Filesystem     1K-blocks    Used Available Use% Mounted on")
        print("/dev/sda1       52428800 26214400  26214400  50% /")
        return 0

    def help(self) -> str:
        return "df - report filesystem disk space usage"


class DuCommand:
    """Estimate file space usage (du)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        if not files:
            files = ['.']
        for f in files:
            print(f"4\t{f}")
        return 0

    def help(self) -> str:
        return "du - estimate file space usage"


class FindCommand:
    """Search for files in a directory hierarchy (find)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            args = ['.']
        print(f"find: searching from '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "find - search for files in a directory hierarchy"


class XargsCommand:
    """Build and execute command lines (xargs)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("xargs: missing command", file=sys.stderr)
            return 1
        print(f"xargs: executing '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "xargs - build and execute command lines"


class IdCommand:
    """Print real and effective user and group IDs (id)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("uid=0(root) gid=0(root) groups=0(root)")
        return 0

    def help(self) -> str:
        return "id - print user identity"


class WhoCommand:
    """Show who is logged in (who)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("root     pts/0        2024-01-01 00:00 (192.168.1.100)")
        return 0

    def help(self) -> str:
        return "who - show who is logged in"


class WCommand:
    """Show who is logged in and what they are doing (w)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print(" 00:00:01 up 1 day,  2:30,  1 user,  load average: 0.00, 0.01, 0.05")
        print("USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT")
        print("root     pts/0    192.168.1.100    00:00    0.00s  0.01s  0.00s w")
        return 0

    def help(self) -> str:
        return "w - show who is logged in and what they are doing"


class LastCommand:
    """Show listing of last logged in users (last)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("root     pts/0        192.168.1.100    Mon Jan  1 08:00   still logged in")
        print("admin    pts/1        192.168.1.100    Mon Jan  1 09:30   still logged in")
        print()
        print("wtmp begins Mon Jan  1 00:00:00 2024")
        return 0

    def help(self) -> str:
        return "last - show listing of last logged in users"


class PatchCommand:
    """Apply a diff file to produce a patch (patch)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("patch: missing input file", file=sys.stderr)
            return 1
        print(f"patch: processing '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "patch - apply a diff file to produce a patch"


class LocateCommand:
    """List files in databases that match a pattern (locate)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("locate: missing pattern", file=sys.stderr)
            return 1
        pattern = args[-1]
        print(f"locate: searching for '{pattern}' in mlocate.db (stub)")
        print(f"/etc/passwd")
        print(f"/home/admin/.bashrc")
        print(f"/usr/bin/{pattern}")
        return 0

    def help(self) -> str:
        return "locate - list files in databases that match a pattern"


class UpdatedbCommand:
    """Update a database for locate (updatedb)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("updatedb: scanning filesystem (stub)")
        return 0

    def help(self) -> str:
        return "updatedb - update a database for locate"


class FileCommand:
    """Determine file type (file)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("file: missing operand", file=sys.stderr)
            return 1
        for f in args:
            print(f"{f}: ASCII text")
        return 0

    def help(self) -> str:
        return "file - determine file type"


class StatCommand:
    """Display file or filesystem status (stat)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("stat: missing operand", file=sys.stderr)
            return 1
        print(f"  File: {args[0]}")
        print(f"  Size: 1234 Blocks: 8 IO Block: 4096 regular file")
        print(f"Access: (0644/-rw-r--r--) Uid: ( 0/ root) Gid: ( 0/ root)")
        return 0

    def help(self) -> str:
        return "stat - display file or filesystem status"


class DiffCommand:
    """Compare files line by line (diff)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("diff: missing operand", file=sys.stderr)
            return 1
        print(f"--- {args[0]}")
        print(f"+++ {args[1]}")
        print(f"@@ -1 +1 @@")
        print(f"-old line")
        print(f"+new line")
        return 1

    def help(self) -> str:
        return "diff - compare files line by line"


class AwkCommand:
    """Pattern scanning and processing language (awk)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("awk: pattern scanning (stub)")
        return 0

    def help(self) -> str:
        return "awk - pattern scanning and processing language"


class GrepCommand:
    """Print lines that match patterns (grep)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("grep: missing pattern", file=sys.stderr)
            return 1
        pattern = args[0]
        files = [a for a in args[1:] if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    for line in fh:
                        if pattern in line:
                            print(line, end='')
            except FileNotFoundError:
                print(f"grep: {f}: No such file", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "grep - print lines matching patterns"


class LessCommand:
    """View file contents with paging (less)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("less: missing file", file=sys.stderr)
            return 1
        try:
            with open(args[0], 'r') as fh:
                print(fh.read(), end='')
        except FileNotFoundError:
            print(f"less: {args[0]}: No such file", file=sys.stderr)
            return 1
        return 0

    def help(self) -> str:
        return "less - view file contents"


class HeadCommand:
    """Output the first lines of files (head)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        n = 10
        for i, a in enumerate(args):
            if a == '-n' and i + 1 < len(args):
                n = int(args[i + 1])
            elif a.startswith('-') and a[1:].isdigit():
                n = int(a[1:])
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    for i, line in enumerate(fh):
                        if i >= n:
                            break
                        print(line, end='')
            except FileNotFoundError:
                print(f"head: {f}: No such file", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "head - output the first lines of files"


class TailCommand:
    """Output the last lines of files (tail)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        n = 10
        for i, a in enumerate(args):
            if a == '-n' and i + 1 < len(args):
                n = int(args[i + 1])
            elif a.startswith('-') and a[1:].isdigit():
                n = int(a[1:])
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    lines = fh.readlines()
                    for line in lines[-n:]:
                        print(line, end='')
            except FileNotFoundError:
                print(f"tail: {f}: No such file", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "tail - output the last lines of files"


class CutCommand:
    """Remove sections from each line of files (cut)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("cut: removing sections (stub)")
        return 0

    def help(self) -> str:
        return "cut - remove sections from each line"


class SortCommand:
    """Sort lines of text files (sort)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        lines = []
        for f in files:
            try:
                with open(f, 'r') as fh:
                    lines.extend(fh.readlines())
            except FileNotFoundError:
                print(f"sort: {f}: No such file", file=sys.stderr)
        lines.sort()
        for line in lines:
            print(line, end='')
        return 0

    def help(self) -> str:
        return "sort - sort lines of text files"


class UniqCommand:
    """Filter adjacent matching lines from INPUT (uniq)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        prev = None
        for f in files:
            try:
                with open(f, 'r') as fh:
                    for line in fh:
                        if line != prev:
                            print(line, end='')
                            prev = line
            except FileNotFoundError:
                print(f"uniq: {f}: No such file", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "uniq - filter adjacent matching lines"


class TrCommand:
    """Translate or delete characters (tr)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 2:
            print("tr: missing operand", file=sys.stderr)
            return 1
        print(f"tr: translating '{args[0]}' -> '{args[1]}' (stub)")
        return 0

    def help(self) -> str:
        return "tr - translate or delete characters"


class TeeCommand:
    """Read from standard input and write to standard output and files (tee)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        append = '-a' in args
        files = [a for a in args if not a.startswith('-')]
        data = stdin if stdin else ''
        if isinstance(data, str):
            print(data, end='')
            for f in files:
                mode = 'a' if append else 'w'
                with open(f, mode) as fh:
                    fh.write(data)
        return 0

    def help(self) -> str:
        return "tee - read stdin and write to stdout and files"


class WcCommand:
    """Word, line, character, and byte count (wc)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'r') as fh:
                    content = fh.read()
                lines = content.count('\n')
                words = len(content.split())
                chars = len(content)
                print(f" {lines} {words} {chars} {f}")
            except FileNotFoundError:
                print(f"wc: {f}: No such file", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "wc - word, line, character, and byte count"


class WhichCommand:
    """Locate a command (which)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        for cmd in args:
            print(f"/usr/bin/{cmd}")
        return 0

    def help(self) -> str:
        return "which - locate a command"


class WhoamiCommand:
    """Print effective userid (whoami)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print(os.environ.get('USER', 'admin'))
        return 0

    def help(self) -> str:
        return "whoami - print effective userid"


class GroupsCommand:
    """Print groups of which the user is a member (groups)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("root admin")
        return 0

    def help(self) -> str:
        return "groups - print group memberships"


class BasenameCommand:
    """Strip directory and suffix from filenames (basename)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("basename: missing operand", file=sys.stderr)
            return 1
        path = args[0]
        suffix = args[1] if len(args) > 1 else ''
        name = path.split('/')[-1].split('\\')[-1]
        if suffix and name.endswith(suffix):
            name = name[:-len(suffix)]
        print(name)
        return 0

    def help(self) -> str:
        return "basename - strip directory and suffix"


class DirnameCommand:
    """Strip last component from file name (dirname)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("dirname: missing operand", file=sys.stderr)
            return 1
        path = args[0].replace('\\', '/')
        if '/' in path:
            print(path.rsplit('/', 1)[0] or '/')
        else:
            print('.')
        return 0

    def help(self) -> str:
        return "dirname - strip last component from file name"


class ReadlinkCommand:
    """Print value of a symbolic link (readlink)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("readlink: missing operand", file=sys.stderr)
            return 1
        target = os.readlink(args[0]) if os.path.islink(args[0]) else args[0]
        print(target)
        return 0

    def help(self) -> str:
        return "readlink - print value of a symbolic link"


class RealpathCommand:
    """Print the resolved file path (realpath)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("realpath: missing operand", file=sys.stderr)
            return 1
        print(os.path.realpath(args[0]))
        return 0

    def help(self) -> str:
        return "realpath - print resolved file path"


class TouchCommand:
    """Change file timestamps (touch)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        for f in args:
            if not f.startswith('-'):
                try:
                    with open(f, 'a'):
                        os.utime(f, None)
                except Exception:
                    pass
        return 0

    def help(self) -> str:
        return "touch - change file timestamps"


class ReniceCommand:
    """Alter priority of running processes (renice)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if len(args) < 1:
            print("renice: missing priority", file=sys.stderr)
            return 1
        print(f"renice: altering priority (stub)")
        return 0

    def help(self) -> str:
        return "renice - alter priority of running processes"


class NiceCommand:
    """Run a command with modified scheduling priority (nice)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        increment = 10
        for i, a in enumerate(args):
            if a == '-n' and i + 1 < len(args):
                increment = int(args[i + 1])
        cmd = [a for a in args if not a.startswith('-') and a != str(increment)]
        print(f"nice: running with priority +{increment} (stub)")
        return 0

    def help(self) -> str:
        return "nice - run a command with modified priority"


class TimeoutCommand:
    """Run a command with a time limit (timeout)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        duration = '10s'
        for i, a in enumerate(args):
            if a.startswith('--signal'):
                pass
            elif not a.startswith('-') and i == 0:
                duration = a
        print(f"timeout: running with {duration} limit (stub)")
        return 0

    def help(self) -> str:
        return "timeout - run a command with a time limit"


class NohupCommand:
    """Run a command immune to hangups (nohup)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("nohup: missing command", file=sys.stderr)
            return 1
        print(f"nohup: running '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "nohup - run a command immune to hangups"


class TasksetCommand:
    """Retrieve or set a process's CPU affinity (taskset)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("taskset: setting CPU affinity (stub)")
        return 0

    def help(self) -> str:
        return "taskset - retrieve or set a process's CPU affinity"


class NsenterCommand:
    """Run an command with namespace of other processes (nsenter)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("nsenter: missing command", file=sys.stderr)
            return 1
        print(f"nsenter: running '{args[-1]}' in namespace (stub)")
        return 0

    def help(self) -> str:
        return "nsenter - run command with namespaces of other processes"


class PgrepCommand:
    """Look up processes by name (pgrep)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("pgrep: missing pattern", file=sys.stderr)
            return 1
        print("1")
        return 0

    def help(self) -> str:
        return "pgrep - look up processes by name"


class PkillCommand:
    """Signal processes based on name (pkill)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("pkill: missing pattern", file=sys.stderr)
            return 1
        print(f"pkill: signaling processes matching '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "pkill - signal processes based on name"


class MesgCommand:
    """Display or control access to terminal (mesg)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("is y")
        elif args[0] == 'y':
            print("mesg: is y")
        elif args[0] == 'n':
            print("mesg: is n")
        else:
            print("Usage: mesg [y|n]")
        return 0

    def help(self) -> str:
        return "mesg - display or control access to terminal"


class ChfnCommand:
    """Change finger information (chfn)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("chfn: changing finger information (stub)")
        return 0

    def help(self) -> str:
        return "chfn - change finger information"


class ChshCommand:
    """Change login shell (chsh)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        shell = args[0] if args else '/bin/bash'
        print(f"chsh: shell changed to '{shell}' (stub)")
        return 0

    def help(self) -> str:
        return "chsh - change login shell"


class ChageCommand:
    """Change user password expiry information (chage)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("chage: changing password expiry (stub)")
        return 0

    def help(self) -> str:
        return "chage - change user password expiry information"


class GpasswdCommand:
    """Administer the /etc/group file (gpasswd)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("gpasswd: administering group (stub)")
        return 0

    def help(self) -> str:
        return "gpasswd - administer /etc/group"


class NewgrpCommand:
    """Log in to a new group (newgrp)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        group = args[0] if args else 'root'
        print(f"newgrp: logging in to group '{group}' (stub)")
        return 0

    def help(self) -> str:
        return "newgrp - log in to a new group"


class UseraddCommand:
    """Create a new user (useradd)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        username = args[-1] if args else 'newuser'
        print(f"useradd: user '{username}' created (stub)")
        return 0

    def help(self) -> str:
        return "useradd - create a new user"


class UsermodCommand:
    """Modify a user account (usermod)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("usermod: modifying user account (stub)")
        return 0

    def help(self) -> str:
        return "usermod - modify a user account"


class UserdelCommand:
    """Delete a user account (userdel)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        username = args[-1] if args else 'olduser'
        print(f"userdel: user '{username}' deleted (stub)")
        return 0

    def help(self) -> str:
        return "userdel - delete a user account"


class GroupaddCommand:
    """Create a new group (groupadd)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        groupname = args[-1] if args else 'newgroup'
        print(f"groupadd: group '{groupname}' created (stub)")
        return 0

    def help(self) -> str:
        return "groupadd - create a new group"


class GroupdelCommand:
    """Delete a group (groupdel)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        groupname = args[-1] if args else 'oldgroup'
        print(f"groupdel: group '{groupname}' deleted (stub)")
        return 0

    def help(self) -> str:
        return "groupdel - delete a group"


class GroupmodCommand:
    """Modify a group definition (groupmod)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        print("groupmod: modifying group (stub)")
        return 0

    def help(self) -> str:
        return "groupmod - modify a group definition"


class NewgrpCommand2:
    """Log in to a new group (newgrp)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        group = args[0] if args else 'root'
        print(f"newgrp: logging in to group '{group}' (stub)")
        return 0

    def help(self) -> str:
        return "newgrp - log in to a new group"


# ─── Misc Tools ──────────────────────────────────────────────────────────────

class CksumCommand:
    """Compute CRC checksum (cksum)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        files = [a for a in args if not a.startswith('-')]
        for f in files:
            try:
                with open(f, 'rb') as fh:
                    data = fh.read()
                checksum = sum(data) & 0xFFFFFFFF
                blocks = (len(data) + 1023) // 1024
                print(f"{checksum} {blocks} {f}")
            except FileNotFoundError:
                print(f"cksum: {f}: No such file", file=sys.stderr)
                return 1
        return 0

    def help(self) -> str:
        return "cksum - compute and verify checksums"


class DpkgCommand:
    """Debian package manager (dpkg)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("dpkg: missing operand", file=sys.stderr)
            return 1
        if '-l' in args or '--list' in args:
            print("dpkg: listing installed packages (stub)")
        else:
            print(f"dpkg: operation '{args[0]}' (stub)")
        return 0

    def help(self) -> str:
        return "dpkg - Debian package manager"
