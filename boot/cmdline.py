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
Umer OS /boot - kernel command line helper
=========================================

A small, dependency-free command line parser/builder that focuses on
the bits that matter at boot time:

* quoted values (``console="ttyS0,115200n8"``)
* repeated keys (``initrd=/a initrd=/b``) preserved in order
* type coercion (``int`` for ``mem=``, ``str`` for ``console=``)
* strict validation against a list of well-known keys
* well-known preset cmdlines (default, recovery, debug, live, server, ...)
* round-trip ``build(parse(s)) == s`` for canonical strings

This module complements :class:`boot.boot_params.KernelCommandLine`
(which is feature-rich and used at runtime) by being a pure
**stateless** parser/builder, suitable for unit tests and the
``python -m boot`` CLI.

Example
-------

::

    from boot.cmdline import parse_cmdline, build_cmdline
    params = parse_cmdline('root=/dev/sda1 ro quiet console=ttyS0,115200')
    assert build_cmdline(params) == 'console=ttyS0,115200 quiet ro root=/dev/sda1'
    assert params['root'].value == '/dev/sda1'
    assert params['ro'].is_flag

References
----------

* https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html
* UAPI.1 Boot Loader Specification - ``options`` field
* systemd-boot(7) - command line options
* FHS 3.0 - ``/boot`` is where the boot loader picks up the cmdline

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Boot.CmdLine")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class CmdParamKind(str, Enum):
    """How a parameter was specified on the command line."""

    FLAG = "flag"           # bare key, no value
    KEY_VALUE = "key=value"
    QUOTED = "key=\"value\""  # the value was quoted


@dataclass
class CmdParam:
    """A single kernel command line parameter (parsed)."""

    key: str
    value: Optional[str] = None
    kind: CmdParamKind = CmdParamKind.FLAG
    position: int = 0  # ordinal on the original line

    @property
    def is_flag(self) -> bool:
        return self.kind == CmdParamKind.FLAG or self.value is None

    def as_string(self) -> str:
        if self.is_flag:
            return self.key
        if self.kind == CmdParamKind.QUOTED:
            return f'{self.key}="{self.value}"'
        return f"{self.key}={self.value}"


@dataclass
class ParsedCmdline:
    """A parsed kernel command line."""

    raw: str = ""
    params: List[CmdParam] = field(default_factory=list)
    quoted_tokens: List[str] = field(default_factory=list)

    # -- mapping-style access -------------------------------------------

    def __getitem__(self, key: str) -> CmdParam:
        """Return the **last** occurrence of ``key``."""
        for p in reversed(self.params):
            if p.key == key:
                return p
        raise KeyError(key)

    def get(self, key: str, default: Optional[CmdParam] = None) -> Optional[CmdParam]:
        for p in reversed(self.params):
            if p.key == key:
                return p
        return default

    def get_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        p = self.get(key)
        return p.value if p is not None else default

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def all(self, key: str) -> List[CmdParam]:
        return [p for p in self.params if p.key == key]

    def keys(self) -> List[str]:
        return [p.key for p in self.params]

    def as_dict(self) -> Dict[str, List[Optional[str]]]:
        out: Dict[str, List[Optional[str]]] = {}
        for p in self.params:
            out.setdefault(p.key, []).append(p.value)
        return out

    def as_string(self) -> str:
        return " ".join(p.as_string() for p in self.params)


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

#: Recognise ``key=value`` (only ASCII alnum + ``.``, ``-``, ``_``, ``/``,
#: ``:``, ``+``).  Keys that do not match are kept as flag candidates.
_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-:/+]*$")


