"""
Umer OS /tests/test_compatibility — Tests for the Windows compatibility layer
=========================================================================

This test file exercises the most important parsers, helpers and
the high-level ``wine_shim`` loader.  It uses only stdlib
``unittest`` so it integrates with the existing Umer OS test
infrastructure (``tests/run_*_tests.py``).

The tests run on both POSIX (where applicable) and Windows hosts;
POSIX-specific behaviour is gated with ``@unittest.skipUnless``.
"""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest

# Make sure the repo root is importable.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from compatibility import (  # noqa: E402
    mz_loader, ne_loader, pe_loader, pe_imports, pe_exports,
    pe_relocations, pe_tls, pe_resources,
    registry_hive, registry_view, registry_paths,
    win_kernel32, win_user32, win_gdi32, win_advapi32, win_ntdll,
    winerror, ntstatus, win_guid, win_sid, win_strings, win_path,
    dll_loader, wine_shim,
    api_set, forwarded, dll_search, manifest, long_path,
    memory_map, sync,
    version_info, delay_imports, signed_pe, winsock, timezone,
)
from compatibility.pe_loader import PeFile, PeClass          # noqa: E402
from compatibility.dll_loader import DllLoader, ResolvedImport  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_pe(
    *,
    machine: int = 0x014C,                # i386
    n_sections: int = 2,
    subsystem: int = 3,                    # WINDOWS_CUI
    image_base: int = 0x00400000,
    entry_rva: int = 0x1000,
    chars: int = 0x60000020,               # .text: code|exec|read
    data_chars: int = 0xC0000040,          # .data: data|read|write
    with_export: bool = False,
) -> bytes:
    """Build a small but well-formed PE32 image in memory.

    Sections: a .text and a .data section; the .text section is
    laid out at file offset 0x200 (the page-aligned slot that the
    selftest expects).
    """
    out = bytearray()
    # --- MZ header ---
    out += b"MZ"
    out += b"\x00" * 58
    pe_off = len(out)
    out += struct.pack("<I", pe_off + 4)
    # --- PE header ---
    out += b"PE\x00\x00"
    out += struct.pack(
        "<HHIIIHH",
        machine, n_sections, 0, 0, 0, 224, 0x0102,
    )
    # Optional header (PE32, 30 fields, then 16 data dirs).
    out += struct.pack(
        "<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII",
        0x10B, 14, 0,        # magic, linker version
        0x200,                # size_of_code
        0x100,                # size_of_initialized_data
        0,                    # size_of_uninitialized_data
        entry_rva,
        0x1000,               # base_of_code
        0x2000,               # base_of_data
        image_base,
        0x1000,               # section_alignment
        0x200,                # file_alignment
        6, 0,                 # OS version
        0, 0,                 # image version
        6, 0,                 # subsystem version
        0,                    # win32 version
        0x3000,               # size_of_image
        0x200,                # size_of_headers
        0,                    # check_sum
        subsystem,
        0x0140,               # dll characteristics
        0x100000, 0x1000,     # stack
        0x100000, 0x1000,     # heap
        0,                    # loader flags
        16,                   # number_of_rva_and_sizes
    )
    # 16 data directories (all zero, except maybe an export).
    for i in range(16):
        if with_export and i == 0:
            out += struct.pack("<II", 0x3000, 0x40)
        else:
            out += struct.pack("<II", 0, 0)
    # Section headers.
    out += b".text\x00\x00\x00"
    out += struct.pack(
        "<IIIIIIHHI",
        0x100, 0x1000, 0x200, 0x200, 0, 0, 0, 0, chars,
    )
    out += b".data\x00\x00\x00"
    out += struct.pack(
        "<IIIIIIHHI",
        0x100, 0x2000, 0x100, 0x400, 0, 0, 0, 0, data_chars,
    )
    # Pad to 0x200, then add a ret (0xC3) at offset 0x200 (entry).
    while len(out) % 0x200 != 0:
        out += b"\x00"
    out += b"\xC3" + b"\x00" * 0x1FF
    out += b"D" * 0x100    # .data body
    return bytes(out)


# ---------------------------------------------------------------------------
# MZ / NE / PE parser tests
# ---------------------------------------------------------------------------

class TestMzHeader(unittest.TestCase):
    def test_minimal(self) -> None:
        data = b"MZ" + b"\x00" * 58
        data += (0x40).to_bytes(4, "little")
        hdr = mz_loader.parse_mz_header(data)
        self.assertTrue(hdr.is_mz)
        self.assertEqual(hdr.e_lfanew, 0x40)


