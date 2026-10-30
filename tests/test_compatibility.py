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
    shell_links, tokens, msi_runtime,
    environment, knownfolders, win_shell32,
    env_registry, env_dialog, installer_env,
)
from compatibility.pe_loader import PeFile, PeClass          # noqa: E402
from compatibility.dll_loader import DllLoader, ResolvedImport  # noqa: E402
from compatibility.env_dialog import DialogScope as DlgScope  # noqa: E402
from compatibility.env_dialog import EnvironmentDialog        # noqa: E402


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
            # The default mode does NOT execute.
            self.assertIsNone(r.run_result)
        finally:
            os.remove(path)

    def test_launch_and_execute_synthetic_pe(self) -> None:
        """The synthetic Win64 PE should execute end-to-end through
        ``WineShim.launch(execute=True)``."""
        from compatibility import win32_runner
        blob = win32_runner.build_gettickcount_pe()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tf:
            tf.write(blob)
            path = tf.name
        try:
            shim = wine_shim.WineShim()
            r = shim.launch(path, execute=True, max_steps=100)
            self.assertIsNotNone(r.run_result,
                f"run_result is None; issues={r.issues}")
            self.assertIsNone(r.run_result.error,
                f"emulator error: {r.run_result.error}")
            self.assertEqual(r.run_result.exit_code, 0)
            self.assertTrue(r.run_result.halted)
        finally:
            os.remove(path)

class TestX86Runner(unittest.TestCase):
    """Smoke-tests for the pure-Python emulator."""

    # ----------------------------------------------------------------
    # Basic-block JIT
    # ----------------------------------------------------------------

    def _run_both_ways(self, code: bytes, *, steps: int = 64,
                       setup=None):
        """Execute ``code`` once through the interpreter and once
        through the JIT and assert both produce the same final state.

        This is the regression test for the whole class of "JIT decodes
        a different instruction length than the interpreter" bugs that
        silently desync the decoder.
        """
        from compatibility import x86_runner
        results = []
        for use_jit in (False, True):
            emu = x86_runner.Emulator()
            emu.mem.write(emu.base, code)
            emu.regs.set(15, emu.base)
            if setup is not None:
                setup(emu)
            emu.run(max_steps=steps, use_jit=use_jit,
                    hot_loop_min_steps=10 ** 9)
            results.append((
                list(emu.regs.r),
                emu.regs.get(15),
                (emu.regs.cf, emu.regs.zf, emu.regs.sf, emu.regs.of),
            ))
        self.assertEqual(results[0][1], results[1][1],
                         "interpreter and JIT disagree on final RIP")
        self.assertEqual(results[0][0], results[1][0],
                         "interpreter and JIT disagree on registers")
        self.assertEqual(results[0][2], results[1][2],
                         "interpreter and JIT disagree on flags")
        return results[0]

    def test_jit_matches_interpreter_on_alu_block(self) -> None:
        """A block of mov/add/sub/cmp/xor/test must behave identically
        whether it is interpreted or JIT-compiled."""
        code = (
            b"\x48\xB8\x2A\x00\x00\x00\x00\x00\x00\x00"  # mov rax, 42
            b"\x48\x83\xC0\x05"                        # add rax, 5
            b"\x48\x89\xC3"                            # mov rbx, rax
            b"\x48\x83\xEB\x0A"                        # sub rbx, 10
            b"\x48\x31\xD2"                            # xor rdx, rdx
            b"\x48\x85\xC3"                            # test rbx, rbx
            b"\xF4"                                    # hlt
        )
        regs, rip, flags = self._run_both_ways(code)
        self.assertEqual(regs[0], 47)     # rax
        self.assertEqual(regs[3], 37)     # rbx
        self.assertEqual(regs[2], 0)      # rdx
        self.assertEqual(flags[1], 0)     # zf clear (rbx != 0)

    def test_jit_matches_interpreter_on_stack_frame(self) -> None:
        """Instructions that touch [rsp+disp] exercise the ModR/M
        emitter's addressing-mode code (including the disp32 path)."""
        code = (
            b"\x48\x83\xEC\x20"                # sub rsp, 0x20
            b"\x48\xC7\x44\x24\x08\x2A\x00\x00\x00"   # mov qword [rsp+8], 42
            b"\x48\x8B\x44\x24\x08"            # mov rax, [rsp+8]
            b"\x48\x8B\x4C\x24\x10"            # mov rcx, [rsp+0x10]
            b"\xF4"                            # hlt
        )
        regs, rip, _flags = self._run_both_ways(code)
        self.assertEqual(regs[0], 42)

    def test_jit_matches_interpreter_on_rip_relative(self) -> None:
        """RIP-relative loads must resolve against the *end* of the
        instruction.  This is the regression test for the bug where
        the JIT emitted a bare constant address instead."""
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        # base+0 : 48 8B 05 <disp32>   mov rax, [rip+disp]
        # base+7 : F4                  hlt
        # base+8 : the qword we want to load lives here.
        disp = 8 - 7                        # rip after insn == base+7
        code = b"\x48\x8B\x05" + struct.pack("<i", disp) + b"\xF4"
        emu.mem.write(emu.base, code)
        emu.mem.write_u64(emu.base + 8, 0x1122334455667788)
        emu.regs.set(15, emu.base)
        emu.run(max_steps=8, use_jit=True, hot_loop_min_steps=10 ** 9)
        self.assertEqual(emu.regs.get(0), 0x1122334455667788)

    def test_jit_matches_interpreter_on_branches(self) -> None:
        """Conditional and unconditional branches must land on the
        same address from either execution path."""
        #   +0  48 83 F8 05    cmp rax, 5        (4 bytes)
        #   +4  74 06          je +6  -> +12     (2 bytes)
        #   +6  90 90 90 90 90 90   padding     (6 bytes)
        #   +12 F4             hlt
        code = (
            b"\x48\x83\xF8\x05"
            b"\x74\x06"
            b"\x90\x90\x90\x90\x90\x90"
            b"\xF4"
        )

        def setup(emu):
            emu.regs.set(0, 5)

        regs, rip, flags = self._run_both_ways(code, setup=setup)
        # The je is taken, so we resume at the hlt.
        self.assertEqual(rip - 0x400000, 12)
        self.assertEqual(flags[1], 1)     # zf set by cmp rax, 5

    def test_jit_matches_interpreter_on_branch_not_taken(self) -> None:
        """The not-taken path of the same branch must agree too."""
        #   +0  48 83 F8 05    cmp rax, 5        (4 bytes)
        #   +4  74 06          je +6  (not taken)
        #   +6  F4             hlt
        #   +7  90 90 90 90 90 90   skipped padding
        code = (
            b"\x48\x83\xF8\x05"
            b"\x74\x06"
            b"\xF4"
            b"\x90\x90\x90\x90\x90\x90"
        )

        def setup(emu):
            emu.regs.set(0, 9)

        regs, rip, flags = self._run_both_ways(code, setup=setup)
        self.assertEqual(rip - 0x400000, 6)
        self.assertEqual(flags[1], 0)     # zf clear

    def test_jit_rejects_blocks_that_do_not_decode_consistently(
            self) -> None:
        """``_validate_block`` must reject a block whose declared
        length disagrees with an independent instruction-length walk.
        """
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        # mov rax, imm64 ; hlt -> a 10-byte block that should validate.
        code = b"\x48\xB8\x01\x00\x00\x00\x00\x00\x00\x00\xF4"
        emu.mem.write(emu.base, code)
        self.assertTrue(emu._validate_block(emu.base, 11))
        # Claiming the same block is 7 bytes long must be rejected.
        self.assertFalse(emu._validate_block(emu.base, 7))

    def test_jit_does_not_execute_blocks_during_validation(self) -> None:
        """Validation must be side-effect free: it may not dispatch
        Win32 thunks or mutate memory."""
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        calls: list[str] = []

        def spy(_emu):            # pragma: no cover - should not run
            calls.append("thunk")
            return 0

        addr = emu.install_thunk("KERNEL32.dll!Test", spy)
        emu.regs.set(15, addr)     # would call the thunk via 0xCC
        # A block that starts exactly at the thunk's 0xCC byte.
        emu._validate_block(addr, 1)
        self.assertEqual(calls, [],
                         "validation must not dispatch thunks")

    # ----------------------------------------------------------------
    # Existing interpreter tests
    # ----------------------------------------------------------------

    def test_selftest_passes(self) -> None:
        from compatibility import x86_runner
        self.assertTrue(x86_runner._selftest())

    def test_push_imm32_sign_extends(self) -> None:
        """`push imm32` should sign-extend to 64 bits in 64-bit mode."""
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        # push -1 ; hlt
        code = b"\x68\xFF\xFF\xFF\xFF" + b"\xF4"
        emu.mem.write(emu.base, code)
        emu.regs.set(15, emu.base)
        emu.run(max_steps=10)
        self.assertEqual(emu.mem.read_u64(emu.stack_top - 0x100 - 8),
                         0xFFFFFFFFFFFFFFFF)

    def test_ret_imm16_cleans_stack(self) -> None:
        """`ret imm16` should pop RIP then add imm16 to rsp."""
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        rsp0 = emu.regs.get(4)
        # Layout:
        #   base+0:  push return_addr   ; 5 bytes, RSP -= 8
        #   base+5:  ret 8              ; 3 bytes (pop + add 8)
        #   base+8:  hlt                ; 1 byte
        ret_target = emu.base + 8           # where ret should land (hlt)
        emu.mem.write(emu.base, b"\x68" + struct.pack("<I", ret_target))
        emu.mem.write(emu.base + 5, b"\xC2\x08\x00\xF4")
        emu.regs.set(15, emu.base)
        emu.run(max_steps=10)
        # `push imm32` -> RSP = rsp0 - 8.
        # `ret 8` pops the 8-byte return addr (RSP -> rsp0) and then
        # adds 8 (RSP -> rsp0 + 8).
        self.assertEqual(emu.regs.get(4), rsp0 + 8)
        self.assertEqual(emu.regs.get(15), ret_target)

    def test_arith_and_flags(self) -> None:
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        # mov eax, 0x2A; add rax, 5; cmp eax, 0x2F; hlt
        code = (
            b"\xB8\x2A\x00\x00\x00"        # mov eax, 0x2A
            b"\x48\x83\xC0\x05"            # add rax, 5
            b"\x3D\x2F\x00\x00\x00"        # cmp eax, 0x2F
            b"\xF4"                        # hlt
        )
        emu.mem.write(emu.base, code)
        emu.regs.set(15, emu.base)
        emu.run(max_steps=20)
        self.assertEqual(emu.regs.get(0), 0x2F)
        self.assertEqual(emu.regs.zf, 1)
        self.assertEqual(emu.regs.cf, 0)

    def test_thunk_dispatch(self) -> None:
        """A thunk should run the registered callable and return to caller."""
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        # Install a thunk that returns 0x42 in rax.
        thunk = emu.install_thunk("demo!SetValue", lambda e: e.regs.set(0, 0x42))
        # Write a tiny program: sub rsp, 0x28; call [rip+disp]; add rsp, 0x28; hlt
        # ``[rip+disp]`` reads the 8-byte address to call from the
        # resolved address.  We arrange that address by writing the
        # thunk address into a known memory location.
        iat_addr = emu.base + 0x100        # pretend IAT slot
        emu.mem.write_u64(iat_addr, thunk)
        call_rip_next = emu.base + 4 + 6
        disp = iat_addr - call_rip_next    # RIP-relative disp
        code = bytearray()
        code += b"\x48\x83\xEC\x28"                                   # sub rsp, 0x28
        code += b"\xFF\x15" + struct.pack("<i", disp)                 # call [rip+disp]
        code += b"\x48\x83\xC4\x28"                                   # add rsp, 0x28
        code += b"\xF4"                                               # hlt
        emu.mem.write(emu.base, bytes(code))
        emu.regs.set(15, emu.base)
        emu.run(max_steps=20)
        self.assertEqual(emu.regs.get(0), 0x42)
        self.assertEqual(emu.regs.r[4], emu.stack_top - 0x100)  # rsp restored

    def test_rip_relative_addressing(self) -> None:
        """`mov [rip+disp], rax` should write to RIP_next + disp."""
        from compatibility import x86_runner
        emu = x86_runner.Emulator()
        # Place rax = 0xCAFEBABE; then write rax to mem[0x3000] via
        # RIP-relative addressing.
        emu.regs.set(0, 0xCAFEBABE)
        # Layout: mov rax, 0xCAFEBABE (10 bytes), mov [rip+disp32], rax (7 bytes),
        # hlt (1 byte).
        rip_after_movimm = emu.base + 10    # 10-byte instruction
        rip_after_memwrite = emu.base + 17   # 7-byte instruction
        target = 0x3000
        disp = target - rip_after_memwrite
        code = bytearray()
        code += b"\x48\xB8" + struct.pack("<Q", 0xCAFEBABE)        # mov rax, imm64
        code += b"\x48\x89\x05" + struct.pack("<i", disp)         # mov [rip+disp], rax
        code += b"\xF4"
        emu.mem.write(emu.base, bytes(code))
        emu.regs.set(15, emu.base)
        emu.run(max_steps=20)
        self.assertEqual(emu.mem.read_u64(target), 0xCAFEBABE)


