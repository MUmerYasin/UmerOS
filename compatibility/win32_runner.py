"""
Umer OS /compatibility/win32_runner — Win32 PE runner over x86_runner
====================================================================

Loads a PE32 / PE32+ image into the minimal pure-Python
:class:`compatibility.x86_runner.Emulator`, resolves the IAT
against the :mod:`compatibility.dll_loader` host library, and runs
the entry point.

The implementation is deliberately tiny -- it implements only
what's needed to execute *hand-assembled* test PEs and small
utility programs:

1. Parse PE headers using :mod:`compatibility.pe_loader`.
2. Map each ``IMAGE_SECTION_HEADER`` into the emulator's virtual
   memory.
3. Walk the Import Directory (data directory index 1) and patch
   the IAT with **emulator-internal thunks** that we install via
   :meth:`compatibility.x86_runner.Emulator.install_thunk`.
4. Build a small stack: ``[argc] [argv...] [envp...] [argv0_dummy]``.
5. Push the entry-point RVA onto the stack as the return address and
   ``call`` into the entry point.

The Windows calling convention for x64 is followed::

    rcx = arg1, rdx = arg2, r8 = arg3, r9 = arg4,
    [rsp+0x20] = arg5, [rsp+0x28] = arg6, ...
    return value in rax.

The shim preserves caller-saved registers; callee-saved registers
(RBX, RBP, RDI, RSI, R12..R15) are preserved by the underlying
Win32 stubs.

This module also includes a small *test PE generator* that emits
a hand-assembled 64-bit PE that:

* Calls :func:`compatibility.win_kernel32.GetTickCount`.
* Stores the returned value at a known memory location.
* Calls the same ``GetTickCount`` a second time (the same way
  real installers double-check).
* Halts cleanly with ``hlt``.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
* https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .pe_loader import PeFile, PeClass
from .pe_imports import parse_imports
from .x86_runner import Emulator, EmulatorHalt, EmulatorBreakpoint, EmulatorError

log = logging.getLogger("UmerOS.Compat.Win32Runner")

# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """The outcome of running a PE in the emulator."""
    exit_code: int = 0
    steps: int = 0
    rip_final: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class Win32Runner:
    """A thin wrapper that knows how to load + run a Win32 PE."""

    def __init__(self, *,
                 imports: Optional[Dict[str, Dict[str, Callable]]] = None,
                 stack_top: int = 0x7FFF_0000,
                 stack_size: int = 0x40000,
                 image_base: int = 0x400000) -> None:
        self.emulator = Emulator(base=image_base,
                                  stack_top=stack_top,
                                  stack_size=stack_size)
        # Where the IAT thunks go.
        self._thunk_table: Dict[Tuple[str, str], int] = {}
        # Public hook for tests: ``imports`` overrides the default
        # compatibility-layer lookup when set.
        self._imports = imports
        # Whether the loaded PE is 64-bit (PE32+) -- affects IAT stride.
        self._pe_is_64: bool = True

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------

    def load_pe(self, pe: PeFile, raw_image: bytes = b"") -> None:
        if pe.optional_header.pe_class == PeClass.PE32_PLUS:
            image_base = pe.optional_header.image_base
            self._pe_is_64 = True
        else:
            image_base = pe.optional_header.image_base
            self._pe_is_64 = False
        # Place the image at the requested base.  The emulator's
        # ``base`` defaults to 0x400000, matching the linker default.
        self.emulator.base = image_base
        # Map each section from the raw image bytes.
        for section in pe.sections:
            self._map_section(section, raw_image)
        # Resolve imports.
        self._resolve_imports(pe)
        # Build a tiny "PEB-like" structure and place it at a known
        # address so the entry point can read process state.
        self._install_peb()

    def _map_section(self, section, raw_image: bytes) -> None:
        if not raw_image:
            return
        raw_off = section.raw_offset
        size = section.raw_size
        if raw_off >= len(raw_image):
            return
        data = raw_image[raw_off:raw_off + size]
        if not data:
            return
        # Sections are mapped at their absolute virtual address, i.e.
        # image_base + RVA.  We don't bother applying relocations --
        # the runner assumes a PE built for the chosen image_base.
        self.emulator.mem.write(
            self.emulator.base + section.virtual_address, data)

    def _resolve_imports(self, pe: PeFile) -> None:
        # Walk import descriptors via the existing parser.
        if self._imports is None:
            from . import dll_loader
            imports_table = dll_loader.HOST_LIBRARIES
        else:
            imports_table = self._imports
        try:
            import_descriptors = parse_imports(pe)
        except Exception as exc:
            log.debug("parse_imports failed: %s", exc)
            return
        for desc in import_descriptors:
            lib = imports_table.get(desc.name.upper())
            if lib is None:
                lib = imports_table.get(desc.name.lower())
            for sym_index, symbol in enumerate(desc.symbols):
                if symbol.is_ordinal_only:
                    name = f"ordinal_{symbol.ordinal}"
                else:
                    name = symbol.name
                target = None
                if lib is not None:
                    target = lib.get(name)
                if target is None:
                    log.debug("unresolved import %s!%s -> 0",
                                desc.name, name)
                    target = self._install_missing_stub(f"{desc.name}!{name}")
                thunk_addr = self.emulator.install_thunk(
                    f"{desc.name}!{name}", target)
                # The IAT slot for symbol index N lives at
                # ``first_thunk + N * stride`` where the stride is 4
                # for PE32 (32-bit thunk entries) and 8 for PE32+
                # (64-bit thunk entries).  The IAT lives inside the
                # loaded image, so the address is RVA + image_base.
                stride = 8 if self._pe_is_64 else 4
                iat_rva = desc.first_thunk + sym_index * stride
                iat_addr = self.emulator.base + iat_rva
                self.emulator.mem.write_u64(iat_addr, thunk_addr)

    def _install_missing_stub(self, name: str) -> Callable:
        """Return a stub that the thunk dispatcher calls when an
        import is unresolved."""
        def _stub(emu: "Emulator") -> None:
            emu.regs.set(0, 0)        # rax = 0
            log.debug("missing stub %s -> 0", name)
        return _stub

    def _install_peb(self) -> int:
        """Allocate a 64-byte fake PEB at a known address."""
        peb = self.emulator.base - 0x1000
        # All zero except the *BeingDebugged* flag at offset 2.
        self.emulator.mem.write(peb, b"\x00" * 64)
        self.emulator.mem.write_u8(peb + 2, 1)
        return peb

    # ------------------------------------------------------------------
    # Argument marshalling + entry-point invocation
    # ------------------------------------------------------------------

    def _setup_stack(self, *, argv: Optional[List[str]] = None,
                     envp: Optional[List[str]] = None) -> int:
        """Push argc / argv / envp / auxv onto the stack x64-style."""
        argv = list(argv or [])
        envp = list(envp or [])
        rsp = self.emulator.regs.get(4)
        # Push the strings first (right-to-left, with NUL terminator).
        arg_offsets: List[int] = []
        for s in argv:
            enc = s.encode("utf-8") + b"\x00"
            rsp -= len(enc)
            self.emulator.mem.write(rsp, enc)
            arg_offsets.append(rsp)
        env_offsets: List[int] = []
        for s in envp:
            enc = s.encode("utf-8") + b"\x00"
            rsp -= len(enc)
            self.emulator.mem.write(rsp, enc)
            env_offsets.append(rsp)
        # Align.
        rsp &= ~0xF
        # Push the auxv (just NULL).
        rsp -= 8
        self.emulator.mem.write_u64(rsp, 0)
        # Push envp array.
        rsp -= 8 * (len(env_offsets) + 1)
        for o in env_offsets:
            self.emulator.mem.write_u64(rsp, o)
            rsp += 8
        self.emulator.mem.write_u64(rsp, 0)        # envp terminator
        # Push argv array.
        rsp -= 8 * (len(arg_offsets) + 1)
        for o in arg_offsets:
            self.emulator.mem.write_u64(rsp, o)
            rsp += 8
        self.emulator.mem.write_u64(rsp, 0)        # argv terminator
        # Push argc.
        rsp -= 8
        self.emulator.mem.write_u64(rsp, len(arg_offsets))
        self.emulator.regs.set(4, rsp)
        return rsp

    def run_entry(self, *, argv: Optional[List[str]] = None,
                  envp: Optional[List[str]] = None,
                  max_steps: int = 100_000) -> RunResult:
        rsp = self._setup_stack(argv=argv, envp=envp)
        # ``ret`` will pop the entry-point address from the stack and
        # jump to it -- we don't have an explicit *jmp*, so the test
        # program should arrange for the entry-point RVA to be on
        # the stack itself.
        try:
            rc = self.emulator.run(max_steps=max_steps)
        except EmulatorHalt:
            rc = self.emulator.exit_code
        except EmulatorDecodeError if 'EmulatorDecodeError' in dir() else EmulatorError as exc:
            return RunResult(exit_code=-1, steps=self.emulator.steps,
                              rip_final=self.emulator.regs.get(15),
                              error=str(exc))
        return RunResult(exit_code=rc, steps=self.emulator.steps,
                          rip_final=self.emulator.regs.get(15))


# Convenience import for older Python versions
EmulatorDecodeError = EmulatorError


# ---------------------------------------------------------------------------
# Test PE generator (hand-assembled 64-bit PE that calls GetTickCount)
# ---------------------------------------------------------------------------

def build_test_pe_gettickcount() -> bytes:
    """Build a minimal PE32+ whose entry point calls
    ``GetTickCount`` twice and halts.

    Layout::

        EP   : 0x001000 (code starts here)
        IAT  : 0x002000 (we patch in a thunk here during loading)
        DATA : 0x003000 (output buffer)

    The code uses RIP-relative addressing so the disp32s below are
    computed against the absolute addresses.
    """
    ep = 0x1000
    iat = 0x2000
    data = 0x3000

    def disp(target: int, rip_next: int) -> int:
        return target - rip_next

    code = bytearray()
    # Function prologue: stack alignment.
    code += b"\x48\x83\xEC\x28"                # sub rsp, 0x28
    # First call.
    #   call sits at offset 4, length 6 -> RIP_next = ep + 10
    rip_after_call1 = ep + 4 + 6
    code += b"\xFF\x15" + struct.pack("<i", disp(iat, rip_after_call1))
    # First mov (7 bytes), RIP_next = rip_after_call1 + 7 = ep + 17.
    rip_after_mov1 = rip_after_call1 + 7
    code += b"\x48\x89\x05" + struct.pack(
        "<i", disp(data, rip_after_mov1))
    # Second call sits at offset 17, length 6 -> RIP_next = rip_after_mov1 + 6.
    rip_after_call2 = rip_after_mov1 + 6
    code += b"\xFF\x15" + struct.pack("<i", disp(iat, rip_after_call2))
    # Second mov (7 bytes), RIP_next = rip_after_call2 + 7.
    rip_after_mov2 = rip_after_call2 + 7
    code += b"\x48\x89\x05" + struct.pack(
        "<i", disp(data + 8, rip_after_mov2))
    # Halt.
    code += b"\xF4"
    return bytes(code)


def build_gettickcount_pe() -> bytes:
    """Build a minimal PE32+ binary that calls
    ``kernel32!GetTickCount`` and halts.

    Layout::

        .text  : 0x401000 (code)
        .rdata : 0x402000 (IAT entry pointing at thunk)
        .data  : 0x403000 (output buffer)

    The thunk is installed by the runner, not the binary; the
    binary's IAT holds a single placeholder address that the runner
    patches during loading.
    """
    MZ = 0x4C

    def pad_to(buf, offset, alignment=0x200):
        while len(buf) % alignment:
            buf.append(0)
        return buf

    out = bytearray()
    # MZ header.
    out += b"MZ" + b"\x00" * 58
    pe_off = len(out)
    out += struct.pack("<I", pe_off + 4)
    out += b"PE\x00\x00"
    # COFF header (20 bytes).
    out += struct.pack("<HHIIIHH",
                       0x8664, 3, 0, 0, 0,        # machine=AMD64, n_sections=3
                       240,            # size of optional header (PE32+ = 240)
                       0x0002)         # file characteristics: EXECUTABLE_IMAGE
    # Optional header (PE32+).
    opt = bytearray()
    opt += struct.pack("<H", 0x020B)              # magic
    opt += struct.pack("<BB", 14, 0)             # linker version
    opt += struct.pack("<I", 0)                  # SizeOfCode
    opt += struct.pack("<I", 0)                  # SizeOfInitializedData
    opt += struct.pack("<I", 0)                  # SizeOfUninitializedData
    opt += struct.pack("<I", 0x1000)              # AddressOfEntryPoint
    opt += struct.pack("<I", 0x1000)              # BaseOfCode
    opt += struct.pack("<Q", 0x000000)            # ImageBase (0 for test PEs)
    opt += struct.pack("<I", 0x1000)             # SectionAlignment
    opt += struct.pack("<I", 0x200)              # FileAlignment
    opt += struct.pack("<HHHHHH", 6, 0, 0, 0, 6, 0)  # OS/Image/Subsystem versions
    opt += struct.pack("<I", 0)                  # Win32VersionValue
    opt += struct.pack("<I", 0x50000)             # SizeOfImage
    opt += struct.pack("<I", 0x1000)             # SizeOfHeaders
    opt += struct.pack("<I", 0)                  # CheckSum
    opt += struct.pack("<H", 3)                  # Subsystem (CONSOLE)
    opt += struct.pack("<H", 0)                  # DllCharacteristics
    opt += struct.pack("<Q", 0x100000)            # SizeOfStackReserve
    opt += struct.pack("<Q", 0x1000)              # SizeOfStackCommit
    opt += struct.pack("<Q", 0x100000)            # SizeOfHeapReserve
    opt += struct.pack("<Q", 0x1000)              # SizeOfHeapCommit
    opt += struct.pack("<I", 0)                  # LoaderFlags
    opt += struct.pack("<I", 16)                 # NumberOfRvaAndSizes
    # 16 data directories.
    for i in range(16):
        if i == 1:    # import directory
            opt += struct.pack("<II", 0x2040, 40)        # one DLL, one terminator
        elif i == 12:    # IAT
            opt += struct.pack("<II", 0x2000, 8)
        else:
            opt += struct.pack("<II", 0, 0)
    assert len(opt) == 240, f"optional header is {len(opt)} bytes"
    out += opt
    # Section headers: .text / .rdata / .data.
    def sec_header(name, va, vsize, raw, rsize, chars):
        """Build a 40-byte IMAGE_SECTION_HEADER.

        Layout per PE spec:
          8s  Name[8]
          I   VirtualSize (4 bytes)
          I   VirtualAddress (4 bytes)
          I   SizeOfRawData (4 bytes)
          I   PointerToRawData (4 bytes)
          I   PointerToRelocations (4 bytes)
          I   PointerToLinenumbers (4 bytes)
          H   NumberOfRelocations (2 bytes)
          H   NumberOfLinenumbers (2 bytes)
          I   Characteristics (4 bytes)
        """
        b = bytearray()
        b += name.encode("ascii").ljust(8, b"\x00")
        b += struct.pack("<I", vsize)
        b += struct.pack("<I", va)
        b += struct.pack("<I", rsize)
        b += struct.pack("<I", raw)
        b += struct.pack("<IIHHI",
                         0, 0, 0, 0, chars)
        assert len(b) == 40, f"section header is {len(b)} bytes, want 40"
        return b
    # Compute body offsets up front -- section bodies sit at
    # file-aligned (0x200) offsets starting at FileAlignment.
    # The COFF header (20) + optional header (240) = 260 bytes; then
    # 3 section headers (40 bytes each) = 120 bytes; total = 380 bytes
    # which pads up to 0x200 = 512.
    text_body_off = 0x200
    rdata_body_off = text_body_off + 0x100
    data_body_off = rdata_body_off + 0x100
    # Section headers must immediately follow the optional header so
    # the PeFile parser can locate them via ``opt_off + size_opt``.
    sec_table_off = len(out)            # should be 0x148
    out += sec_header(".text",  0x1000, 0x1000, text_body_off,
                       0x100, 0x60000020)
    out += sec_header(".rdata", 0x2000, 0x1000, rdata_body_off,
                       0x100, 0x40000040)
    out += sec_header(".data",  0x3000, 0x1000, data_body_off,
                       0x100, 0xC0000040)
    # Pad to FileAlignment (0x200) so the section bodies sit at
    # file-aligned offsets.
    pad_to(out, len(out), 0x200)
    assert len(out) == text_body_off, (
        f"expected body to start at 0x{text_body_off:x}, got 0x{len(out):x}")
    # .text body.
    code = build_test_pe_gettickcount()
    assert len(code) <= 0x100
    out += code + b"\x00" * (0x100 - len(code))
    # .rdata body (raw size = 0x100, virtual = 0x1000).
    # Layout (RVAs):
    #   0x2000  IAT entry (8 bytes; patched at load time)
    #   0x2008  -- padding --
    #   0x2020  INT entry: hint/name RVA (4 bytes) + terminator (4)
    #   0x2028  -- padding --
    #   0x2040  Import descriptor (20 bytes) for kernel32.dll
    #   0x2054  Import descriptor terminator (20 bytes of zeros)
    #   0x2070  Hint/Name: 2-byte hint + "GetTickCount\0"
    #   0x2080  "kernel32.dll\0"
    rdata = bytearray(0x100)
    # IAT at 0x2000 (file offset 0).
    struct.pack_into("<Q", rdata, 0, 0xFFFF_FFFF)        # placeholder
    # INT at 0x2020 (file offset 0x20): hint/name RVA = 0x2070.
    struct.pack_into("<I", rdata, 0x20, 0x2070)
    struct.pack_into("<I", rdata, 0x24, 0)                # INT terminator
    # Import descriptor at 0x2040 (file offset 0x40):
    #   OriginalFirstThunk = 0x2020
    #   TimeDateStamp      = 0
    #   ForwarderChain     = 0xFFFFFFFF
    #   Name RVA           = 0x2080
    #   FirstThunk (IAT)   = 0x2000
    struct.pack_into("<IIIII", rdata, 0x40,
                     0x2020, 0, 0xFFFFFFFF, 0x2080, 0x2000)
    # Terminator at 0x2054 (file offset 0x54): 20 bytes of zeros (already)
    # Hint/Name at 0x2070 (file offset 0x70):
    #   Hint (2 bytes): 0
    #   Name: "GetTickCount\0"
    name = b"GetTickCount\x00"
    struct.pack_into("<H", rdata, 0x70, 0)
    rdata[0x72:0x72 + len(name)] = name
    # DLL name at 0x2080 (file offset 0x80):
    dllname = b"kernel32.dll\x00"
    rdata[0x80:0x80 + len(dllname)] = dllname
    out += rdata
    # .data body.
    data = bytearray()
    data += b"\x00" * 0x100
    out += data
    # Pad file to SizeOfImage.
    pad_to(out, len(out), 0x1000)
    return bytes(out)


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    from .pe_loader import PeFile
    blob = build_gettickcount_pe()
    pe = PeFile.from_bytes(blob)
    if pe is None:
        return False
    # Build a tiny import table that resolves kernel32!GetTickCount
    # to a stub that returns 12345 in rax.
    def _fake_tick(emu: "Emulator") -> None:
        emu.regs.set(0, 12345)        # rax
    imports = {
        "KERNEL32.DLL": {
            "GetTickCount": _fake_tick,
        },
    }
    runner = Win32Runner(image_base=int(pe.optional_header.image_base),
                         imports=imports)
    # Load the PE -- section mapping + import resolution.
    runner.load_pe(pe, raw_image=blob)
    # Set RIP to the entry point and run.
    runner.emulator.regs.set(15, 0x1000)
    try:
        rc = runner.emulator.run(max_steps=50)
    except EmulatorHalt:
        rc = 0
    if rc != 0:
        return False
    # Read the two tick results.
    r1 = runner.emulator.mem.read_u64(0x3000)
    r2 = runner.emulator.mem.read_u64(0x3008)
    if r1 != 12345 or r2 != 12345:
        return False
    return True


# Convenience import for older Python versions


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