class TestNeHeader(unittest.TestCase):
    def test_minimal(self) -> None:
        data = bytearray(64)
        data[0:2] = b"NE"
        data[2] = 5
        struct.pack_into("<H", data, 36, 9)        # sector shift
        hdr = ne_loader.parse_ne_header(bytes(data))
        self.assertTrue(hdr.is_ne)
        self.assertEqual(hdr.version_major, 5)
        self.assertEqual(hdr.sector_shift, 9)


class TestPeFile(unittest.TestCase):
    def test_basic_load(self) -> None:
        pe = PeFile.from_bytes(_build_pe())
        self.assertEqual(pe.machine, 0x014C)
        self.assertEqual(pe.optional_header.pe_class, PeClass.PE32)
        self.assertEqual(pe.number_of_sections, 2)
        self.assertEqual(pe.entry_point_rva, 0x1000)
        self.assertEqual(pe.image_base, 0x00400000)
        self.assertEqual(pe.subsystem_name, "WINDOWS_CUI")
        names = [s.name for s in pe.sections]
        self.assertIn(".text", names)
        self.assertIn(".data", names)
        # First byte of .text should be 0xC3.
        self.assertEqual(pe.get_data(0x1000, 1), b"\xC3")
        # RVA -> offset round-trip.
        off, length = pe.rva_to_offset(0x1000)
        self.assertEqual(off, 0x200)
        self.assertEqual(length, 0x200)

    def test_data_directory_parsing(self) -> None:
        pe = PeFile.from_bytes(_build_pe())
        self.assertEqual(len(pe.optional_header.data_directories), 16)
        for d in pe.optional_header.data_directories:
            self.assertFalse(d.is_present)

    def test_dll_characteristics_parsed(self) -> None:
        pe = PeFile.from_bytes(_build_pe())
        # 0x0140 = DYNAMIC_BASE | NX_COMPAT
        self.assertTrue(pe.optional_header.dll_characteristics & 0x100)
        self.assertTrue(pe.optional_header.dll_characteristics & 0x0040)


class TestPeDirectoryParsers(unittest.TestCase):
    def setUp(self) -> None:
        self.pe = PeFile.from_bytes(_build_pe())

    def test_imports_empty(self) -> None:
        self.assertEqual(pe_imports.parse_imports(self.pe), [])

    def test_exports_empty(self) -> None:
        self.assertIsNone(pe_exports.parse_exports(self.pe))

    def test_relocations_empty(self) -> None:
        reloc = pe_relocations.parse_relocations(self.pe)
        self.assertEqual(reloc.entry_count, 0)

    def test_tls_empty(self) -> None:
        self.assertIsNone(pe_tls.parse_tls_directory(self.pe))

    def test_resources_empty(self) -> None:
        self.assertIsNone(pe_resources.parse_resources(self.pe))


# ---------------------------------------------------------------------------
# Foundation
# ---------------------------------------------------------------------------

class TestErrorCodes(unittest.TestCase):
    def test_winerror_format(self) -> None:
        self.assertEqual(winerror.format_win32_error(0), "ERROR_SUCCESS (0x00000000)")
        self.assertEqual(winerror.format_win32_error(2), "ERROR_FILE_NOT_FOUND (0x00000002)")
        self.assertEqual(winerror.format_hresult(0), "S_OK")
        self.assertEqual(winerror.format_hresult(0x80070005),
                         "HRESULT_FROM_WIN32(ERROR_ACCESS_DENIED (0x00000005))")

    def test_ntstatus_format(self) -> None:
        self.assertEqual(ntstatus.format_ntstatus(0), "STATUS_SUCCESS (0x00000000)")
        self.assertEqual(ntstatus.format_ntstatus(0xC0000005),
                         "STATUS_ACCESS_VIOLATION (0xC0000005)")

    def test_ntstatus_to_win32(self) -> None:
        self.assertEqual(ntstatus.ntstatus_to_win32(ntstatus.STATUS_SUCCESS), 0)
        self.assertEqual(ntstatus.ntstatus_to_win32(ntstatus.STATUS_INVALID_HANDLE), 6)
        self.assertEqual(ntstatus.ntstatus_to_win32(ntstatus.STATUS_ACCESS_DENIED), 5)
        self.assertEqual(ntstatus.ntstatus_to_win32(0xDEADBEEF), 1)


class TestGuid(unittest.TestCase):
    def test_round_trip_string(self) -> None:
        g = win_guid.Guid.from_string("{12345678-9ABC-DEF0-1234-56789ABCDEF0}")
        self.assertEqual(g.data1, 0x12345678)
        self.assertEqual(g.data2, 0x9ABC)
        self.assertEqual(g.data3, 0xDEF0)
        s = str(g)
        self.assertEqual(s, "{12345678-9ABC-DEF0-1234-56789ABCDEF0}")

    def test_uuid_bridge(self) -> None:
        g = win_guid.Guid(0x00020400, 0x0000, 0x0000,
                            (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46))
        u = g.to_uuid()
        g2 = win_guid.Guid.from_uuid(u)
        self.assertEqual(g, g2)

    def test_iunknown_is_known(self) -> None:
        self.assertEqual(win_guid.IID_IUNKNOWN.data1, 0)