# ---------------------------------------------------------------------------
# Win32 PE runner
# ---------------------------------------------------------------------------

class TestWin32Runner(unittest.TestCase):
    """End-to-end test of the Win32 PE loader + emulator."""

    def test_selftest_passes(self) -> None:
        from compatibility import win32_runner
        self.assertTrue(win32_runner._selftest())

    def test_synthetic_pe_sections(self) -> None:
        """The hand-assembled PE must have .text/.rdata/.data sections
        with file-aligned bodies."""
        from compatibility import win32_runner
        blob = win32_runner.build_gettickcount_pe()
        pe = PeFile.from_bytes(blob)
        names = [s.name for s in pe.sections]
        self.assertEqual(names, [".text", ".rdata", ".data"])
        # All raw_size must be > 0 and file-aligned to 0x100.
        for s in pe.sections:
            self.assertGreater(s.raw_size, 0)
            self.assertEqual(s.raw_offset % 0x100, 0)

    def test_runs_gettickcount_through_emulator(self) -> None:
        """Load the synthetic PE, dispatch GetTickCount to a stub,
        and verify the result lands in the .data section."""
        from compatibility import win32_runner

        def _fake_tick(emu):
            emu.regs.set(0, 12345)

        blob = win32_runner.build_gettickcount_pe()
        pe = PeFile.from_bytes(blob)
        runner = win32_runner.Win32Runner(
            image_base=int(pe.optional_header.image_base),
            imports={"KERNEL32.DLL": {"GetTickCount": _fake_tick}},
        )
        runner.load_pe(pe, raw_image=blob)
        runner.emulator.regs.set(15, 0x1000)
        rc = runner.emulator.run(max_steps=50)
        self.assertEqual(rc, 0)
        self.assertEqual(runner.emulator.mem.read_u64(0x3000), 12345)
        self.assertEqual(runner.emulator.mem.read_u64(0x3008), 12345)
        # The thunk was installed exactly once.
        self.assertEqual(runner.emulator._thunk_count, 1)

    def test_unknown_import_returns_zero(self) -> None:
        """Imports that have no stub should still resolve -- via the
        missing-stub shim that returns 0."""
        from compatibility import win32_runner

        blob = win32_runner.build_gettickcount_pe()
        pe = PeFile.from_bytes(blob)
        # Empty import map -- every import is "missing".
        runner = win32_runner.Win32Runner(
            image_base=int(pe.optional_header.image_base),
            imports={},
        )
        runner.load_pe(pe, raw_image=blob)
        runner.emulator.regs.set(15, 0x1000)
        rc = runner.emulator.run(max_steps=50)
        self.assertEqual(rc, 0)
        # Both stores should be 0 (the missing-stub return value).
        self.assertEqual(runner.emulator.mem.read_u64(0x3000), 0)
        self.assertEqual(runner.emulator.mem.read_u64(0x3008), 0)


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
# Shell Links
# ---------------------------------------------------------------------------

class TestShellLinks(unittest.TestCase):
    def test_build_and_parse(self) -> None:
        blob = shell_links.build_shell_link(
            "C:\\Windows\\notepad.exe",
            working_dir="C:\\Windows",
            arguments="test.txt",
            description="Open test.txt",
        )
        link = shell_links.parse_shell_link(blob)
        self.assertIsNotNone(link)
        self.assertEqual(link.target_path,
                         "C:\\Windows\\notepad.exe")
        self.assertEqual(link.strings.working_dir, "C:\\Windows")
        self.assertEqual(link.strings.command_line_args, "test.txt")
        self.assertEqual(link.strings.name, "Open test.txt")
        self.assertIn("ARCHIVE", link.attribute_names())

    def test_ishelllink_setpath(self) -> None:
        blob = shell_links.build_shell_link("C:\\Windows\\calc.exe")
        link = shell_links.parse_shell_link(blob)
        shell_links.IShellLinkW_SetPath(link, "C:\\foo\\bar.exe")
        self.assertEqual(shell_links.IShellLinkW_GetPath(link),
                         "C:\\foo\\bar.exe")

    def test_truncated(self) -> None:
        self.assertIsNone(shell_links.parse_shell_link(b""))


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