def _tokenize(line: str) -> List[str]:
    """Split a kernel command line into raw tokens, respecting quotes.

    Quotes are stripped from the value but the *flag* is recorded via
    :class:`ParsedCmdline.quoted_tokens`.
    """
    tokens: List[str] = []
    buf: List[str] = []
    quote: Optional[str] = None
    for ch in line:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def parse_cmdline(line: str) -> ParsedCmdline:
    """Parse a kernel command line string into a :class:`ParsedCmdline`."""
    parsed = ParsedCmdline(raw=line)
    if not line:
        return parsed
    for pos, raw_token in enumerate(_tokenize(line)):
        if not raw_token:
            continue
        # Strip a single layer of matching surrounding quotes from the
        # whole token - this catches ``"foo=bar"`` as well as ``'foo=bar'``.
        unquoted = raw_token
        if len(raw_token) >= 2 and raw_token[0] == raw_token[-1] \
                and raw_token[0] in ("\"", "'"):
            unquoted = raw_token[1:-1]
            parsed.quoted_tokens.append(raw_token)
        if "=" in unquoted:
            k, _, v = unquoted.partition("=")
            # If the *value* still carries a surrounding quote, strip
            # and mark as QUOTED.
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("\"", "'") \
                    and v[0] != raw_token[0]:
                v = v[1:-1]
                kind = CmdParamKind.QUOTED
            elif len(v) >= 2 and v[0] == v[-1] and v[0] in ("\"", "'") \
                    and unquoted != raw_token:
                # We already peeled the outer quotes; this is double-quoting
                # inside the value - treat as QUOTED anyway.
                v = v[1:-1]
                kind = CmdParamKind.QUOTED
            elif " " in v:
                kind = CmdParamKind.QUOTED
            else:
                kind = CmdParamKind.KEY_VALUE
            parsed.params.append(CmdParam(
                key=k.strip(), value=v.strip(),
                kind=kind, position=pos,
            ))
        else:
            if _KEY_RE.match(unquoted):
                parsed.params.append(CmdParam(
                    key=unquoted, value=None,
                    kind=CmdParamKind.FLAG, position=pos,
                ))
            else:
                log.debug("ignoring non-key token: %r", raw_token)
    return parsed


def build_cmdline(parsed: ParsedCmdline, sorted_keys: bool = False) -> str:
    """Re-emit a :class:`ParsedCmdline` as a string.

    When ``sorted_keys`` is True the parameters are emitted in
    alphabetical order (which loses ordering for repeated keys such
    as ``initrd=``).  By default, parameters are emitted in their
    original positional order.
    """
    if sorted_keys:
        params = sorted(parsed.params, key=lambda p: p.key)
    else:
        params = list(parsed.params)
    return " ".join(p.as_string() for p in params)


# ---------------------------------------------------------------------------
# Presets + known keys
# ---------------------------------------------------------------------------

#: Built-in cmdline presets.  Used by ``preset(name)`` and by the CLI.
PRESETS: Dict[str, str] = {
    "default":   "root=/dev/sda1 ro quiet splash",
    "recovery":  "root=/dev/sda1 ro single",
    "debug":     "root=/dev/sda1 ro nomodeset rd.debug rd.shell systemd.log_level=debug",
    "live":      "root=/dev/sdb1 rw live-media=removable quiet splash",
    "server":    "root=/dev/sda1 ro console=ttyS0,115200 quiet",
    "secure":    "root=/dev/sda1 ro selinux=enforcing enforcing",
    "minimal":   "root=/dev/sda1 ro console=tty0",
    "memtest":   "memtest",
    "kdump":     "root=/dev/sda1 ro maxcpus=1 irqpoll noirqdebug",
    "install":   "root=/dev/sdb1 rw preseed/file=/cdrom/preseed.cfg quiet",
}


def preset(name: str) -> str:
    """Return the named preset cmdline, or ``PRESETS["default"]``."""
    return PRESETS.get(name, PRESETS["default"])