class TestSid(unittest.TestCase):
    def test_round_trip(self) -> None:
        s = win_sid.Sid.from_string("S-1-5-32-544")
        self.assertEqual(s.authority, 5)
        self.assertEqual(s.subauthorities, (32, 544))
        self.assertEqual(str(s), "S-1-5-32-544")

    def test_database(self) -> None:
        db = win_sid.DEFAULT_DB
        self.assertEqual(db.lookup_name(win_sid.SID_LOCAL_SYSTEM), "LocalSystem")
        self.assertEqual(db.lookup_sid("Everyone"), win_sid.SID_EVERYONE)


class TestDosPath(unittest.TestCase):
    def setUp(self) -> None:
        # Use a relative compat root so the test is portable across
        # POSIX / Windows.  The mapper will absolute-path it, but
        # we assert against the *absolute* root rather than a
        # hard-coded one.
        self.tmp = tempfile.mkdtemp()
        self.compat = os.path.join(self.tmp, "compat")
        self.m = win_path.DosPathMapper(compat_root=self.compat)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _expected(self, *parts) -> str:
        """Compose an expected path with forward slashes (the
        mapper normalises everything to forward slashes for
        portability)."""
        return "/".join([self.m.compat_root.replace("\\", "/")] + list(parts))

    def test_drive_path(self) -> None:
        self.assertEqual(
            self.m.to_posix(r"C:\Windows"),
            self._expected("C", "Windows"),
        )

    def test_unc(self) -> None:
        self.assertEqual(
            self.m.to_posix(r"\\server\share\path"),
            self._expected("unc", "server", "share", "path"),
        )

    def test_drive_relative(self) -> None:
        self.m.set_drive_cwd("D", r"D:\Projects\UmerOS")
        self.assertEqual(
            self.m.to_posix("D:readme.txt"),
            self._expected("D", "Projects", "UmerOS", "readme.txt"),
        )


class TestUnicodeString(unittest.TestCase):
    def test_wide_str(self) -> None:
        self.assertEqual(win_strings.wide_str("hi"), b"h\x00i\x00\x00\x00")
        self.assertEqual(win_strings.from_wide(b"h\x00i\x00\x00\x00"), "hi")

    def test_dataclass(self) -> None:
        u = win_strings.UnicodeString("hello")
        self.assertEqual(u.length_bytes, 10)
        self.assertEqual(u.max_bytes, 12)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry(unittest.TestCase):
    def test_in_memory_round_trip(self) -> None:
        reg = registry_view.InMemoryRegistry()
        version = "2.0.0".encode("utf-16-le") + b"\x00\x00"
        reg.set_value(r"HKLM\SOFTWARE\UmerOS", "Version", version,
                      registry_hive.RegType.SZ)
        v = reg.get_value(r"HKLM\SOFTWARE\UmerOS", "Version")
        self.assertIsNotNone(v)
        self.assertEqual(v.as_string(), "2.0.0")
        # DWORD
        reg.set_value(r"HKLM\SOFTWARE\UmerOS", "Flags",
                      b"\x01\x00\x00\x00", registry_hive.RegType.DWORD)
        v = reg.get_value(r"HKLM\SOFTWARE\UmerOS", "Flags")
        self.assertEqual(v.as_dword(), 1)
        # Delete
        self.assertTrue(reg.delete_value(r"HKLM\SOFTWARE\UmerOS", "Version"))
        self.assertIsNone(reg.get_value(r"HKLM\SOFTWARE\UmerOS", "Version"))

    def test_paths(self) -> None:
        # Use a temporary compat root so the assertion is portable.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                registry_paths.hive_posix_path(
                    "SOFTWARE", compat_root=os.path.join(tmp, "compat", "Windows", "System32", "config")),
                os.path.join(tmp, "compat", "Windows", "System32", "config", "SOFTWARE"),
            )
        self.assertEqual(registry_paths.hkey_for_hive("SOFTWARE"), 0x80000002)
        self.assertEqual(registry_paths.hkey_for_hive("NTUSER"), 0x80000001)


# ---------------------------------------------------------------------------
# Win32 API
# ---------------------------------------------------------------------------