class TestTokens(unittest.TestCase):
    def test_self_token_elevated(self) -> None:
        h, err = tokens.OpenProcessToken(
            0xFFFFFFFF, tokens.TOKEN_QUERY)
        self.assertEqual(err, 0)
        self.assertNotEqual(h, 0)
        elev = tokens.GetTokenInformation(
            h, tokens.TokenInformationClass.TokenElevation)
        self.assertIsInstance(elev, tokens.TokenElevation)
        self.assertTrue(elev.is_elevated)
        self.assertTrue(tokens.IsUserAdmin(h))
        self.assertTrue(tokens.CloseToken(h))

    def test_lookup_privilege(self) -> None:
        low, high = tokens.LookupPrivilegeValue(None, "SeShutdownPrivilege")
        self.assertNotEqual((low, high), (0, 0))
        self.assertEqual(tokens.LookupPrivilegeValue(None, "SeNope"), (0, 0))

    def test_adjust_privileges(self) -> None:
        h, _ = tokens.OpenProcessToken(0xFFFFFFFF, tokens.TOKEN_QUERY)
        lp = tokens.LuidAndAttributes(
            luid=tokens.Luid(*tokens.LUID_SE_SHUTDOWN_PRIVILEGE),
            attributes=0x80000000)
        self.assertEqual(tokens.AdjustTokenPrivileges(h, False, [lp], 0),
                         0)
        tokens.CloseToken(h)


# ---------------------------------------------------------------------------
# MSI Runtime
# ---------------------------------------------------------------------------

class TestMsiRuntime(unittest.TestCase):
    def test_open_get_set(self) -> None:
        handle = []
        rc = msi_runtime.MsiOpenPackageA("C:\\Installer\\MyApp.msi", handle)
        self.assertEqual(rc, 0)
        self.assertTrue(handle)
        rc, name = msi_runtime.MsiGetPropertyA(
            handle[0], "ProductName", None)
        self.assertEqual(rc, 0)
        self.assertTrue(name)
        self.assertEqual(msi_runtime.MsiSetPropertyA(
            handle[0], "INSTALLDIR", "C:\\Foo"), 0)
        rc, val = msi_runtime.MsiGetPropertyA(
            handle[0], "INSTALLDIR", None)
        self.assertEqual(val, "C:\\Foo")

    def test_features(self) -> None:
        handle = []
        msi_runtime.MsiOpenPackageA("C:\\Installer\\B.msi", handle)
        rc, state = msi_runtime.MsiGetFeatureStateA(
            handle[0], "MainFeature")
        self.assertEqual(rc, 0)
        self.assertEqual(state, msi_runtime.INSTALLSTATE_UNKNOWN)
        msi_runtime.MsiSetFeatureStateA(
            handle[0], "MainFeature", msi_runtime.INSTALLSTATE_LOCAL)
        rc, state = msi_runtime.MsiGetFeatureStateA(
            handle[0], "MainFeature")
        self.assertEqual(state, msi_runtime.INSTALLSTATE_LOCAL)

    def test_close(self) -> None:
        handle = []
        msi_runtime.MsiOpenPackageA("C:\\Installer\\C.msi", handle)
        msi_runtime.MsiCloseHandle(handle[0])
        rc, _ = msi_runtime.MsiGetPropertyA(
            handle[0], "ProductName", None)
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

class TestEnvironment(unittest.TestCase):
    """Win32 environment-variable handling."""

    def test_selftest_passes(self) -> None:
        from compatibility import environment
        self.assertTrue(environment._selftest())

    def test_canonical_win10_vars_present(self) -> None:
        from compatibility import environment
        d = environment.get_default_block()
        for name in ("SystemRoot", "ComSpec", "OS", "PATHEXT",
                     "AppData", "LocalAppData", "ProgramData",
                     "Public", "ProgramFiles", "ProgramFiles(x86)",
                     "USERPROFILE", "HomeDrive", "HomePath",
                     "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"):
            self.assertIsNotNone(d.get(name), f"missing canonical var {name}")

    def test_case_insensitive_lookup(self) -> None:
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        blk["PATH"] = r"C:\Windows"
        blk["Path"] = r"C:\Windows;overridden"
        self.assertEqual(blk["PATH"], r"C:\Windows;overridden")
        self.assertEqual(blk["path"], r"C:\Windows;overridden")
        self.assertEqual(len(blk), 1)

    def test_get_and_set_win32_a(self) -> None:
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        self.assertIsNone(environment.GetEnvironmentVariableA("MISSING", blk))
        self.assertTrue(environment.SetEnvironmentVariableA("X", "1", blk))
        self.assertEqual(environment.GetEnvironmentVariableA("X", blk), "1")
        self.assertTrue(environment.SetEnvironmentVariableA("X", None, blk))
        self.assertIsNone(environment.GetEnvironmentVariableA("X", blk))

    def test_expand_environment_strings(self) -> None:
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        blk["FOO"] = "%BAR%"
        blk["bar"] = "baz"
        self.assertEqual(environment.ExpandEnvironmentStringsA("%FOO%!", blk),
                         "baz!")
        # Unresolvable: stays as literal.
        self.assertEqual(environment.ExpandEnvironmentStringsA(
            "a %NOPE% b", blk), "a %NOPE% b")
        # Recursive.
        blk["A"] = "%B%"
        blk["B"] = "%C%"
        blk["C"] = "leaf"
        self.assertEqual(environment.ExpandEnvironmentStringsA("%A%", blk),
                         "leaf")
        # Cyclic guard.
        blk["LOOP"] = "%LOOP%"
        # Must not stack-overflow -- the cap kicks in and the literal
        # is returned.
        result = environment.ExpandEnvironmentStringsA("%LOOP%", blk)
        self.assertEqual(result, "%LOOP%")

    def test_pathext_match(self) -> None:
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        blk["PATHEXT"] = ".COM;.EXE;.BAT"
        self.assertTrue(blk.matches_pathext("foo.EXE"))
        self.assertTrue(blk.matches_pathext("bar.bat"))
        self.assertFalse(blk.matches_pathext("readme.txt"))

    def test_path_add_remove(self) -> None:
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        blk["PATH"] = r"C:\A;C:\B"
        self.assertTrue(blk.add_path_entry(r"C:\C"))
        self.assertEqual(blk.get("PATH"), r"C:\A;C:\B;C:\C")
        # Duplicate -> no-op.
        self.assertFalse(blk.add_path_entry(r"C:\C"))
        # at_front moves the entry to the head.
        self.assertTrue(blk.add_path_entry(r"C:\Z", at_front=True))
        self.assertEqual(blk.get("PATH"), r"C:\Z;C:\A;C:\B;C:\C")
        self.assertTrue(blk.remove_path_entry(r"C:\A"))
        self.assertEqual(blk.get("PATH"), r"C:\Z;C:\B;C:\C")

    def test_to_zz_block_round_trip(self) -> None:
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        blk["PATH"] = r"C:\Windows;overridden"
        z = blk.to_zz_block()
        # The block ends with the empty terminator.
        self.assertTrue(z.endswith(b"\x00\x00\x00\x00"))
        # The decoded form should be "PATH=C:\Windows;overridden".
        decoded = z[:-2].decode("utf-16-le")
        parts = [p for p in decoded.split("\x00") if p]
        self.assertEqual(parts, [r"PATH=C:\Windows;overridden"])

    def test_dynamic_cd_resolves_to_cwd(self) -> None:
        from compatibility import environment
        s = environment.ExpandEnvironmentStringsA("cwd=%CD%")
        self.assertTrue(s.startswith("cwd="))
        self.assertGreater(len(s), 4)

    def test_set_errorlevel_then_expand(self) -> None:
        from compatibility import environment
        environment.set_errorlevel(42)
        s = environment.ExpandEnvironmentStringsA("rc=%ERRORLEVEL%")
        self.assertEqual(s, "rc=42")
        environment.set_errorlevel(0)

    def test_scopes_distinct(self) -> None:
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        blk["X"] = "process"
        self.assertEqual(blk.scope_of("X"), environment.EnvScope.PROCESS)
        blk["Y"] = "system"
        blk._scopes["Y"] = environment.EnvScope.SYSTEM
        self.assertEqual(blk.scope_of("Y"), environment.EnvScope.SYSTEM)


# ---------------------------------------------------------------------------
# Known folders (KNOWNFOLDERID / CSIDL)
# ---------------------------------------------------------------------------

