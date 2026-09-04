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

    def test_drive_path(self) -> None:
        self.assertEqual(
            self.m.to_posix(r"C:\Windows"),
            os.path.join(self.m.compat_root, "C", "Windows"),
        )

    def test_unc(self) -> None:
        self.assertEqual(
            self.m.to_posix(r"\\server\share\path"),
            os.path.join(self.m.compat_root, "unc", "server", "share", "path"),
        )

    def test_drive_relative(self) -> None:
        self.m.set_drive_cwd("D", r"D:\Projects\UmerOS")
        self.assertEqual(
            self.m.to_posix("D:readme.txt"),
            os.path.join(self.m.compat_root, "D", "Projects", "UmerOS", "readme.txt"),
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
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            path = tf.name
            tf.write(b"hello world")
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
            os.remove(path)


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
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