class TestKernel32(unittest.TestCase):
    def test_get_set_last_error(self) -> None:
        win_kernel32.SetLastError(win_kernel32.ERROR_FILE_NOT_FOUND)
        self.assertEqual(win_kernel32.GetLastError(),
                         win_kernel32.ERROR_FILE_NOT_FOUND)

    def test_file_io(self) -> None:
        import os
        import tempfile
        # Use a path under our tmp dir to avoid the default
        # Windows temp directory which can have permission
        # inheritance issues.
        path = os.path.join(tempfile.gettempdir(),
                            "umeros_test_compat_io.bin")
        with open(path, "wb") as f:
            f.write(b"hello world")
        try:
            h = win_kernel32.CreateFileA(
                path, 0xC0000000, 0, None, 3, 0, 0)
            self.assertNotEqual(h, 0xFFFFFFFF)
            ok, data = win_kernel32.ReadFile(h, 5)
            self.assertTrue(ok)
            self.assertEqual(data, b"hello")
            ok, n = win_kernel32.WriteFile(h, b"!")
            self.assertTrue(ok)
            self.assertEqual(n, 1)
            self.assertTrue(win_kernel32.CloseHandle(h))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


class TestUser32(unittest.TestCase):
    def test_message_pump(self) -> None:
        # Register a class and create a window.
        from dataclasses import dataclass as _dc
        @_dc
        class W:
            lpszClassName: str
            style: int = 0
            lpfnWndProc: object = None
            cbClsExtra: int = 0
            cbWndExtra: int = 0
            hInstance: int = 0
            hIcon: int = 0
            hCursor: int = 0
            hbrBackground: int = 0
            lpszMenuName: str = ""
            hIconSm: int = 0
        win_user32.RegisterClassExA(W(lpszClassName="UmerOSWindow"))
        hwnd = win_user32.CreateWindowExA(
            0, "UmerOSWindow", "Test", 0, 0, 0, 100, 100, 0, 0, 0, 0)
        self.assertNotEqual(hwnd, 0)
        self.assertTrue(win_user32.PostMessageA(hwnd, 0x0001, 0, 0))
        m = win_user32.Msg(hwnd=0, message=0, wparam=0, lparam=0, time=0)
        self.assertTrue(win_user32.GetMessageA(m, 0, 0, 0))
        self.assertEqual(m.message, 0x0001)


class TestGdi32(unittest.TestCase):
    def test_object_lifecycle(self) -> None:
        dc = win_gdi32.GetDC(0)
        self.assertNotEqual(dc, 0)
        self.assertTrue(win_gdi32.ReleaseDC(0, dc))
        pen = win_gdi32.CreatePen(0, 1, 0)
        self.assertTrue(win_gdi32.DeleteObject(pen))


class TestAdvApi32(unittest.TestCase):
    def test_registry_stub(self) -> None:
        h = win_advapi32.RegOpenKeyA(0x80000002, r"SOFTWARE\UmerOS")
        self.assertNotEqual(h, 0)
        self.assertEqual(win_advapi32.RegCloseKey(h), 0)


class TestNtdll(unittest.TestCase):
    def test_nt_create_file(self) -> None:
        out = [0]
        rc = win_ntdll.NtCreateFile(out, 0, None, None, None, 0, 0, 0, 0,
                                    None, 0)
        self.assertEqual(rc, ntstatus.STATUS_SUCCESS)
        self.assertNotEqual(out[0], 0)
        self.assertEqual(win_ntdll.NtClose(out[0]), ntstatus.STATUS_SUCCESS)


# ---------------------------------------------------------------------------
# DLL loader + Wine shim
# ---------------------------------------------------------------------------

class TestDllLoader(unittest.TestCase):
    def test_resolve_empty(self) -> None:
        pe = PeFile.from_bytes(_build_pe())
        loader = DllLoader()
        loaded = loader.resolve(pe)
        self.assertEqual(loaded.pe, pe)
        self.assertEqual(loaded.imports, [])
        self.assertEqual(loaded.resolved_imports, [])
        self.assertEqual(loaded.missing_imports(), [])

    def test_host_libraries_loaded(self) -> None:
        from compatibility.dll_loader import HOST_LIBRARIES
        self.assertIn("KERNEL32.DLL", HOST_LIBRARIES)
        self.assertIn("USER32.DLL", HOST_LIBRARIES)
        # The kernel32 export "GetTickCount" must be the real function.
        from compatibility.win_kernel32 import GetTickCount
        self.assertIs(HOST_LIBRARIES["KERNEL32.DLL"]["GetTickCount"],
                      GetTickCount)


class TestWineShim(unittest.TestCase):
    def test_launch_fake(self) -> None:
        # Build a fake PE in a temp file, then audit it.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tf:
            tf.write(_build_pe())
            path = tf.name
        try:
            shim = wine_shim.WineShim()
            r = shim.launch(path)
            self.assertTrue(r.pe.entry_point_rva != 0)
            # The fake PE has no imports, so all are resolvable.
            self.assertTrue(r.is_loadable)
        finally:
            os.remove(path)


# ---------------------------------------------------------------------------
# API Set Schema
# ---------------------------------------------------------------------------