class TestKnownFolders(unittest.TestCase):
    """The Windows 10 Known Folder catalogue."""

    def test_selftest_passes(self) -> None:
        from compatibility import knownfolders
        self.assertTrue(knownfolders._selftest())

    def test_csidl_values_match_shlobj(self) -> None:
        from compatibility.knownfolders import Csidl
        expected = {
            "DESKTOP": 0x0000, "INTERNET": 0x0001, "PROGRAMS": 0x0002,
            "CONTROLS": 0x0003, "PRINTERS": 0x0004, "PERSONAL": 0x0005,
            "FAVORITES": 0x0006, "STARTUP": 0x0007, "RECENT": 0x0008,
            "SENDTO": 0x0009, "BITBUCKET": 0x000A, "STARTMENU": 0x000B,
            "MYMUSIC": 0x000D, "MYVIDEO": 0x000E, "DESKTOPDIRECTORY": 0x0010,
            "DRIVES": 0x0011, "NETWORK": 0x0012, "NETHOOD": 0x0013,
            "FONTS": 0x0014, "TEMPLATES": 0x0015, "COMMON_STARTMENU": 0x0016,
            "COMMON_PROGRAMS": 0x0017, "COMMON_STARTUP": 0x0018,
            "COMMON_DESKTOPDIRECTORY": 0x0019, "APPDATA": 0x001A,
            "PRINTHOOD": 0x001B, "LOCAL_APPDATA": 0x001C, "ALTSTARTUP": 0x001D,
            "COMMON_ALTSTARTUP": 0x001E, "COMMON_FAVORITES": 0x001F,
            "INTERNET_CACHE": 0x0020, "COOKIES": 0x0021, "HISTORY": 0x0022,
            "COMMON_APPDATA": 0x0023, "WINDOWS": 0x0024, "SYSTEM": 0x0025,
            "PROGRAM_FILES": 0x0026, "MYPICTURES": 0x0027, "PROFILE": 0x0028,
            "SYSTEMX86": 0x0029, "PROGRAM_FILESX86": 0x002A,
            "PROGRAM_FILES_COMMON": 0x002B, "PROGRAM_FILES_COMMONX86": 0x002C,
            "COMMON_TEMPLATES": 0x002D, "COMMON_DOCUMENTS": 0x002E,
            "COMMON_ADMINTOOLS": 0x002F, "ADMINTOOLS": 0x0030,
            "CONNECTIONS": 0x0031, "COMMON_MUSIC": 0x0035,
            "COMMON_PICTURES": 0x0036, "COMMON_VIDEO": 0x0037,
            "RESOURCES": 0x0038, "RESOURCES_LOCALIZED": 0x0039,
            "COMMON_OEM_LINKS": 0x003A, "CDBURN_AREA": 0x003B,
            "COMPUTERSNEARME": 0x003D,
        }
        for name, value in expected.items():
            self.assertEqual(int(getattr(Csidl, name)), value,
                             f"CSIDL_{name} should be 0x{value:04X}")

    def test_mydocuments_is_an_alias_of_personal(self) -> None:
        from compatibility.knownfolders import Csidl
        self.assertIs(Csidl.MYDOCUMENTS, Csidl.PERSONAL)

    def test_catalogue_is_complete_and_unique(self) -> None:
        from compatibility import knownfolders
        self.assertGreaterEqual(len(knownfolders.KNOWN_FOLDERS), 120)
        guids = [k.guid for k in knownfolders.KNOWN_FOLDERS.values()]
        self.assertEqual(len(guids), len(set(guids)))
        for guid in guids:
            self.assertTrue(guid.startswith("{") and guid.endswith("}"))

    def test_every_folder_type_is_represented(self) -> None:
        from compatibility import knownfolders
        for kind in knownfolders.KnownFolderType:
            self.assertTrue(knownfolders.list_known_folders(kind),
                            f"no folders of type {kind}")

    def test_virtual_folders_have_no_path(self) -> None:
        from compatibility import knownfolders
        for kf in knownfolders.list_known_folders(
                knownfolders.KnownFolderType.VIRTUAL):
            self.assertIsNone(kf.default_path, kf.name)
            self.assertTrue(kf.shell_path.startswith("::{"))

    def test_physical_folders_have_a_template(self) -> None:
        from compatibility import knownfolders
        for kf in knownfolders.list_known_folders():
            if kf.folder_type is knownfolders.KnownFolderType.VIRTUAL:
                continue
            self.assertTrue(kf.default_path, kf.name)
            self.assertIn("%", kf.default_path, kf.name)

    def test_resolve_by_name_and_by_guid(self) -> None:
        from compatibility import knownfolders
        by_name = knownfolders.resolve_known_folder("FOLDERID_Desktop")
        by_guid = knownfolders.resolve_known_folder(
            "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}")
        self.assertEqual(by_name, by_guid)
        self.assertTrue(by_name.lower().endswith(r"\desktop"))

    def test_resolve_unknown_folder_raises(self) -> None:
        from compatibility import knownfolders
        with self.assertRaises(KeyError):
            knownfolders.resolve_known_folder("FOLDERID_NotAThing")

    def test_redirection_matrix(self) -> None:
        from compatibility import knownfolders
        p64 = knownfolders.resolve_known_folder(
            "FOLDERID_ProgramFiles", app_is_32bit=False, os_is_64bit=True)
        p32 = knownfolders.resolve_known_folder(
            "FOLDERID_ProgramFiles", app_is_32bit=True, os_is_64bit=True)
        self.assertNotIn("(x86)", p64)
        self.assertIn("Program Files (x86)", p32)

        c64 = knownfolders.resolve_known_folder(
            "FOLDERID_ProgramFilesCommon", app_is_32bit=False,
            os_is_64bit=True)
        c32 = knownfolders.resolve_known_folder(
            "FOLDERID_ProgramFilesCommon", app_is_32bit=True,
            os_is_64bit=True)
        self.assertNotIn("(x86)", c64)
        self.assertIn("(x86)", c32)

        s32 = knownfolders.resolve_known_folder(
            "FOLDERID_System", app_is_32bit=False, os_is_64bit=True)
        s86 = knownfolders.resolve_known_folder(
            "FOLDERID_SystemX86", app_is_32bit=False, os_is_64bit=True)
        self.assertTrue(s32.lower().endswith(r"\system32"))
        self.assertTrue(s86.lower().endswith(r"\syswow64"))

    def test_x64_only_folder_rejects_32bit_caller(self) -> None:
        from compatibility import knownfolders
        with self.assertRaises(ValueError):
            knownfolders.resolve_known_folder("FOLDERID_ProgramFilesX64",
                                             app_is_32bit=True,
                                             os_is_64bit=True)
        # A 64-bit caller on a 64-bit OS is fine.
        path = knownfolders.resolve_known_folder("FOLDERID_ProgramFilesX64",
                                                 app_is_32bit=False,
                                                 os_is_64bit=True)
        self.assertTrue(path)

    def test_resolve_csidl(self) -> None:
        from compatibility import knownfolders
        profile = knownfolders.resolve_csidl(0x0028)     # CSIDL_PROFILE
        self.assertTrue(profile)
        sysdir = knownfolders.resolve_csidl(0x0025)      # CSIDL_SYSTEM
        self.assertTrue(sysdir.lower().endswith(r"\system32"))

    def test_virtual_csidl_resolves_to_shell_namespace(self) -> None:
        from compatibility import knownfolders
        bin = knownfolders.resolve_csidl(0x000A)         # CSIDL_BITBUCKET
        self.assertTrue(bin.startswith("::{"))

    def test_unknown_csidl_raises(self) -> None:
        from compatibility import knownfolders
        with self.assertRaises(KeyError):
            knownfolders.resolve_csidl(0x7FFF)

    def test_csidl_to_known_folder_mapping(self) -> None:
        from compatibility import knownfolders
        self.assertEqual(
            knownfolders.csidl_to_known_folder(0x001A),
            "FOLDERID_RoamingAppData")
        self.assertEqual(
            knownfolders.csidl_to_known_folder(0x0005),
            "FOLDERID_Documents")
        self.assertIsNone(knownfolders.csidl_to_known_folder(0x7FFF))


# ---------------------------------------------------------------------------
# shell32.dll folder-path API
# ---------------------------------------------------------------------------

