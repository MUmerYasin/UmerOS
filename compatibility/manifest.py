"""
Umer OS /compatibility/manifest — Win32 application manifest parser
==================================================================

A Win32 application manifest is an XML document the loader reads at
process start to determine which **side-by-side (SxS)** assembly
versions the application needs.  The same XML can be:

* embedded as resource ID ``ISOLATIONAWARE_MANIFEST_RESOURCE_ID``
  (``2``) of type ``RT_MANIFEST`` (``24``) inside the PE,
* stored next to the executable as ``<name>.exe.manifest``,
* stored in the application's directory under a WinSxS style name.

We parse the *subset* of the schema that affects the loader:

* ``<assemblyIdentity>`` — the assembly's identity triple
  (``name``, ``version``, ``processorArchitecture``, ``type``,
  ``publicKeyToken``, ``language``).
* ``<dependency>`` — a *required* dependent assembly, identified by
  the same triple; the loader resolves it against the WinSxS store
  and (when possible) substitutes a forwarder DLL.
* ``<file>`` — a single DLL inside the assembly; used to map a
  logical dependency to a specific DLL name.

The parser is intentionally tolerant: unknown elements are kept in
:meth:`ActivationManifest.unknown_elements` so callers can audit
without failing.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/sbscs/application-manifests
* https://learn.microsoft.com/en-us/windows/win32/sbscs/assembly-identification

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

log = logging.getLogger("UmerOS.Compat.Manifest")

# Manifest resource constants — Microsoft convention.
ISOLATIONAWARE_MANIFEST_RESOURCE_ID = 2
RT_MANIFEST = 24

# XML namespace used by every side-by-side manifest.
MANIFEST_NS = "urn:schemas-microsoft-com:asm.v1"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssemblyIdentity:
    """A Win32 side-by-side assembly identity."""

    name: str
    version: str = "0.0.0.0"
    processor_architecture: str = "*"
    type: str = "win32"
    public_key_token: str = ""
    language: str = "*"

    def matches(self, other: "AssemblyIdentity") -> bool:
        """Return ``True`` if ``other`` describes the same assembly.

        Wildcard fields (``"*"`` or empty string) match anything;
        ``public_key_token`` and ``language`` are compared
        case-insensitively (matching ``SxsStore.dll`` behaviour).
        """
        def eq(a: str, b: str) -> bool:
            if not a or not b:
                return True        # empty == wildcard
            if a == "*" or b == "*":
                return True
            return a.lower() == b.lower()
        return (eq(self.name, other.name)
                and eq(self.version, other.version)
                and eq(self.processor_architecture,
                      other.processor_architecture)
                and eq(self.type, other.type)
                and eq(self.public_key_token, other.public_key_token)
                and eq(self.language, other.language))


@dataclass(frozen=True)
class Dependency:
    """A ``<dependency>`` block: a reference to another assembly."""

    identity: AssemblyIdentity
    files: Tuple[Tuple[str, str], ...] = ()    # ((logical_name, file_name),)


@dataclass
class ActivationManifest:
    """The parsed manifest.

    The fields are *populated* by :func:`parse_manifest`; tests can
    construct one directly when round-tripping.
    """

    #: ``<assemblyIdentity>`` of the *main* assembly, if any.
    assembly: Optional[AssemblyIdentity] = None
    #: All declared dependencies in the order they appeared.
    dependencies: Tuple[Dependency, ...] = ()
    #: Element text that the parser did not understand.
    unknown_elements: Tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def find_dependency(self, name: str) -> Optional[Dependency]:
        """Return the first dependency whose ``identity.name == name``."""
        for d in self.dependencies:
            if d.identity.name == name:
                return d
        return None

    def all_assemblies(self) -> List[AssemblyIdentity]:
        out: List[AssemblyIdentity] = []
        if self.assembly is not None:
            out.append(self.assembly)
        for d in self.dependencies:
            out.append(d.identity)
        return out


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def _attrs_to_identity(attrs: Dict[str, str]) -> AssemblyIdentity:
    return AssemblyIdentity(
        name=attrs.get("name", ""),
        version=attrs.get("version", "0.0.0.0"),
        processor_architecture=attrs.get("processorArchitecture", "*"),
        type=attrs.get("type", "win32"),
        public_key_token=attrs.get("publicKeyToken", ""),
        language=attrs.get("language", "*"),
    )


def parse_manifest(xml_text: str) -> ActivationManifest:
    """Parse an SxS manifest (XML text) into an :class:`ActivationManifest`.

    Returns an empty manifest when ``xml_text`` is not valid XML; the
    raw text is preserved in :attr:`unknown_elements` so the caller can
    audit it.
    """
    if not xml_text or not xml_text.strip():
        return ActivationManifest(unknown_elements=("<empty>",))
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.debug("manifest XML parse error: %s", exc)
        return ActivationManifest(unknown_elements=(str(exc),))

    assembly: Optional[AssemblyIdentity] = None
    deps: List[Dependency] = []
    unknown: List[str] = []
    qn = f"{{{MANIFEST_NS}}}"

    # Some manifests use the namespace as the root (most common); some
    # nest <assembly> under a non-namespaced root.  Accept both.
    asm = root
    if not asm.tag.endswith("}assembly") and asm.tag != "assembly":
        asm = root.find(f"{qn}assembly")
        if asm is None:
            asm = root.find("assembly")
    if asm is not None:
        ident = asm.find(f"{qn}assemblyIdentity")
        if ident is None:
            ident = asm.find("assemblyIdentity")
        if ident is not None:
            assembly = _attrs_to_identity(ident.attrib)
        # <dependency> blocks.
        for dep in asm.findall(f"{qn}dependency"):
            dep_ident = dep.find(f"{qn}dependentAssembly")
            if dep_ident is None:
                dep_ident = dep.find("dependentAssembly")
            if dep_ident is None:
                dep_ident = dep.find(f"{qn}assemblyIdentity")
            if dep_ident is None:
                dep_ident = dep.find("assemblyIdentity")
            # The actual <assemblyIdentity> lives *inside*
            # <dependentAssembly>; fall back to one level deeper.
            if dep_ident is not None:
                inner = dep_ident.find(f"{qn}assemblyIdentity")
                if inner is None:
                    inner = dep_ident.find("assemblyIdentity")
                if inner is not None:
                    dep_ident = inner
            if dep_ident is None:
                continue
            files: List[Tuple[str, str]] = []
            files_el = dep.find(f"{qn}file")
            if files_el is None:
                files_el = dep.find("file")
            if files_el is not None:
                files.append((
                    files_el.attrib.get("name", ""),
                    files_el.attrib.get("hash", ""),
                ))
            deps.append(Dependency(
                identity=_attrs_to_identity(dep_ident.attrib),
                files=tuple(files),
            ))

    # Capture any text inside elements we did not understand.
    for el in root.iter():
        tag = el.tag.split("}", 1)[-1]
        if tag not in ("assembly", "assemblyIdentity", "dependency",
                       "dependentAssembly", "file"):
            unknown.append(tag)

    return ActivationManifest(
        assembly=assembly,
        dependencies=tuple(deps),
        unknown_elements=tuple(unknown),
    )


def parse_manifest_file(path: str) -> ActivationManifest:
    """Read ``path`` and parse it as a manifest."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return parse_manifest(f.read())