class TestApiSet(unittest.TestCase):
    def test_fallback_resolves_core(self) -> None:
        ns = api_set.fallback_namespace()
        e = ns.resolve("api-ms-win-core-io-l1-1-0.dll")
        self.assertIsNotNone(e)
        self.assertEqual(e.values[0].dll_name.lower(), "kernel32.dll")

    def test_fallback_resolves_crt(self) -> None:
        ns = api_set.fallback_namespace()
        e = ns.resolve("api-ms-win-crt-runtime-l1-1-0")
        self.assertIsNotNone(e)
        self.assertEqual(e.values[0].dll_name.lower(), "ucrtbase.dll")

    def test_is_api_set_name(self) -> None:
        self.assertTrue(api_set.is_api_set_name("api-ms-win-core-foo-l1-1-0"))
        self.assertTrue(api_set.is_api_set_name("API-MS-WIN-CORE-FOO-L1-1-0.DLL"))
        self.assertFalse(api_set.is_api_set_name("KERNEL32.DLL"))
        self.assertFalse(api_set.is_api_set_name(""))

    def test_parse_synthetic_blob(self) -> None:
        blob = api_set._build_synthetic_schema()
        ns = api_set.parse_apiset(blob)
        self.assertIsNotNone(ns)
        self.assertEqual(ns.version, 2)
        e = ns.resolve("api-ms-win-test-set-l1-1-0.dll")
        self.assertIsNotNone(e)
        self.assertEqual(e.values[0].dll_name, "ucrtbase.dll")


# ---------------------------------------------------------------------------
# Forwarded exports
# ---------------------------------------------------------------------------

class TestForwarded(unittest.TestCase):
    def test_parse_forwarder(self) -> None:
        f = forwarded.ForwarderString.parse("kernel32.DecodePointer")
        self.assertIsNotNone(f)
        self.assertEqual(f.dll, "kernel32")
        self.assertEqual(f.symbol, "DecodePointer")
        self.assertFalse(f.is_ordinal)

    def test_parse_ordinal(self) -> None:
        f = forwarded.ForwarderString.parse("ntdll.#42")
        self.assertIsNotNone(f)
        self.assertTrue(f.is_ordinal)
        self.assertEqual(f.ordinal, 42)

    def test_follow_chain(self) -> None:
        def resolver(dll, sym):
            if (dll.upper(), sym) == ("A", "foo"):
                return "b.dll.bar"
            if (dll.upper(), sym) == ("B.DLL", "bar"):
                return "c.dll.baz"
            if (dll.upper(), sym) == ("C.DLL", "baz"):
                return forwarded.follow_forward.__globals__.get(
                    "__terminal__", "__terminal__")
            return None
        result = forwarded.follow_forward("a.foo", resolver)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_terminal)
        self.assertEqual(result.final_dll.upper(), "C.DLL")
        self.assertEqual(result.final_name, "baz")
        self.assertEqual(result.depth, 3)
        self.assertEqual(len(result.chain), 2)

    def test_cycle_detection(self) -> None:
        def resolver(dll, sym):
            if sym == "alpha":
                return "beta"
            if sym == "beta":
                return "alpha"
            return None
        self.assertIsNone(forwarded.follow_forward("gamma.alpha", resolver))


# ---------------------------------------------------------------------------
# DLL search order
# ---------------------------------------------------------------------------