class TestShell32(unittest.TestCase):
    """``SHGetFolderPath`` / ``SHGetKnownFolderPath``."""

    def test_selftest_passes(self) -> None:
        from compatibility import win_shell32
        self.assertTrue(win_shell32._selftest())

    def test_shget_folder_path(self) -> None:
        from compatibility import win_shell32
        path = win_shell32.SHGetFolderPathA(0, 0x001A, 0, 0)
        self.assertTrue(path.lower().endswith(r"appdata\roaming"))

    def test_csidl_flags_are_masked_off(self) -> None:
        from compatibility import win_shell32
        plain = win_shell32.SHGetFolderPathA(0, 0x001A, 0, 0)
        flagged = win_shell32.SHGetFolderPathA(0, 0x001A | 0x8000, 0, 0)
        self.assertEqual(plain, flagged)

    def test_known_folder_by_name_and_guid(self) -> None:
        from compatibility import win_shell32
        by_name = win_shell32.SHGetKnownFolderPath("FOLDERID_Documents")
        by_guid = win_shell32.SHGetKnownFolderPath(
            "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")
        self.assertEqual(by_name, by_guid)
        self.assertTrue(by_name)

    def test_unknown_identifier_returns_empty_string(self) -> None:
        from compatibility import win_shell32
        self.assertEqual(
            win_shell32.SHGetKnownFolderPath(
                "{00000000-0000-0000-0000-000000000000}"), "")
        self.assertEqual(win_shell32.SHGetFolderPathA(0, 0x7FFF, 0, 0), "")

    def test_set_known_folder_path_is_observable(self) -> None:
        from compatibility import win_shell32
        try:
            self.assertTrue(win_shell32.SHSetKnownFolderPath(
                "FOLDERID_Documents", 0, 0, r"C:\Docs"))
            self.assertEqual(
                win_shell32.SHGetKnownFolderPath("FOLDERID_Documents"),
                r"C:\Docs")
        finally:
            win_shell32.SHSetKnownFolderPath("FOLDERID_Documents", 0, 0, "")
        self.assertNotEqual(
            win_shell32.SHGetKnownFolderPath("FOLDERID_Documents"), r"C:\Docs")

    def test_virtual_folder_returns_shell_path(self) -> None:
        from compatibility import win_shell32
        self.assertTrue(
            win_shell32.SHGetKnownFolderPath(
                "FOLDERID_RecycleBinFolder").startswith("::{"))

    def test_exports_surface(self) -> None:
        from compatibility import win_shell32
        for name in ("SHGetFolderPathA", "SHGetKnownFolderPath",
                     "SHSetKnownFolderPath"):
            self.assertIn(name, win_shell32.EXPORTS)


# ---------------------------------------------------------------------------
# Environment variables: catalogue, scopes and inspection
# ---------------------------------------------------------------------------

class TestEnvironmentCatalogue(unittest.TestCase):
    """The USMT-recognised variable catalogue."""

    def test_usmt_context_sizes(self) -> None:
        from compatibility import environment
        self.assertEqual(len(environment.USMT_USER_AND_SYSTEM), 57)
        self.assertEqual(len(environment.USMT_USER_ONLY), 40)
        self.assertEqual(len(environment.USMT_RECOGNISED), 97)

    def test_usmt_contexts_are_disjoint(self) -> None:
        from compatibility import environment
        overlap = (set(environment.USMT_USER_AND_SYSTEM)
                   & set(environment.USMT_USER_ONLY))
        self.assertEqual(overlap, set())

    def test_recognised_is_a_superset_of_usmt(self) -> None:
        from compatibility import environment
        self.assertTrue(set(environment.USMT_RECOGNISED)
                        <= set(environment.WIN10_RECOGNISED))
        for name in ("PATH", "APPDATA", "ProgramFiles",
                     "ProgramFiles(x86)", "SystemRoot", "ComSpec"):
            self.assertIn(name, environment.WIN10_RECOGNISED)
            self.assertTrue(environment.is_recognised(name))

    def test_known_csidl_names_are_recognised(self) -> None:
        from compatibility import environment
        for name in ("CSIDL_APPDATA", "CSIDL_COMMON_APPDATA",
                     "CSIDL_DEFAULT_DESKTOP", "CSIDL_SYSTEM",
                     "CSIDL_WINDOWS", "CSIDL_PROGRAM_FILES"):
            self.assertTrue(environment.is_recognised(name), name)

    def test_usmt_context_lookup(self) -> None:
        from compatibility import environment
        self.assertIn("UserAndSystem",
                      environment.usmt_context_for("CSIDL_APPDATA"))
        self.assertIn("User", environment.usmt_context_for("CSIDL_APPDATA"))
        self.assertNotIn("System",
                         environment.usmt_context_for("CSIDL_APPDATA"))

    def test_resolve_alias(self) -> None:
        from compatibility import environment
        self.assertEqual(environment.resolve_usmt_variable("PROGRAMFILES"),
                         r"C:\Program Files")
        self.assertEqual(environment.resolve_usmt_variable("PROGRAMFILES(X86)"),
                         r"C:\Program Files (x86)")

    def test_resolve_template(self) -> None:
        from compatibility import environment
        self.assertEqual(
            environment.resolve_usmt_variable("CSIDL_DEFAULT_DESKTOP"),
            r"C:\Users\Default\Desktop")
        self.assertEqual(
            environment.resolve_usmt_variable("CSIDL_COMMON_APPDATA"),
            r"C:\ProgramData")

    def test_resolve_csidl(self) -> None:
        from compatibility import environment
        self.assertEqual(
            environment.resolve_usmt_variable("CSIDL_SYSTEM"),
            r"C:\Windows\system32")
        # CSIDL_DESKTOP maps to FOLDERID_Desktop, which is the *physical*
        # Desktop folder -- the KNOWNFOLDERID CSIDL-equivalent column is
        # authoritative here, not the "virtual" feel of the legacy name.
        self.assertEqual(
            environment.resolve_usmt_variable("CSIDL_DESKTOP"),
            r"C:\Users\Default\Desktop")
        # CSIDL_BITBUCKET maps to the virtual Recycle Bin.
        self.assertTrue(
            environment.resolve_usmt_variable("CSIDL_BITBUCKET").startswith("::{"))

    def test_resolve_unknown_is_none(self) -> None:
        from compatibility import environment
        self.assertIsNone(
            environment.resolve_usmt_variable("TOTALLY_NOT_A_VARIABLE"))

    def test_build_usmt_context(self) -> None:
        from compatibility import environment
        table = environment.build_usmt_context("System")
        self.assertGreaterEqual(len(table), 50)
        self.assertIn("CSIDL_SYSTEM", table)
        self.assertIn("WINDIR", table)
        with self.assertRaises(KeyError):
            environment.build_usmt_context("NoSuchContext")

    def test_registry_paths_for_scope(self) -> None:
        from compatibility import environment
        self.assertTrue(environment.registry_path_for_scope(
            environment.EnvScope.SYSTEM).startswith("HKLM"))
        self.assertTrue(environment.registry_path_for_scope(
            environment.EnvScope.USER).startswith("HKCU"))
        self.assertIsNone(environment.registry_path_for_scope(
            environment.EnvScope.PROCESS))