# ---------------------------------------------------------------------------
# Resource extraction helper
# ---------------------------------------------------------------------------

def find_manifest_in_resources(pe) -> Optional[Tuple[int, str]]:
    """Locate the embedded manifest inside ``pe`` resources.

    Returns ``(lang_id, manifest_text)`` for the first manifest found,
    or ``None`` when the binary does not embed one.  ``pe`` must
    expose :meth:`get_resources` from :mod:`pe_resources`.
    """
    try:
        from .pe_resources import parse_resources
    except Exception:
        return None
    res = parse_resources(pe)
    if res is None:
        return None
    for entry in res.entries:
        if entry.type_id == RT_MANIFEST and entry.name_id == ISOLATIONAWARE_MANIFEST_RESOURCE_ID:
            data = entry.data
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("utf-8", errors="replace")
            return (0, text)
    return None


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity name="Microsoft.VC90.CRT"
                    version="9.0.21022.8"
                    processorArchitecture="x86"
                    publicKeyToken="1fc8b3b9a1e18e3b"
                    type="win32" />
  <dependency>
    <dependentAssembly>
      <assemblyIdentity name="Microsoft.VC90.CRT"
                        version="9.0.21022.8"
                        processorArchitecture="x86"
                        publicKeyToken="1fc8b3b9a1e18e3b" />
    </dependentAssembly>
  </dependency>
  <file name="foo.dll" hash="abc" />
</assembly>
"""


def _selftest() -> bool:
    m = parse_manifest(_SAMPLE)
    if m.assembly is None:
        return False
    if m.assembly.name != "Microsoft.VC90.CRT":
        return False
    if m.assembly.version != "9.0.21022.8":
        return False
    if m.assembly.public_key_token.lower() != "1fc8b3b9a1e18e3b":
        return False
    if len(m.dependencies) != 1:
        return False
    dep = m.find_dependency("Microsoft.VC90.CRT")
    if dep is None:
        return False
    if dep.identity.version != "9.0.21022.8":
        return False

    # Wildcard match.
    a = AssemblyIdentity(name="X", version="")
    b = AssemblyIdentity(name="X", version="1.2.3.4")
    if not a.matches(b):
        return False
    if not b.matches(a):
        return False
    c = AssemblyIdentity(name="Y", version="")
    if a.matches(c):
        return False

    # PublicKeyToken is case-insensitive.
    a = AssemblyIdentity(name="X", public_key_token="abcdef")
    b = AssemblyIdentity(name="X", public_key_token="ABCDEF")
    if not a.matches(b):
        return False

    # Malformed XML returns empty manifest, not exception.
    bad = parse_manifest("<assembly>")
    if bad.assembly is not None:
        return False
    empty = parse_manifest("")
    if empty.assembly is not None:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