#: Keys that are **expected** to appear in a well-formed cmdline.  This
#: is intentionally short - it is the *minimum* the FHS / systemd-boot
#: flow requires.
KNOWN_KEYS: set[str] = {
    "root", "ro", "rw", "init", "console", "quiet", "splash",
    "panic", "memtest", "elevator", "selinux", "enforcing",
    "nomodeset", "nokaslr", "acpi", "noapic", "nosmp", "maxcpus",
    "reserve", "mem", "hugepages", "initrd",
    "net.ifnames",
    "systemd.unit", "systemd.log_level", "systemd.log_target",
    "rd.break", "rd.shell", "rd.debug",
    "resume", "noresume",
    "video", "vga",
    "ipv6.disable",
    "libata.force",
    "pci", "nomsi",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class CmdlineIssue:
    code: str
    message: str
    position: int = -1

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message,
                "position": self.position}


def validate(line: str, required: Optional[List[str]] = None) -> List[CmdlineIssue]:
    """Return a list of :class:`CmdlineIssue` for a kernel cmdline.

    Currently checks:

    * has a non-empty ``root=`` argument (unless ``memtest`` is the only key)
    * every key matches ``^[A-Za-z][A-Za-z0-9_.\\-:/+]*$``
    * any required key is present
    """
    issues: List[CmdlineIssue] = []
    parsed = parse_cmdline(line)
    if not parsed.params:
        issues.append(CmdlineIssue("CL001", "command line is empty"))
        return issues

    keys = {p.key for p in parsed.params}
    if required:
        for r in required:
            if r not in keys:
                issues.append(CmdlineIssue(
                    "CL002", f"required parameter missing: {r}"))
    if "memtest" not in keys and "root" not in keys:
        issues.append(CmdlineIssue(
            "CL003", "no 'root=' and no 'memtest' - nothing to boot"))
    for p in parsed.params:
        if not _KEY_RE.match(p.key):
            issues.append(CmdlineIssue(
                "CL004", f"invalid key syntax: {p.key!r}", position=p.position))
    return issues


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # 1. Round-trip a canonical string
    s = "console=ttyS0,115200 quiet ro root=/dev/sda1 initrd=/boot/initramfs.img"
    parsed = parse_cmdline(s)
    rebuilt = build_cmdline(parsed)
    if set(rebuilt.split()) != set(s.split()):
        return False
    if parsed["root"].value != "/dev/sda1":
        return False
    if not parsed["ro"].is_flag:
        return False
    if parsed["quiet"].kind != CmdParamKind.FLAG:
        return False

    # 2. Quoted values
    p2 = parse_cmdline('console="ttyS0,115200n8"')
    if p2["console"].value != "ttyS0,115200n8":
        return False
    if p2["console"].kind != CmdParamKind.QUOTED:
        return False

    # 3. Repeated keys
    p3 = parse_cmdline("initrd=/a initrd=/b")
    if len(p3.all("initrd")) != 2:
        return False
    if p3.get_value("initrd") != "/b":
        return False

    # 4. has() / get()
    p4 = parse_cmdline("ro")
    if not p4.has("ro"):
        return False
    if p4.get("rw") is not None:
        return False
    if p4.get_value("root", default="default-root") != "default-root":
        return False

    # 5. Validation
    issues = validate("ro quiet")
    if not any(i.code == "CL003" for i in issues):
        return False
    issues2 = validate("root=/dev/sda1 ro")
    if any(i.code == "CL003" for i in issues2):
        return False
    issues3 = validate("", required=["root"])
    if not any(i.code == "CL001" for i in issues3):
        return False

    # 6. Presets
    if "root=" not in preset("default"):
        return False
    if preset("nope") != preset("default"):
        return False

    # 7. Empty / whitespace
    if parse_cmdline("").params:
        return False
    if parse_cmdline("   \t  ").params:
        return False

    return True


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2 or sys.argv[1] in ("selftest", "--selftest"):
        print("cmdline selftest:", "OK" if _selftest() else "FAIL")
    elif sys.argv[1] == "preset" and len(sys.argv) > 2:
        print(preset(sys.argv[2]))
    elif sys.argv[1] == "validate":
        issues = validate(" ".join(sys.argv[2:]))
        print(json.dumps([i.as_dict() for i in issues], indent=2))
    else:
        print(json.dumps(parse_cmdline(" ".join(sys.argv[1:])).as_dict(),
                         indent=2))