class TestDllSearch(unittest.TestCase):
    def test_safe_mode_application_first(self) -> None:
        sp = dll_search.DllSearchPath(
            application_dir="C:/App",
            system32_dir="C:/Windows/System32",
            system16_dir="C:/Windows/System",
            windows_dir="C:/Windows",
            current_dir="C:/Other",
            safe_dll_search_mode=True,
        )
        kinds = [l.kind for l in sp.make_sequence()]
        self.assertEqual(kinds[:4],
                         ["application", "system32", "system16", "windows"])
        self.assertEqual(kinds[4], "current")

    def test_legacy_mode_current_before_system(self) -> None:
        sp = dll_search.DllSearchPath(
            application_dir="C:/App",
            system32_dir="C:/Windows/System32",
            system16_dir="C:/Windows/System",
            windows_dir="C:/Windows",
            current_dir="C:/Other",
            safe_dll_search_mode=False,
        )
        kinds = [l.kind for l in sp.make_sequence()]
        self.assertEqual(kinds[:2], ["application", "current"])

    def test_find_dll_with_real_files(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            app = os.path.join(tmp, "app")
            sys32 = os.path.join(tmp, "win", "system32")
            os.makedirs(app)
            os.makedirs(sys32)
            with open(os.path.join(sys32, "foo.dll"), "wb") as f:
                f.write(b"x")
            sp = dll_search.DllSearchPath(
                application_dir=app,
                system32_dir=sys32,
                windows_dir=tmp,
                safe_dll_search_mode=True,
            )
            loc, path = dll_search.find_dll("foo.dll", sp)
            self.assertIsNotNone(loc)
            self.assertEqual(loc.kind, "system32")

    def test_candidate_names(self) -> None:
        self.assertEqual(dll_search.DllSearchPath.candidate_names("kernel32"),
                         ("kernel32.dll", "kernel32.DLL"))
        self.assertEqual(dll_search.DllSearchPath.candidate_names("foo.bar"),
                         ("foo.bar",))


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class TestManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.xml = (
            '<?xml version="1.0"?>'
            '<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">'
            '  <assemblyIdentity name="X" version="1.0.0.0" processorArchitecture="x86" '
            'publicKeyToken="abcdef" type="win32" />'
            '  <dependency>'
            '    <dependentAssembly>'
            '      <assemblyIdentity name="Y" version="2.0.0.0" '
            'processorArchitecture="x86" publicKeyToken="123456" />'
            '    </dependentAssembly>'
            '  </dependency>'
            '</assembly>'
        )

    def test_parse_basic(self) -> None:
        m = manifest.parse_manifest(self.xml)
        self.assertIsNotNone(m.assembly)
        self.assertEqual(m.assembly.name, "X")
        self.assertEqual(m.assembly.version, "1.0.0.0")

    def test_parse_dependency(self) -> None:
        m = manifest.parse_manifest(self.xml)
        self.assertEqual(len(m.dependencies), 1)
        d = m.find_dependency("Y")
        self.assertIsNotNone(d)
        self.assertEqual(d.identity.public_key_token, "123456")

    def test_wildcard_match(self) -> None:
        a = manifest.AssemblyIdentity(name="X", public_key_token="abc")
        b = manifest.AssemblyIdentity(name="X", public_key_token="ABC")
        self.assertTrue(a.matches(b))

    def test_malformed_returns_empty(self) -> None:
        m = manifest.parse_manifest("<assembly>")
        self.assertIsNone(m.assembly)


# ---------------------------------------------------------------------------
# Long path
# ---------------------------------------------------------------------------

class TestLongPath(unittest.TestCase):
    def test_parse_extended_drive(self) -> None:
        p = long_path.parse_long_path("\\\\?\\C:\\Windows")
        self.assertEqual(p.prefix, long_path.LongPathPrefix.WIN32_EXTENDED)
        self.assertEqual(p.drive, "C")
        self.assertEqual(p.path_parts, ("Windows",))

    def test_parse_extended_unc(self) -> None:
        p = long_path.parse_long_path(
            "\\\\?\\UNC\\server\\share\\dir\\file.txt")
        self.assertEqual(p.prefix, long_path.LongPathPrefix.WIN32_UNC)
        self.assertTrue(p.is_unc)
        self.assertEqual(p.server, "server")
        self.assertEqual(p.share, "share")

    def test_parse_device(self) -> None:
        p = long_path.parse_long_path("\\\\.\\COM1")
        self.assertEqual(p.prefix, long_path.LongPathPrefix.WIN32_DEVICE)

    def test_to_native_drops_prefix(self) -> None:
        p = long_path.parse_long_path("\\\\?\\C:\\Windows\\foo")
        self.assertEqual(p.to_native(), "C:\\Windows\\foo")

    def test_no_prefix_passthrough(self) -> None:
        p = long_path.parse_long_path("C:\\Windows")
        self.assertEqual(p.prefix, long_path.LongPathPrefix.NONE)
        self.assertEqual(p.drive, "C")

    def test_make_extended_roundtrip(self) -> None:
        s = long_path.make_extended("D", ("a", "b"))
        p = long_path.parse_long_path(s)
        self.assertEqual(p.drive, "D")
        self.assertEqual(p.path_parts, ("a", "b"))


# ---------------------------------------------------------------------------
# Memory-mapped files
# ---------------------------------------------------------------------------

class TestMemoryMap(unittest.TestCase):
    def test_anonymous_round_trip(self) -> None:
        h = memory_map.CreateFileMappingA(
            memory_map.INVALID_HANDLE_VALUE, None,
            memory_map.PAGE_READWRITE, 0, 4096,
            "Local\\UmerOS_test_anon")
        self.assertNotEqual(h, 0)
        addr = memory_map.MapViewOfFile(
            h, memory_map.FILE_MAP_ALL_ACCESS, 0, 0, 4096)
        self.assertNotEqual(addr, 0)
        mapping = memory_map.get_mapping(h)
        self.assertIsNotNone(mapping)
        view = mapping.views[-1]
        view.mmap[:11] = b"hello world"
        self.assertEqual(view.read(11), b"hello world")
        self.assertTrue(memory_map.UnmapViewOfFile(addr))
        self.assertTrue(memory_map.CloseMappingHandle(h))

    def test_open_existing(self) -> None:
        h1 = memory_map.CreateFileMappingA(
            memory_map.INVALID_HANDLE_VALUE, None,
            memory_map.PAGE_READWRITE, 0, 256,
            "Local\\UmerOS_test_lookup")
        h2 = memory_map.OpenFileMappingA(
            memory_map.FILE_MAP_ALL_ACCESS, False,
            "Local\\UmerOS_test_lookup")
        self.assertNotEqual(h1, 0)
        self.assertNotEqual(h2, 0)
        self.assertIs(memory_map.get_mapping(h1),
                      memory_map.get_mapping(h2))
        memory_map.CloseMappingHandle(h1)

    def test_missing_name(self) -> None:
        self.assertEqual(
            memory_map.OpenFileMappingA(
                memory_map.FILE_MAP_ALL_ACCESS, False,
                "Local\\UmerOS_does_not_exist"),
            0)


# ---------------------------------------------------------------------------
# Synchronization primitives
# ---------------------------------------------------------------------------

class TestSync(unittest.TestCase):
    def test_critical_section_recursive(self) -> None:
        cs = sync.create_critical_section()
        sync.InitializeCriticalSection(cs)
        sync.EnterCriticalSection(cs)
        self.assertTrue(sync.TryEnterCriticalSection(cs))
        sync.LeaveCriticalSection(cs)
        sync.LeaveCriticalSection(cs)
        sync.DeleteCriticalSection(cs)

    def test_srw_exclusive_blocks_shared(self) -> None:
        srw = sync.create_srw_lock()
        sync.InitializeSRWLock(srw)
        sync.AcquireSRWLockExclusive(srw)
        self.assertFalse(sync.TryAcquireSRWLockShared(srw))
        self.assertFalse(sync.TryAcquireSRWLockExclusive(srw))
        sync.ReleaseSRWLockExclusive(srw)
        self.assertTrue(sync.TryAcquireSRWLockShared(srw))
        sync.ReleaseSRWLockShared(srw)

    def test_init_once_runs_once(self) -> None:
        import threading
        io = sync.create_init_once()
        sync.InitOnceInitialize(io)
        counter = [0]
        results: list = []

        def init(_p):
            counter[0] += 1
            return "ctx"

        def runner():
            sync.InitOnceExecuteOnce(io, init, None, results)

        threads = [threading.Thread(target=runner) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)
        self.assertEqual(counter[0], 1)
        self.assertTrue(all(r == "ctx" for r in results))


# ---------------------------------------------------------------------------
# VS_VERSIONINFO
# ---------------------------------------------------------------------------

class TestVersionInfo(unittest.TestCase):
    def test_fixture_round_trip(self) -> None:
        blob = version_info._build_fixture()
        info = version_info.parse_version_info(blob)
        self.assertIsNotNone(info)
        self.assertEqual(info.file_version, "1.2.3.4")
        self.assertEqual(info.product_version, "5.6.7.8")
        self.assertEqual(info.company_name(), "Umer OS Project")
        self.assertEqual(info.file_description(), "selftest pe")
        self.assertEqual(info.string_tables[0].lang_cp, "040904b0")

    def test_VerQueryValue(self) -> None:
        blob = version_info._build_fixture()
        q = version_info.VerQueryValue(
            blob, "\\StringFileInfo\\040904b0")
        self.assertIsNotNone(q)
        self.assertEqual(q[0], "StringFileInfo")
        self.assertEqual(q[1]["FileVersion"], "1.2.3.4")

    def test_malformed(self) -> None:
        self.assertIsNone(version_info.parse_version_info(b""))
        self.assertIsNone(version_info.parse_version_info(b"\x00\x00"))


# ---------------------------------------------------------------------------
# Delay Imports
# ---------------------------------------------------------------------------

class TestDelayImports(unittest.TestCase):
    def test_fixture_parse(self) -> None:
        blob = delay_imports._build_pe_with_delay_imports()
        pe = PeFile.from_bytes(blob)
        ddir = delay_imports.parse_delay_imports(pe)
        self.assertIsNotNone(ddir)
        self.assertEqual(len(ddir.entries), 1)
        self.assertEqual(ddir.entries[0].dll_name.upper(), "MYDLL.DLL")
        sym = ddir.entries[0].symbols[0]
        self.assertEqual(sym.name, "Foo")
        self.assertEqual(sym.hint, 42)

    def test_empty(self) -> None:
        from compatibility.pe_loader import _build_fake_pe
        pe = PeFile.from_bytes(_build_fake_pe())
        self.assertIsNone(delay_imports.parse_delay_imports(pe))


# ---------------------------------------------------------------------------
# Signed PE
# ---------------------------------------------------------------------------

class TestSignedPe(unittest.TestCase):
    def test_unsigned_image(self) -> None:
        from compatibility.pe_loader import _build_fake_pe
        pe = PeFile.from_bytes(_build_fake_pe())
        info = signed_pe.parse_certificates(pe)
        self.assertFalse(info.is_signed)
        self.assertEqual(info.signer_count, 0)

    def test_signed_image(self) -> None:
        import struct as _s
        from compatibility.pe_loader import _build_fake_pe, PeFile
        pe_bytes = bytearray(_build_fake_pe())
        cert_off = 0x400
        fake_blob = (b"CN=Test Signer\x00"
                     + b"O=Acme\x00"
                     + b"\x00" * 64)
        struct.pack_into("<IHH", pe_bytes, cert_off,
                         len(fake_blob) + 8,
                         signed_pe.WIN_CERT_REVISION_2_0,
                         signed_pe.WIN_CERT_TYPE_PKCS_SIGNED_DATA)
        pe_bytes[cert_off + 8: cert_off + 8 + len(fake_blob)] = fake_blob
        pe2 = PeFile.from_bytes(bytes(pe_bytes))
        n = pe2.optional_header.number_of_rva_and_sizes
        dd_off = (pe2.pe_offset + 4 + 20
                  + pe2.size_of_optional_header - n * 8)
        struct.pack_into("<II", pe_bytes, dd_off + 4 * 8,
                         cert_off, 8 + len(fake_blob))
        pe3 = PeFile.from_bytes(bytes(pe_bytes))
        info = signed_pe.parse_certificates(pe3)
        self.assertTrue(info.is_signed)
        self.assertTrue(info.has_security_directory)


# ---------------------------------------------------------------------------
# Winsock
# ---------------------------------------------------------------------------

class TestWinsock(unittest.TestCase):
    def setUp(self) -> None:
        winsock.WSACleanup()

    def tearDown(self) -> None:
        winsock.WSACleanup()

    def test_startup_cleanup(self) -> None:
        rc, data = winsock.WSAStartup(winsock.WSA_VERSION)
        self.assertEqual(rc, 0)
        self.assertEqual(data.version, winsock.WSA_VERSION)
        self.assertEqual(winsock.WSACleanup(), 0)

    def test_byte_order_and_inet(self) -> None:
        self.assertEqual(winsock.inet_addr("127.0.0.1"), 0x0100007F)
        self.assertEqual(winsock.inet_ntoa(0x0100007F), "127.0.0.1")
        self.assertEqual(
            winsock.htons(0x1234),
            winsock._stdlib_socket.htons(0x1234))

    def test_sockaddr_round_trip(self) -> None:
        addr = winsock.SockAddrIn(family=winsock.AF_INET,
                                   port=80, address="10.0.0.1")
        blob = addr.to_bytes()
        addr2 = winsock.SockAddrIn.from_bytes(blob)
        self.assertEqual(addr2.port, 80)
        self.assertEqual(addr2.address, "10.0.0.1")

    def test_socket_lifecycle(self) -> None:
        winsock.WSAStartup(winsock.WSA_VERSION)
        s = winsock.socket(winsock.AF_INET, winsock.SOCK_STREAM)
        self.assertNotEqual(s, winsock.INVALID_SOCKET)
        self.assertEqual(winsock.closesocket(s), 0)


# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------

class TestTimezone(unittest.TestCase):
    def test_system_time_round_trip(self) -> None:
        st = timezone.SystemTime(year=2025, month=6, day=15,
                                  hour=12, minute=34,
                                  second=56, millisecond=789)
        ft = timezone.SystemTimeToFileTime(st)
        self.assertIsNotNone(ft)
        st2 = timezone.FileTimeToSystemTime(ft)
        self.assertEqual((st2.year, st2.month, st2.day,
                          st2.hour, st2.minute, st2.second),
                         (2025, 6, 15, 12, 34, 56))

    def test_dos_round_trip(self) -> None:
        import datetime as _dt
        ft = timezone.FileTime.from_datetime(
            _dt.datetime(2024, 12, 31, 23, 59, 58,
                         tzinfo=_dt.timezone.utc))
        dos_date, dos_time = timezone.FileTimeToDosDateTime(ft)
        ft2 = timezone.DosDateTimeToFileTime(dos_date, dos_time)
        self.assertEqual(ft2.to_datetime().year, 2024)

    def test_tz_round_trip(self) -> None:
        tz = timezone.GetTimeZoneInformation()
        raw = tz.to_bytes()
        tz2 = timezone.TimeZoneInformation.from_bytes(raw)
        self.assertEqual(tz2.bias, tz.bias)

    def test_get_system_time(self) -> None:
        st = timezone.GetSystemTime()
        self.assertGreaterEqual(st.year, 2024)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