class TestScopedEnvironment(unittest.TestCase):
    """Machine / User / Process scoping with Windows precedence."""

    def _env(self):
        from compatibility import environment
        return environment.ScopedEnvironment(host_fallback=False)

    def test_precedence_is_process_user_system(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("Path", r"C:\System", environment.EnvScope.SYSTEM)
        env.set("Path", r"C:\User", environment.EnvScope.USER)
        self.assertEqual(env.get("PATH"), r"C:\User")
        env.set("Path", r"C:\Process", environment.EnvScope.PROCESS)
        self.assertEqual(env.get("PATH"), r"C:\Process")
        self.assertIs(env.scope_of("PATH"), environment.EnvScope.PROCESS)

    def test_get_from_reads_one_scope(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("X", "sys", environment.EnvScope.SYSTEM)
        env.set("X", "usr", environment.EnvScope.USER)
        self.assertEqual(env.get_from("X", environment.EnvScope.SYSTEM), "sys")
        self.assertEqual(env.get_from("X", environment.EnvScope.USER), "usr")
        self.assertIsNone(env.get_from("X", environment.EnvScope.PROCESS))

    def test_unset_one_scope_falls_back_to_the_next(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("X", "sys", environment.EnvScope.SYSTEM)
        env.set("X", "usr", environment.EnvScope.USER)
        env.unset("X", environment.EnvScope.USER)
        self.assertEqual(env.get("X"), "sys")

    def test_unset_every_scope(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("X", "sys", environment.EnvScope.SYSTEM)
        env.set("X", "usr", environment.EnvScope.USER)
        self.assertTrue(env.unset("X"))
        self.assertIsNone(env.get("X"))
        self.assertFalse(env.unset("X"))

    def test_set_none_unsets(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("X", "1", environment.EnvScope.USER)
        env.set("X", None, environment.EnvScope.USER)
        self.assertIsNone(env.get("X"))

    def test_case_insensitive_but_case_preserving(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("MyVar", "1", environment.EnvScope.USER)
        self.assertEqual(env.get("myvar"), "1")
        self.assertEqual(env.get("MYVAR"), "1")
        self.assertEqual(env.names(environment.EnvScope.USER), ["MyVar"])

    def test_effective_block_flattens_scopes(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("Path", r"C:\System", environment.EnvScope.SYSTEM)
        env.set("Path", r"C:\Process", environment.EnvScope.PROCESS)
        blk = env.effective()
        self.assertEqual(blk.get("PATH"), r"C:\Process")
        self.assertIs(blk.scope_of("PATH"), environment.EnvScope.PROCESS)

    def test_to_registry_omits_the_process_scope(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("A", "1", environment.EnvScope.SYSTEM)
        env.set("B", "2", environment.EnvScope.USER)
        env.set("C", "3", environment.EnvScope.PROCESS)
        reg = env.to_registry()
        self.assertNotIn(environment.EnvScope.PROCESS, reg)
        self.assertEqual(reg[environment.EnvScope.SYSTEM], {"A": "1"})
        self.assertEqual(reg[environment.EnvScope.USER], {"B": "2"})

    def test_roundtrip_through_a_block(self) -> None:
        from compatibility import environment
        env = self._env()
        env.set("A", "1", environment.EnvScope.SYSTEM)
        env.set("B", "2", environment.EnvScope.USER)
        again = environment.ScopedEnvironment.from_block(env.effective(),
                                                         host_fallback=False)
        self.assertEqual(again.get("A"), "1")
        self.assertEqual(again.get("B"), "2")
        self.assertIs(again.scope_of("B"), environment.EnvScope.USER)


class TestEnvironmentInspection(unittest.TestCase):
    """``set`` / ``echo`` / ``Get-ChildItem Env:`` equivalents."""

    def _block(self):
        from compatibility import environment
        blk = environment.EnvironmentBlock()
        blk["FOO"] = "bar"
        blk["PATH"] = r"C:\Windows;C:\Tools"
        blk["PATHEXT"] = ".COM;.EXE"
        return blk

    def test_cmd_set_output(self) -> None:
        from compatibility import environment
        blk = self._block()
        out = environment.cmd_set_output(blk)
        self.assertIn("FOO=bar", out)
        self.assertIn("PATH=", out)
        self.assertEqual(environment.cmd_set_output(blk, "FOO"), "FOO=bar")

    def test_cmd_set_output_for_missing_name(self) -> None:
        from compatibility import environment
        out = environment.cmd_set_output(self._block(), "NOPE")
        self.assertIn("not defined", out)

    def test_cmd_expand_leaves_undefined_literal(self) -> None:
        from compatibility import environment
        blk = self._block()
        self.assertEqual(environment.cmd_expand("%FOO%", blk), "bar")
        self.assertEqual(environment.cmd_expand("%NOPE%", blk), "%NOPE%")

    def test_cmd_expand_is_single_pass(self) -> None:
        from compatibility import environment
        blk = self._block()
        blk["OUTER"] = "%INNER%"
        blk["INNER"] = "value"
        self.assertEqual(environment.cmd_expand("%OUTER%", blk), "%INNER%")

    def test_cmd_echo_appends_a_space(self) -> None:
        from compatibility import environment
        blk = self._block()
        self.assertEqual(environment.cmd_echo("%FOO%", blk), "bar ")
        self.assertEqual(environment.cmd_echo("plain", blk), "plain ")

    def test_powershell_get_env(self) -> None:
        from compatibility import environment
        blk = self._block()
        self.assertEqual(environment.powershell_get_env("FOO", blk), "bar")
        self.assertIsNone(environment.powershell_get_env("NOPE", blk))

    def test_powershell_env_listing(self) -> None:
        from compatibility import environment
        listing = environment.powershell_env_listing(self._block())
        self.assertIn("Name", listing)
        self.assertIn("Value", listing)
        self.assertIn("FOO", listing)
        self.assertIn("bar", listing)

    def test_search_path_prefers_the_current_directory(self) -> None:
        from compatibility import environment
        blk = self._block()
        cand = environment.search_path("tool.exe", blk, cwd=r"C:\Here",
                                       must_exist=False)
        self.assertEqual(cand, r"C:\Here\tool.exe")

    def test_search_path_falls_through_to_path(self) -> None:
        from compatibility import environment
        blk = self._block()
        cand = environment.search_path("tool.exe", blk, cwd=r"C:\Here",
                                       must_exist=False)
        self.assertTrue(cand.startswith(r"C:\Here"))
        # Nothing on PATH either -> the first candidate is returned.
        blk2 = environment.EnvironmentBlock()
        blk2["PATH"] = r"C:\Windows"
        blk2["PATHEXT"] = ".EXE"
        cand2 = environment.search_path("tool.exe", blk2, cwd=r"C:\Here",
                                        must_exist=False)
        self.assertEqual(cand2, r"C:\Here\tool.exe")

    def test_which_finds_a_real_file(self) -> None:
        import os
        import sys
        from compatibility import environment
        exe_dir = os.path.dirname(sys.executable)
        blk = environment.EnvironmentBlock()
        blk["PATH"] = exe_dir
        blk["PATHEXT"] = ".EXE"
        found = environment.which(os.path.basename(sys.executable), blk)
        self.assertIsNotNone(found)
        self.assertTrue(os.path.isfile(found))


class TestEnvironmentCommands(unittest.TestCase):
    """``set`` / ``setx`` semantics and variable-name validation."""

    def test_variable_name_validation(self) -> None:
        from compatibility import environment
        self.assertTrue(environment.is_valid_variable_name("PATH"))
        self.assertTrue(environment.is_valid_variable_name("ProgramFiles(x86)"))
        self.assertFalse(environment.is_valid_variable_name(""))
        self.assertFalse(environment.is_valid_variable_name("A=B"))
        self.assertFalse(environment.is_valid_variable_name("=LEADING"))

    def test_cmd_set_defines_in_the_process_scope(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        self.assertTrue(environment.cmd_set(env, "FOO", "bar"))
        self.assertEqual(env.get("FOO"), "bar")
        self.assertIs(env.scope_of("FOO"), environment.EnvScope.PROCESS)

    def test_cmd_set_with_an_empty_value_deletes(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        env.set("FOO", "bar", environment.EnvScope.PROCESS)
        self.assertTrue(environment.cmd_set(env, "FOO", ""))
        self.assertIsNone(env.get("FOO"))

    def test_cmd_set_without_a_value_does_not_change_anything(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        env.set("FOO", "bar", environment.EnvScope.PROCESS)
        self.assertFalse(environment.cmd_set(env, "FOO"))
        self.assertEqual(env.get("FOO"), "bar")

    def test_cmd_set_rejects_an_invalid_name(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        self.assertFalse(environment.cmd_set(env, "A=B", "x"))

    def test_setx_writes_to_a_persistent_scope(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        self.assertTrue(environment.setx(env, "PERSIST", "v",
                                         environment.EnvScope.USER))
        self.assertEqual(env.get_from("PERSIST", environment.EnvScope.USER),
                         "v")
        # It must not leak into the process scope.
        self.assertIsNone(env.get_from("PERSIST",
                                        environment.EnvScope.PROCESS))

    def test_setx_crops_values_over_1024_characters(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        # setx crops the value rather than rejecting it.
        self.assertTrue(environment.setx(env, "BIG", "x" * 1025,
                                         environment.EnvScope.USER))
        self.assertEqual(len(env.get_from("BIG", environment.EnvScope.USER)),
                         1024)
        # Exactly 1024 characters is fine.
        self.assertTrue(environment.setx(env, "EXACT", "x" * 1024,
                                         environment.EnvScope.USER))
        self.assertEqual(len(env.get_from("EXACT", environment.EnvScope.USER)),
                         1024)

    def test_setx_cannot_target_the_process_scope(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        self.assertFalse(environment.setx(env, "X", "v",
                                          environment.EnvScope.PROCESS))

    def test_setx_crops_at_1024_characters(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        # setx crops, it does not reject.
        self.assertTrue(environment.setx(env, "LONG", "x" * 2000,
                                         environment.EnvScope.USER))
        stored = env.get_from("LONG", environment.EnvScope.USER)
        self.assertEqual(len(stored), 1024)

    def test_setx_expands_variable_references(self) -> None:
        from compatibility import environment
        env = environment.ScopedEnvironment(host_fallback=False)
        env.set("JAVADIR", r"C:\Java", environment.EnvScope.USER)
        environment.setx(env, "MYPATH", r"%JAVADIR%\bin",
                         environment.EnvScope.USER)
        # setx flattens references before storing.
        self.assertEqual(env.get_from("MYPATH", environment.EnvScope.USER),
                         r"C:\Java\bin")


class TestEnvRegistry(unittest.TestCase):
    """Registry-backed persistence of the two persistent scopes."""

    def test_selftest_passes(self) -> None:
        from compatibility import env_registry
        self.assertTrue(env_registry._selftest())

    def test_scope_keys_match_windows(self) -> None:
        from compatibility import env_registry
        self.assertEqual(env_registry.USER_ENV_KEY, r"HKCU\Environment")
        self.assertEqual(
            env_registry.SYSTEM_ENV_KEY,
            r"HKLM\SYSTEM\CurrentControlSet\Control"
            r"\Session Manager\Environment")

    def test_write_and_read_back(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        store = EnvRegistryStore()
        self.assertTrue(store.set("user", "MYAPP", r"C:\Apps\MyApp"))
        entry = store.get("user", "MYAPP")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.value, r"C:\Apps\MyApp")
        self.assertFalse(entry.expand)
        self.assertEqual(entry.type_name, "REG_SZ")

    def test_path_is_stored_expandable(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        store = EnvRegistryStore()
        store.set("system", "Path", r"%SystemRoot%\system32;C:\Tools")
        entry = store.get("system", "Path")
        self.assertTrue(entry.expand)
        self.assertEqual(entry.type_name, "REG_EXPAND_SZ")
        # The reference is preserved verbatim in the registry.
        self.assertEqual(entry.raw, r"%SystemRoot%\system32;C:\Tools")

    def test_expandable_values_expand_on_read(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        from compatibility.environment import EnvironmentBlock
        store = EnvRegistryStore()
        store.set("system", "Path", r"%SystemRoot%\system32")
        blk = EnvironmentBlock()
        blk["SystemRoot"] = r"C:\Windows"
        expanded = store.read_expanded("system", blk)
        self.assertEqual(expanded["PATH"], r"C:\Windows\system32")

    def test_scopes_are_independent(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        store = EnvRegistryStore()
        store.set("user", "SHARED", "u")
        store.set("system", "SHARED", "s")
        self.assertEqual(store.get("user", "SHARED").value, "u")
        self.assertEqual(store.get("system", "SHARED").value, "s")

    def test_unset(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        store = EnvRegistryStore()
        store.set("user", "GONE", "x")
        self.assertTrue(store.unset("user", "GONE"))
        self.assertIsNone(store.get("user", "GONE"))
        self.assertFalse(store.unset("user", "GONE"))

    def test_write_replaces_scope_contents(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        store = EnvRegistryStore()
        store.set("user", "OLD", "1")
        store.write("user", {"NEW": "2"})
        names = set(store.read("user"))
        self.assertNotIn("OLD", names)
        self.assertIn("NEW", names)

    def test_unknown_scope_is_rejected(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        store = EnvRegistryStore()
        with self.assertRaises(KeyError):
            store.key_for("nonsense")

    def test_non_string_values_are_skipped(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        from compatibility.registry_hive import RegType
        from compatibility.registry_view import InMemoryRegistry
        reg = InMemoryRegistry()
        reg.set_value(r"HKCU\Environment", "DWORDVAL",
                      b"\x01\x00\x00\x00", RegType.DWORD)
        store = EnvRegistryStore(reg)
        self.assertIsNone(store.get("user", "DWORDVAL"))


class TestEnvironmentDialog(unittest.TestCase):
    """The two-section 'Environment Variables' dialog."""

    def test_selftest_passes(self) -> None:
        from compatibility import env_dialog
        self.assertTrue(env_dialog._selftest())

    def _dialog(self):
        from compatibility import env_dialog
        from compatibility.environment import EnvScope, ScopedEnvironment
        env = ScopedEnvironment(host_fallback=False)
        env.set("Machine", r"C:\Machine", EnvScope.SYSTEM)
        env.set("OnlyMe", r"C:\User", EnvScope.USER)
        return env, env_dialog.EnvironmentDialog(env)

    def test_two_sections_are_separate(self) -> None:
        _env, dlg = self._dialog()
        self.assertEqual(dlg.get(DlgScope.SYSTEM, "Machine"), r"C:\Machine")
        self.assertEqual(dlg.get(DlgScope.USER, "OnlyMe"), r"C:\User")
        self.assertIsNone(dlg.get(DlgScope.USER, "Machine"))
        self.assertIsNone(dlg.get(DlgScope.SYSTEM, "OnlyMe"))

    def test_add_edit_remove(self) -> None:
        _env, dlg = self._dialog()
        self.assertTrue(dlg.add(DlgScope.USER, "NEWVAR", "v"))
        self.assertEqual(dlg.get(DlgScope.USER, "NEWVAR"), "v")
        # Adding an existing name is refused.
        self.assertFalse(dlg.add(DlgScope.USER, "NEWVAR", "v2"))
        self.assertTrue(dlg.edit(DlgScope.USER, "NEWVAR", "v2"))
        self.assertEqual(dlg.get(DlgScope.USER, "NEWVAR"), "v2")
        self.assertTrue(dlg.remove(DlgScope.USER, "NEWVAR"))
        self.assertIsNone(dlg.get(DlgScope.USER, "NEWVAR"))

    def test_invalid_names_are_refused(self) -> None:
        _env, dlg = self._dialog()
        self.assertFalse(dlg.add(DlgScope.USER, "A=B", "v"))
        self.assertFalse(dlg.add(DlgScope.USER, "", "v"))

    def test_cancel_discards_pending_changes(self) -> None:
        _env, dlg = self._dialog()
        dlg.add(DlgScope.USER, "GONE", "x")
        self.assertEqual(dlg.pending_count(), 1)
        dlg.cancel()
        self.assertEqual(dlg.pending_count(), 0)
        self.assertIsNone(dlg.get(DlgScope.USER, "GONE"))

    def test_ok_commits_to_the_environment(self) -> None:
        env, dlg = self._dialog()
        dlg.add(DlgScope.USER, "KEPT", "yes")
        result = dlg.apply()
        self.assertTrue(result.changed)
        self.assertEqual(env.get("KEPT"), "yes")
        self.assertEqual(result.changes[0].kind, "added")

    def test_ok_persists_to_the_registry(self) -> None:
        from compatibility.env_registry import EnvRegistryStore
        env, _dlg = self._dialog()
        store = EnvRegistryStore()
        dlg = EnvironmentDialog(env, store)
        dlg.add(DlgScope.SYSTEM, "PERSISTED", "yes")
        dlg.apply()
        self.assertEqual(store.get("system", "PERSISTED").value, "yes")

    def test_path_is_edited_as_a_directory_list(self) -> None:
        _env, dlg = self._dialog()
        editor = dlg.path_editor(DlgScope.SYSTEM)
        self.assertEqual(editor.entries, [])
        dlg.add(DlgScope.SYSTEM, "Path", r"C:\A;C:\B")
        editor = dlg.path_editor(DlgScope.SYSTEM)
        self.assertEqual(editor.entries, [r"C:\A", r"C:\B"])
        self.assertTrue(editor.move_up(1))
        self.assertEqual(editor.entries, [r"C:\B", r"C:\A"])
        self.assertTrue(editor.move_down(0))
        self.assertEqual(editor.entries, [r"C:\A", r"C:\B"])
        self.assertTrue(editor.add(r"C:\C"))
        self.assertFalse(editor.add(r"C:\C"))       # duplicate
        dlg.set_path(DlgScope.SYSTEM, editor)
        self.assertEqual(dlg.get(DlgScope.SYSTEM, "Path"),
                         r"C:\A;C:\B;C:\C")

    def test_blank_path_entries_survive_a_round_trip(self) -> None:
        _env, dlg = self._dialog()
        dlg.add(DlgScope.SYSTEM, "Path", r"C:\A;;C:\B")
        editor = dlg.path_editor(DlgScope.SYSTEM)
        self.assertEqual(len(editor.entries), 3)
        self.assertEqual(editor.to_value(), r"C:\A;;C:\B")

    def test_over_long_values_are_truncated(self) -> None:
        from compatibility import env_dialog
        _env, dlg = self._dialog()
        dlg.add(DlgScope.USER, "LONG", "x" * 5000)
        result = dlg.apply()
        self.assertTrue(result.changes[0].truncated)
        self.assertEqual(len(result.changes[0].new_value),
                         env_dialog.MAX_DIALOG_VALUE_LENGTH)
        self.assertTrue(result.warnings)

    def test_a_very_long_path_warns(self) -> None:
        from compatibility import env_dialog
        _env, dlg = self._dialog()
        long_path = ";".join(r"C:\Dir%03d" % i for i in range(300))
        dlg.add(DlgScope.SYSTEM, "Path", long_path)
        result = dlg.apply()
        self.assertTrue(any("Path" in w for w in result.warnings))

    def test_a_normal_path_does_not_warn(self) -> None:
        _env, dlg = self._dialog()
        dlg.add(DlgScope.SYSTEM, "Path", r"C:\A;C:\B")
        result = dlg.apply()
        self.assertFalse(any("Path" in w for w in result.warnings))


class TestWow64Redirection(unittest.TestCase):
    """The WOW64 environment rewrite a 32-bit child process receives."""

    def _base(self):
        from compatibility.environment import EnvironmentBlock
        blk = EnvironmentBlock(host_fallback=False)
        blk["ProgramFiles"] = r"C:\Program Files"
        blk["ProgramFiles(x86)"] = r"C:\Program Files (x86)"
        blk["CommonProgramFiles"] = r"C:\Program Files\Common Files"
        blk["CommonProgramFiles(x86)"] = r"C:\Program Files (x86)\Common Files"
        return blk

    def test_64_bit_process(self) -> None:
        from compatibility.environment import apply_wow64_redirection
        blk = apply_wow64_redirection(self._base(), app_is_32bit=False)
        self.assertEqual(blk.get("PROCESSOR_ARCHITECTURE"), "AMD64")
        self.assertEqual(blk.get("ProgramFiles"), r"C:\Program Files")
        self.assertEqual(blk.get("ProgramW6432"), r"C:\Program Files")
        self.assertEqual(blk.get("CommonProgramFiles"),
                         r"C:\Program Files\Common Files")
        self.assertEqual(blk.get("CommonProgramW6432"),
                         r"C:\Program Files\Common Files")
        self.assertIsNone(blk.get("PROCESSOR_ARCHITEW6432"))

    def test_32_bit_process(self) -> None:
        from compatibility.environment import apply_wow64_redirection
        blk = apply_wow64_redirection(self._base(), app_is_32bit=True)
        self.assertEqual(blk.get("PROCESSOR_ARCHITECTURE"), "x86")
        self.assertEqual(blk.get("PROCESSOR_ARCHITEW6432"), "AMD64")
        self.assertEqual(blk.get("ProgramFiles"), r"C:\Program Files (x86)")
        self.assertEqual(blk.get("ProgramW6432"), r"C:\Program Files")
        self.assertEqual(blk.get("CommonProgramFiles"),
                         r"C:\Program Files (x86)\Common Files")
        self.assertEqual(blk.get("CommonProgramW6432"),
                         r"C:\Program Files\Common Files")

    def test_32_bit_os_is_not_redirected(self) -> None:
        from compatibility.environment import apply_wow64_redirection
        blk = apply_wow64_redirection(self._base(), app_is_32bit=True,
                                      os_is_64bit=False)
        self.assertIsNone(blk.get("PROCESSOR_ARCHITEW6432"))
        self.assertEqual(blk.get("PROCESSOR_ARCHITECTURE"), "x86")

    def test_arm64_native_architecture(self) -> None:
        from compatibility.environment import apply_wow64_redirection
        blk = apply_wow64_redirection(self._base(), app_is_32bit=True,
                                      native_arch="ARM64")
        self.assertEqual(blk.get("PROCESSOR_ARCHITEW6432"), "ARM64")
        self.assertEqual(blk.get("PROCESSOR_ARCHITECTURE"), "x86")


class TestShellSession(unittest.TestCase):
    """A shell whose environment is backed by the registry."""

    def _session(self):
        from compatibility.environment import ShellSession
        from compatibility.env_registry import EnvRegistryStore
        return ShellSession(EnvRegistryStore())

    def test_registry_change_is_invisible_until_refresh(self) -> None:
        session = self._session()
        session.store.set("user", "NEWVAR", "hello")
        # The running shell still has the old value ...
        self.assertIsNone(session.live.get("NEWVAR"))
        # ... and knows it is out of date.
        self.assertIn("NEWVAR", session.stale_names())
        # A refresh picks it up.
        self.assertTrue(session.refresh())
        self.assertEqual(session.live.get("NEWVAR"), "hello")
        self.assertEqual(session.stale_names(), [])

    def test_a_new_shell_sees_the_registry(self) -> None:
        session = self._session()
        session.store.set("user", "NEWVAR", "hello")
        # A shell launched by Explorer is built from the registry ...
        fresh = session.new_shell_block()
        self.assertEqual(fresh.get("NEWVAR"), "hello")
        # ... while the live shell has not seen it yet.
        self.assertIsNone(session.live.get("NEWVAR"))

    def test_a_child_inherits_the_parent_block(self) -> None:
        session = self._session()
        session.store.set("user", "NEWVAR", "hello")
        # A child of this shell inherits its (stale) block, so the
        # installer keeps using the old value.
        child = session.child_block()
        self.assertIsNone(child.get("NEWVAR"))

    def test_set_persistent_does_not_touch_the_live_environment(self) -> None:
        from compatibility import environment
        session = self._session()
        session.set_persistent(environment.EnvScope.USER, "PERSIST", "v")
        self.assertIsNone(session.live.get("PERSIST"))
        self.assertEqual(session.store.get("user", "PERSIST").value, "v")

    def test_setting_a_variable_broadcasts_the_change(self) -> None:
        from compatibility import environment
        from compatibility import win_user32
        session = self._session()
        before = len(win_user32.setting_change_log())
        session.set_persistent(environment.EnvScope.SYSTEM, "BROADCAST", "v")
        log = win_user32.setting_change_log()
        self.assertEqual(len(log), before + 1)
        self.assertEqual(log[-1][1], "Environment")

    def test_unset_persistent(self) -> None:
        from compatibility import environment
        session = self._session()
        session.store.set("user", "TEMP", "v")
        self.assertTrue(session.unset_persistent(environment.EnvScope.USER,
                                                 "TEMP"))
        self.assertIsNone(session.store.get("user", "TEMP"))


class TestInstallerEnv(unittest.TestCase):
    """Where software is installed, per context and architecture."""

    def test_selftest_passes(self) -> None:
        from compatibility import installer_env
        self.assertTrue(installer_env._selftest())

    def _block(self):
        from compatibility.environment import EnvironmentBlock
        blk = EnvironmentBlock(host_fallback=False)
        blk["ProgramFiles"] = r"C:\Program Files"
        blk["ProgramFiles(x86)"] = r"C:\Program Files (x86)"
        blk["CommonProgramFiles"] = r"C:\Program Files\Common Files"
        blk["CommonProgramFiles(x86)"] = r"C:\Program Files (x86)\Common Files"
        blk["LocalAppData"] = r"C:\Users\me\AppData\Local"
        blk["AppData"] = r"C:\Users\me\AppData\Roaming"
        blk["ProgramData"] = r"C:\ProgramData"
        return blk

    def test_per_machine_64bit_package(self) -> None:
        from compatibility.installer_env import (InstallationContext,
                                                 resolve_install_target)
        target = resolve_install_target("MyApp", InstallationContext.PER_MACHINE,
                                        app_is_32bit=False, os_is_64bit=True,
                                        block=self._block())
        self.assertEqual(target.app_dir, r"C:\Program Files\MyApp")
        self.assertFalse(target.wow64)
        self.assertTrue(target.uninstall_key.startswith("HKLM"))

    def test_per_machine_32bit_package_on_64bit_windows(self) -> None:
        from compatibility.installer_env import (InstallationContext,
                                                 resolve_install_target)
        target = resolve_install_target("MyApp", InstallationContext.PER_MACHINE,
                                        app_is_32bit=True, os_is_64bit=True,
                                        block=self._block())
        self.assertEqual(target.app_dir, r"C:\Program Files (x86)\MyApp")
        self.assertTrue(target.wow64)

    def test_per_user_install(self) -> None:
        from compatibility.installer_env import (InstallationContext,
                                                 resolve_install_target)
        target = resolve_install_target("MyApp", InstallationContext.PER_USER,
                                        block=self._block())
        self.assertEqual(target.app_dir,
                         r"C:\Users\me\AppData\Local\Programs\MyApp")
        self.assertEqual(target.common_files,
                         r"C:\Users\me\AppData\Local\Programs\Common")
        self.assertTrue(target.uninstall_key.startswith("HKCU"))
        self.assertTrue(target.start_menu.startswith(
            r"C:\Users\me\AppData\Roaming\Microsoft\Windows\Start Menu"))

    def test_per_machine_start_menu_is_shared(self) -> None:
        from compatibility.installer_env import (InstallationContext,
                                                 resolve_install_target)
        target = resolve_install_target("MyApp", InstallationContext.PER_MACHINE,
                                        block=self._block())
        self.assertTrue(target.start_menu.startswith(
            r"C:\ProgramData\Microsoft\Windows\Start Menu"))

    def test_msi_context_properties(self) -> None:
        from compatibility.installer_env import (InstallationContext,
                                                 msi_properties)
        self.assertEqual(
            msi_properties(InstallationContext.PER_MACHINE)["ALLUSERS"], "1")
        self.assertEqual(
            msi_properties(InstallationContext.PER_USER)["ALLUSERS"], "")

    def test_installer_environment_carries_the_wow64_rewrite(self) -> None:
        from compatibility.installer_env import (InstallationContext,
                                                 installer_environment)
        env = installer_environment(self._block(), app_is_32bit=True,
                                    context=InstallationContext.PER_MACHINE)
        self.assertEqual(env.get("ProgramFiles"), r"C:\Program Files (x86)")
        self.assertEqual(env.get("ProgramW6432"), r"C:\Program Files")
        self.assertEqual(env.get("ALLUSERS"), "1")

    def test_path_entries_an_installer_adds(self) -> None:
        from compatibility.installer_env import (InstallationContext,
                                                 installer_path_entries,
                                                 resolve_install_target)
        target = resolve_install_target("MyApp", InstallationContext.PER_MACHINE,
                                        block=self._block())
        self.assertEqual(installer_path_entries(target),
                         [r"C:\Program Files\MyApp\bin"])

    def test_per_user_requires_no_elevation(self) -> None:
        from compatibility.installer_env import InstallationContext
        self.assertTrue(InstallationContext.PER_MACHINE.requires_elevation)
        self.assertFalse(InstallationContext.PER_USER.requires_elevation)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
