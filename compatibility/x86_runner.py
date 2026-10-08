"""
Umer OS /compatibility/x86_runner — minimal pure-Python x86-64 emulator
=======================================================================

Pure-Python user-mode x86-64 instruction interpreter and emulator.
It is intentionally **tiny**: it implements just enough of the
instruction set to run hand-assembled Win32 helper PEs and to drive
a Win32 syscall dispatch table.  The goal is *not* to replace QEMU
or Unicorn -- those are 1000x faster.  The goal is to demonstrate
that the compatibility layer's stubs can be reached from real
machine code, on a pure-Python stack, without C extensions.

Implemented instruction set
----------------------------

* ``B8+rd id`` / ``B8+rd id`` — ``mov reg, imm64`` (with Rex.W)
* ``89 /r`` — ``mov r/m, r``
* ``8B /r`` — ``mov r, r/m``
* ``C7 /0 id`` — ``mov r/m32, imm32``
* ``48 89 /r`` — ``mov r/m64, r64``
* ``48 8B /r`` — ``mov r64, r/m64``
* ``48 83 /0 ib`` — ``add/sub r/m64, imm8``
* ``48 03 /r`` — ``add r64, r/m64``
* ``48 29 /r`` — ``sub r/m64, r64``
* ``48 31 /r`` — ``xor r/m64, r64``
* ``48 33 /r`` — ``xor r64, r/m64``
* ``48 3B /r`` — ``cmp r64, r/m64``
* ``48 8D /r`` — ``lea r64, [m]``
* ``50+rd`` — ``push reg``
* ``58+rd`` — ``pop reg``
* ``FF /2`` — ``call r/m64``
* ``FF /5`` — ``jmp [rip+disp32]``
* ``FF 15 id`` — ``call [rip+disp32]`` (CALL via memory -- Win32 IAT calls)
* ``E9 cd`` — ``jmp rel32``
* ``EB cb`` — ``jmp rel8``
* ``0F 84/85/8D/8E cd`` — ``je/jne/jge/jle rel32``
* ``C3`` — ``ret``
* ``C9`` — ``leave``
* ``90`` — ``nop``
* ``CC`` — ``int 3`` (raise ``EmulatorBreakpoint``)
* ``F4`` — ``hlt``
* ``0F B6 /r`` — ``movzx r8/16/32, r/m8``
* ``0F B7 /r`` — ``movzx r16/32/64, r/m16``
* ``24/0C/2D ib`` — ``and/al/sub al, imm8``
* ``34/0C/2D ib`` — ``xor al, imm8``

Win32 syscall dispatch
----------------------

The emulator exposes :class:`Emulator.api_call` -- call this from a
custom *thunk* whose address the emulator will jump to.  Real Win32
PEs do ``call [IAT_ENTRY]`` where ``IAT_ENTRY`` holds the address
of the host-side stub.  We wire that address up to a Python callable
so the emulator sees ``call [IAT_ENTRY]`` as "enter the syscall
dispatch", looks up the entry in :attr:`Emulator.imports`, and
invokes the corresponding Python function with the parsed
arguments.

References
----------

* Intel SDM Volume 2 -- instruction set reference
* https://wiki.osdev.org/X86-64_Instruction_Encoding

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.X86Runner")

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class EmulatorError(Exception):
    """Base class for every emulator error."""


class EmulatorHalt(EmulatorError):
    """Raised when the program reaches ``hlt`` (we treat it as a clean
    termination signal in the same way QEMU does)."""


class EmulatorBreakpoint(EmulatorError):
    """Raised when the program hits ``int 3``."""


class EmulatorDecodeError(EmulatorError):
    """The instruction decoder could not make sense of a byte."""


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------

REG_NAMES = [
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
    "r8",  "r9",  "r10", "r11", "r12", "r13", "r14", "r15",
]

REG_RAX = 0
REG_RCX = 1
REG_RDX = 2
REG_RBX = 3
REG_RSP = 4
REG_RBP = 5
REG_RSI = 6
REG_RDI = 7
REG_RIP = 15

BYTE_REGS = {
    REG_RAX: "al", REG_RCX: "cl", REG_RDX: "dl", REG_RBX: "bl",
    REG_RSP: "spl", REG_RBP: "bpl", REG_RSI: "sil", REG_RDI: "dil",
}

WORD_REGS = {
    REG_RAX: "ax", REG_RCX: "cx", REG_RDX: "dx", REG_RBX: "bx",
    REG_RSP: "sp", REG_RBP: "bp", REG_RSI: "si", REG_RDI: "di",
}

DWORD_REGS = {
    REG_RAX: "eax", REG_RCX: "ecx", REG_RDX: "edx", REG_RBX: "ebx",
    REG_RSP: "esp", REG_RBP: "ebp", REG_RSI: "esi", REG_RDI: "edi",
}


@dataclass
class Registers:
    """The 16 x86-64 general-purpose registers + a few flags."""
    r: List[int] = field(default_factory=lambda: [0] * 16)

    # EFlags
    cf: int = 0
    pf: int = 0
    zf: int = 0
    sf: int = 0
    of: int = 0

    def get(self, idx: int) -> int:
        return self.r[idx] & 0xFFFFFFFFFFFFFFFF

    def set(self, idx: int, value: int) -> None:
        self.r[idx] = value & 0xFFFFFFFFFFFFFFFF

    def snapshot(self) -> Dict[str, int]:
        out = {REG_NAMES[i]: self.r[i] for i in range(16)}
        out.update({"cf": self.cf, "pf": self.pf, "zf": self.zf,
                    "sf": self.sf, "of": self.of})
        return out


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class Memory:
    """A flat byte-addressed virtual memory."""

    def __init__(self) -> None:
        self._pages: Dict[int, bytearray] = {}
        self._page_size = 0x1000

    def _page(self, addr: int) -> bytearray:
        page = addr & ~(self._page_size - 1)
        existing = self._pages.get(page)
        if existing is None:
            existing = bytearray(self._page_size)
            self._pages[page] = existing
        return existing

    def write(self, addr: int, data: bytes) -> None:
        i = 0
        while i < len(data):
            page_off = addr & (self._page_size - 1)
            page = self._page(addr)
            n = min(len(data) - i, self._page_size - page_off)
            page[page_off:page_off + n] = data[i:i + n]
            addr += n
            i += n

    def read(self, addr: int, n: int) -> bytes:
        out = bytearray()
        while len(out) < n:
            page_off = addr & (self._page_size - 1)
            page = self._page(addr)
            take = min(n - len(out), self._page_size - page_off)
            out += page[page_off:page_off + take]
            addr += take
        return bytes(out)

    def read_u64(self, addr: int) -> int:
        return struct.unpack("<Q", self.read(addr, 8))[0]

    def write_u64(self, addr: int, value: int) -> None:
        self.write(addr, struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF))

    def read_u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read(addr, 4))[0]

    def write_u32(self, addr: int, value: int) -> None:
        self.write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def read_u8(self, addr: int) -> int:
        return self._page(addr)[addr & (self._page_size - 1)]

    def write_u8(self, addr: int, value: int) -> None:
        self._page(addr)[addr & (self._page_size - 1)] = value & 0xFF


# ---------------------------------------------------------------------------
# Emulator
# ---------------------------------------------------------------------------

class Emulator:
    """The minimal x86-64 user-mode emulator."""

    def __init__(self, *, code: bytes = b"",
                 base: int = 0x400000,
                 stack_top: int = 0x7FFF_0000,
                 stack_size: int = 0x40000) -> None:
        self.regs = Registers()
        self.mem = Memory()
        self.regs.set(REG_RSP, stack_top - 0x100)
        self.base = base
        self.stack_top = stack_top
        self.stack_size = stack_size
        self.rip = base
        self.stopped = False
        self.exit_code: int = 0
        # Install the code if any.
        if code:
            self.mem.write(base, code)
        # Allocate the stack.
        self.mem.write(stack_top - stack_size, b"\x00" * stack_size)
        # Imports table: thunk address -> (name, callable).
        self._thunks: Dict[int, Tuple[str, Callable]] = {}
        self._thunk_count = 0
        # Stats.
        self.steps = 0

    # ------------------------------------------------------------------
    # Thunk installation
    # ------------------------------------------------------------------

    def install_thunk(self, name: str, callable_: Callable
                       ) -> int:
        """Reserve a memory address whose contents (a fake 'function
        entry') represent this Python callable.

        The address is what a PE's IAT should point at; calling it
        triggers :meth:`_invoke_thunk`.
        """
        self._thunk_count += 1
        addr = 0x80000000 + self._thunk_count * 0x10
        self._thunks[addr] = (name, callable_)
        # Store a single-byte opcode (CC = int 3) at the thunk so the
        # emulator stops there and dispatches.
        self.mem.write(addr, b"\xCC")
        return addr

    def _invoke_thunk(self, addr: int) -> None:
        info = self._thunks.get(addr)
        if info is None:
            raise EmulatorError(f"unknown thunk at 0x{addr:x}")
        name, callable_ = info
        log.debug("thunk call: %s @ 0x%016x", name, self.regs.get(REG_RIP))
        # Tolerate both ``callable_()`` (kernel32 plain functions) and
        # ``callable_(emu)`` (stubs that want the emulator).
        import inspect as _inspect
        try:
            sig = _inspect.signature(callable_)
        except (TypeError, ValueError):
            sig = None
        if sig is not None and len(sig.parameters) == 0:
            result = callable_()
        else:
            result = callable_(self)
        # Place the return value (if it's a Win32-ish integer) in rax.
        if isinstance(result, (int, bool)):
            self.regs.set(0, int(result) & 0xFFFFFFFFFFFFFFFF)
        # The thunk is reached via a Win32 ``call [IAT]`` which
        # pushed a return address onto the stack.  Pop it now and
        # resume execution at the caller.
        ret = self._pop()
        self.regs.set(REG_RIP, ret)

    # ------------------------------------------------------------------
    # Decode helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _modrm_size(mod: int, rm: int) -> int:
        if mod == 0 and rm == 5:
            return 4    # RIP-relative addressing
        if mod == 0:
            return 0
        if mod == 1:
            return 1    # disp8
        if mod == 2:
            return 4    # disp32
        return 0

    def _decode_modrm(self, addr: int, mod: int, rm: int, rex_b: bool
                       ) -> Tuple[str, Any, int]:
        """Decode ModR/M + SIB + disp at ``addr``.

        ``addr`` is the *post-ModR/M* address (i.e. the address of
        the byte immediately after the ModR/M byte).  The function
        returns ``(kind, value, n)`` where ``n`` is the number of
        bytes consumed from ``addr`` onwards (i.e. SIB + disp).
        The caller updates RIP to ``addr + n``.
        """
        n = 0    # bytes consumed from addr onwards
        if mod == 3:
            return ("reg", (rm + (8 if rex_b else 0)), n)

        # Memory operand: SIB + displacement.
        if rm == 4:
            sib = self.mem.read(addr + n, 1)[0]
            n += 1
            scale = 1 << (sib >> 6)
            idx = (sib >> 3) & 7
            base = sib & 7
            if base == 5 and mod == 0:
                # ModR/M=00 r/m=5 (i.e. SIB base=5) -> no base reg,
                # displacement is 32 bits.
                disp = self._signed(self.mem.read_u32(addr + n), 32)
                n += 4
                base_idx = None
            else:
                base_idx = base
                # Read the displacement according to mod.
                if mod == 1:
                    disp = self._signed(self.mem.read_u8(addr + n), 8)
                    n += 1
                elif mod == 2:
                    disp = self._signed(self.mem.read_u32(addr + n), 32)
                    n += 4
                else:
                    disp = 0
            # Apply REX.X to index, REX.B to base.
            if rex_b and base_idx is not None:
                base_idx = (base_idx + 8) & 0xF
            idx = (idx + 8) & 0xF if (self._rex & 0x2) else idx
            if base_idx is None:
                addr_val = disp
            else:
                addr_val = self.regs.get(base_idx) + disp
            addr_val += self.regs.get(idx) * scale if idx != 4 else 0
        else:
            base_idx = rm
            if rex_b:
                base_idx = (base_idx + 8) & 0xF
            base_val = self.regs.get(base_idx)
            if mod == 0 and rm == 5:
                disp = self._signed(self.mem.read_u32(addr + n), 32)
                n += 4
                # RIP-relative addressing: address = RIP_next + disp.
                # RIP_next is the address of the next instruction,
                # which equals ``addr + n`` (the post-ModR/M address
                # plus everything we just consumed).
                addr_val = (addr + n) + disp
            elif mod == 0:
                addr_val = base_val
            elif mod == 1:
                disp = self._signed(self.mem.read_u8(addr + n), 8)
                n += 1
                addr_val = base_val + disp
            else:    # mod == 2
                disp = self._signed(self.mem.read_u32(addr + n), 32)
                n += 4
                addr_val = base_val + disp
        return ("mem", addr_val, n)

    @staticmethod
    def _signed(value: int, bits: int) -> int:
        sign = 1 << (bits - 1)
        return value - (1 << bits) if value & sign else value

    # ------------------------------------------------------------------
    # Operand decoders
    # ------------------------------------------------------------------

    def _read_imm(self, addr: int, n: int) -> Tuple[int, int]:
        """Read ``n`` bytes starting at ``addr`` and decode as little-endian."""
        data = self.mem.read(addr, n)
        if n == 1:
            return data[0], 1
        if n == 2:
            return struct.unpack("<H", data)[0], 2
        if n == 4:
            return struct.unpack("<I", data)[0], 4
        if n == 8:
            return struct.unpack("<Q", data)[0], 8
        raise EmulatorDecodeError(f"bad imm size {n}")

    def _resolve_rm(self, addr: int, mod: int, rm: int, rex_b: bool,
                    op_size: int = 8) -> Tuple[str, Any, int]:
        kind, val, n = self._decode_modrm(addr, mod, rm, rex_b)
        if kind == "reg":
            return (kind, val, n)
        if op_size == 1:
            return ("mem8", val, n)
        if op_size == 2:
            return ("mem16", val, n)
        if op_size == 4:
            return ("mem32", val, n)
        return ("mem64", val, n)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    _rex: int = 0

    def step(self) -> None:
        """Decode and execute one instruction."""
        ip = self.regs.get(15)
        # We use rip-relative addressing via the *current* RIP,
        # which is normally what Intel specifies for a fetch before
        # the next instruction.
        # BUT we read the opcode byte at this address.
        b0 = self.mem.read_u8(ip)
        # Parse (possibly multiple) REX prefixes.  Strict-mode Intel
        # only allows one but MSVC and GCC occasionally emit redundant
        # ones (``40 48 ...``) which CPUs tolerate by letting the last
        # REX win.  We mimic that behaviour.
        rex = 0
        while 0x40 <= b0 <= 0x4F:
            rex = b0 - 0x40
            self._rex = rex
            ip += 1
            b0 = self.mem.read_u8(ip)
        rex_w = bool(rex & 0x8)
        rex_r = (rex & 0x4) << 1
        rex_x = (rex & 0x2) << 2
        rex_b = bool(rex & 0x1)
        # Detect 0F escape.
        op_size = 8 if rex_w else 4
        if b0 == 0x0F:
            b1 = self.mem.read_u8(ip + 1)
            ip += 2
            self._decode_twobyte(b1, ip, rex, rex_w, rex_r, rex_x, rex_b,
                                  op_size)
            return
        ip += 1
        self._decode_onebyte(b0, ip, rex, rex_w, rex_r, rex_x, rex_b,
                              op_size)

    def _decode_onebyte(self, op: int, ip: int, rex: int, rex_w: int,
                         rex_r: int, rex_x: int, rex_b: int,
                         op_size: int) -> None:
        # 50-57 push reg
        if 0x50 <= op <= 0x57:
            reg = op - 0x50 + rex_b * 8
            self._push(self.regs.get(reg))
            self.regs.set(15, ip)
            return
        # 58-5F pop reg
        if 0x58 <= op <= 0x5F:
            reg = op - 0x58 + rex_b * 8
            v = self._pop()
            self.regs.set(reg, v)
            self.regs.set(15, ip)
            return
        # B0-B7 mov r8, imm8
        if 0xB0 <= op <= 0xB7:
            reg = op - 0xB0 + rex_b * 8
            imm, _ = self._read_imm(ip, 1)
            if reg < 8:
                # Write low byte of the register.
                old = self.regs.get(reg)
                self.regs.set(reg, (old & ~0xFF) | imm)
            else:
                self.regs.set(reg, imm)
            self.regs.set(15, ip + 1)
            return
        # B8-BF mov reg, imm (size = op_size)
        if 0xB8 <= op <= 0xBF:
            reg = op - 0xB8 + rex_b * 8
            imm, n = self._read_imm(ip, op_size)
            self.regs.set(reg, imm)
            self.regs.set(15, ip + n)
            return
        if op == 0xC3:
            # ret -- pop RIP.
            self.regs.set(15, self._pop())
            return
        if op == 0x60:
            # 0x60 = PUSHAD in 32-bit mode; in 64-bit (long) mode the
            # opcode is undefined.  Some Win10 binaries emit it as
            # padding/junk, so just advance past it like a NOP.
            self.regs.set(15, ip)
            return
        if op == 0x61:
            # 0x61 = POPAD -- same undefined-in-long-mode treatment.
            self.regs.set(15, ip)
            return
        if op == 0xC4:
            # VEX 3-byte prefix (0xC4 byte1 byte3 opcode).  We don't
            # actually decode VEX-encoded AVX; the safest stub is to
            # ignore the prefix (we already did — op == 0xC4 is the
            # one-byte opcode slot) and re-enter the main decoder at
            # the byte after the VEX 3-byte sequence.  That lets our
            # existing 0x0F-escape, FPU, and SSE/MMX skip handlers
            # see the actual instruction.
            self.regs.set(15, ip + 3)
            return
        if op == 0xC5:
            # VEX 2-byte prefix (0xC5 byte2 opcode).
            self.regs.set(15, ip + 2)
            return
        if op == 0xC2:
            # ret imm16 -- pop RIP then add imm16 to rsp (callee stack cleanup).
            imm, _ = self._read_imm(ip, 2)
            self.regs.set(15, self._pop())
            self.regs.set(REG_RSP, self.regs.get(REG_RSP) + imm)
            return
        if op == 0x68:
            # push imm32 (sign-extended to 64 bits in 64-bit mode).
            imm, _ = self._read_imm(ip, 4)
            self._push(self._signed(imm, 32))
            self.regs.set(15, ip + 4)
            return
        if op == 0x6A:
            # push imm8 (sign-extended).
            imm, _ = self._read_imm(ip, 1)
            self._push(self._signed(imm, 8))
            self.regs.set(15, ip + 1)
            return
        if op == 0xC9:
            # leave: rsp = rbp; pop rbp.
            self.regs.set(REG_RSP, self.regs.get(REG_RBP))
            self.regs.set(REG_RBP, self._pop())
            self.regs.set(15, ip)
            return
        if op == 0x90:
            self.regs.set(15, ip)
            return
        if op == 0x9E:  # SAHF
            ah = (self.regs.get(REG_RAX) >> 8) & 0xFF
            self.regs.cf = ah & 0x01
            self.regs.pf = (ah >> 2) & 0x01
            self.regs.zf = (ah >> 6) & 0x01
            self.regs.sf = (ah >> 7) & 0x01
            self.regs.set(15, ip + 1)
            return
        if op == 0xA0:
            # mov al, moffs8 -- load byte from absolute 16-bit offset.
            moffs = struct.unpack("<H", self.mem.read(ip, 2))[0]
            self.regs.set(REG_RAX, (self.regs.get(REG_RAX) & ~0xFF)
                          | self.mem.read_u8(moffs))
            self.regs.set(15, ip + 2)
            return
        if op == 0xA1:
            # mov ax/eax/rax, moffs -- load word/dword/qword.
            moffs = struct.unpack("<H", self.mem.read(ip, 2))[0]
            if op_size == 8:
                self.regs.set(REG_RAX, self.mem.read_u64(moffs))
            elif op_size == 4:
                self.regs.set(REG_RAX,
                              (self.regs.get(REG_RAX) & 0xFFFFFFFF00000000)
                              | self.mem.read_u32(moffs))
            else:
                self.regs.set(REG_RAX, (self.regs.get(REG_RAX) & ~0xFFFF)
                              | self.mem.read_u16(moffs))
            self.regs.set(15, ip + 2)
            return
        if op == 0xA2:
            # mov moffs8, al -- store byte to absolute 16-bit offset.
            moffs = struct.unpack("<H", self.mem.read(ip, 2))[0]
            self.mem.write_u8(moffs, self.regs.get(REG_RAX) & 0xFF)
            self.regs.set(15, ip + 2)
            return
        if op == 0xA3:
            # mov moffs, ax/eax/rax -- store word/dword/qword.
            moffs = struct.unpack("<H", self.mem.read(ip, 2))[0]
            if op_size == 8:
                self.mem.write_u64(moffs, self.regs.get(REG_RAX))
            elif op_size == 4:
                self.mem.write_u32(moffs, self.regs.get(REG_RAX) & 0xFFFFFFFF)
            else:
                self.mem.write_u16(moffs, self.regs.get(REG_RAX) & 0xFFFF)
            self.regs.set(15, ip + 2)
            return
        if op == 0x9F:  # LAHF
            ah = 0
            ah |= (self.regs.cf & 0x01) << 0
            ah |= 1 << 1                                # always 1
            ah |= (self.regs.pf & 0x01) << 2
            ah |= (self.regs.zf & 0x01) << 6
            ah |= (self.regs.sf & 0x01) << 7
            self.regs.set(REG_RAX, (self.regs.get(REG_RAX) & ~0xFF00) | (ah << 8))
            self.regs.set(15, ip + 1)
            return
        if op == 0x6C:
            # insb -- port I/O; we have no hardware emulation, so this
            # is a no-op (the caller does not check the byte).
            self.regs.set(15, ip + 1)
            return
        if op == 0x6D:
            # insw/insd
            self.regs.set(15, ip + 1)
            return
        if op == 0x6E:
            # outsb -- port I/O; no-op.
            self.regs.set(15, ip + 1)
            return
        if op == 0x6F:
            # outsw/outsd
            self.regs.set(15, ip + 1)
            return
        if op == 0xEC:
            # in al, dx
            self.regs.set(15, ip + 1)
            return
        if op == 0xED:
            # in eax, dx
            self.regs.set(15, ip + 1)
            return
        if op == 0xEE:
            # out dx, al
            self.regs.set(15, ip + 1)
            return
        if op == 0xEF:
            # out dx, eax
            self.regs.set(15, ip + 1)
            return
        if op == 0xE4:
            # in al, imm8
            self.regs.set(15, ip + 2)
            return
        if op == 0xE5:
            # in eax, imm8
            self.regs.set(15, ip + 2)
            return
        if op == 0xE6:
            # out imm8, al
            self.regs.set(15, ip + 2)
            return
        if op == 0xE7:
            # out imm8, eax
            self.regs.set(15, ip + 2)
            return
        if op == 0xF2:
            # REP prefix (F2 or F3) -- simplest interpretation: ignore
            # the prefix and decode the next instruction.  This is
            # safe for ``repz retn`` etc.
            self.regs.set(15, ip)
            return
        if op == 0xF3:
            # REP / REPZ (3) prefix -- ignore.
            self.regs.set(15, ip)
            return
        if op in (0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65):
            # Segment override prefixes -- in flat 64-bit mode, ignore.
            self.regs.set(15, ip)
            return
        if op == 0x66:
            # Operand-size prefix -- ignored for our 64-bit decoder.
            self.regs.set(15, ip)
            return
        if op == 0x67:
            # Address-size prefix -- ignored for our 64-bit decoder.
            self.regs.set(15, ip)
            return
        if op == 0xF8:
            # clc
            self.regs.cf = 0
            self.regs.set(15, ip + 1)
            return
        if op == 0xF9:
            # stc
            self.regs.cf = 1
            self.regs.set(15, ip + 1)
            return
        if op == 0xFC:
            # cld
            self.regs.df = 0
            self.regs.set(15, ip + 1)
            return
        if op == 0xFD:
            # std
            self.regs.df = 1
            self.regs.set(15, ip + 1)
            return
        if op == 0xCC:
            # int 3 - signal breakpoint.  If the address is a
            # registered thunk, dispatch it; otherwise treat as
            # a debugging-style no-op (some Win10 PEs emit int3 as
            # padding between functions).
            cur_rip = self.regs.get(15)
            if cur_rip in self._thunks:
                self._invoke_thunk(cur_rip)
                return
            self.regs.set(15, ip)
            return
        if op == 0xCD:
            # int imm8 -- software interrupt (DOS/Win16 only).  Skip.
            self.regs.set(15, ip + 2)
            return
        if op == 0xF1:
            # int1 / icebp -- skip.
            self.regs.set(15, ip + 1)
            return
        if op == 0xF4:
            # hlt -- terminate cleanly.
            self.stopped = True
            raise EmulatorHalt("HLT")
        if op == 0xE9:
            disp, _ = self._read_imm(ip, 4)
            target = (ip + 4) + self._signed(disp, 32)
            self.regs.set(15, target)
            return
        if op == 0xEA:
            # jmp far ptr -- in 64-bit flat mode the segment selector
            # is ignored, so we just jump to the absolute offset.
            offset = struct.unpack("<Q", self.mem.read(ip, 8))[0]
            self.regs.set(15, offset)
            return
        if op == 0xE8:
            # call near rel32 -- push return address then jump.
            disp, _ = self._read_imm(ip, 4)
            target = (ip + 4) + self._signed(disp, 32)
            self._push(ip + 4)
            self.regs.set(15, target)
            return
        if op == 0xEB:
            disp, _ = self._read_imm(ip, 1)
            target = (ip + 1) + self._signed(disp, 8)
            self.regs.set(15, target)
            return
        # 70-7F short conditional jumps
        if 0x70 <= op <= 0x7F:
            disp, _ = self._read_imm(ip, 1)
            target = (ip + 1) + self._signed(disp, 8)
            taken = False
            if op == 0x70:    # jo
                taken = self.regs.of == 1
            elif op == 0x71:    # jno
                taken = self.regs.of == 0
            elif op == 0x72:    # jb/jc
                taken = self.regs.cf == 1
            elif op == 0x73:    # jnb/jnc/jae
                taken = self.regs.cf == 0
            elif op == 0x74:    # je/jz
                taken = self.regs.zf == 1
            elif op == 0x75:    # jne/jnz
                taken = self.regs.zf == 0
            elif op == 0x76:    # jbe
                taken = self.regs.cf == 1 or self.regs.zf == 1
            elif op == 0x77:    # jnbe/ja
                taken = self.regs.cf == 0 and self.regs.zf == 0
            elif op == 0x78:    # js
                taken = self.regs.sf == 1
            elif op == 0x79:    # jns
                taken = self.regs.sf == 0
            elif op == 0x7A:    # jp
                taken = self.regs.pf == 1
            elif op == 0x7B:    # jnp
                taken = self.regs.pf == 0
            elif op == 0x7C:    # jl
                taken = self.regs.sf != self.regs.of
            elif op == 0x7D:    # jge
                taken = self.regs.sf == self.regs.of
            elif op == 0x7E:    # jle
                taken = self.regs.zf == 1 or self.regs.sf != self.regs.of
            elif op == 0x7F:    # jg
                taken = self.regs.zf == 0 and self.regs.sf == self.regs.of
            if taken:
                self.regs.set(15, target)
            else:
                self.regs.set(15, ip + 1)
            return
        # 24/34/2C/3C AL/AX/EAX op imm8
        if op in (0x24, 0x34, 0x2C, 0x3C):
            imm, n = self._read_imm(ip, 1)
            old = self.regs.get(REG_RAX)
            if op == 0x24:
                self.regs.set(REG_RAX, (old & ~0xFF) | (imm & 0xFF))
            elif op == 0x34:
                self.regs.set(REG_RAX, (old & ~0xFF) | ((old ^ imm) & 0xFF))
            elif op == 0x2C:
                self.regs.set(REG_RAX, (old & ~0xFF) | ((old - imm) & 0xFF))
            elif op == 0x3C:
                self.regs.set(REG_RAX, (old & ~0xFF) | ((old - imm) & 0xFF))
                self.regs.zf = 1 if (old & 0xFF) == imm else 0
            self.regs.set(15, ip + n)
            return
        # ModR/M byte required for most remaining instructions.
        modrm = self.mem.read_u8(ip)
        mod = (modrm >> 6) & 3
        reg = (modrm >> 3) & 7
        rm = modrm & 7
        op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
        # We pass ``ip + 1`` because ModR/M itself was 1 byte; the
        # _resolve_rm helper expects the *post-ModR/M* address.
        rm_addr = ip + 1
        if op == 0x89:
            # mov r/m, reg
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                self.regs.set(val, self.regs.get(op_reg))
            elif kind == "mem64":
                self.mem.write_u64(val, self.regs.get(op_reg))
            elif kind == "mem32":
                self.mem.write_u32(val, self.regs.get(op_reg) & 0xFFFFFFFF)
            elif kind == "mem8":
                self.mem.write_u8(val, self.regs.get(op_reg) & 0xFF)
            else:
                self.mem.write(val, struct.pack("<H",
                            self.regs.get(op_reg) & 0xFFFF))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x8B:
            # mov r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            elif kind == "mem32":
                src = self.mem.read_u32(val)
            elif kind == "mem8":
                src = self.mem.read_u8(val)
            else:
                src = struct.unpack("<H", self.mem.read(val, 2))[0]
            self.regs.set(op_reg, src)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x01:
            # add r/m, reg
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            src = self.regs.get(op_reg)
            if kind == "reg":
                tgt = self.regs.get(val)
                res = (tgt + src) & ((1 << (op_size * 8)) - 1)
                self.regs.set(val, res)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
                res = (tgt + src) & 0xFFFFFFFFFFFFFFFF
                self.mem.write_u64(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x00:
            # add r/m8, r8
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            cur = self.regs.get(op_reg) & 0xFF
            res = (cur + src) & 0xFF
            if kind == "reg":
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            elif kind == "mem8" or kind == "mem":
                self.mem.write_u8(val, res & 0xFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x02:
            # add r8, r/m8
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            cur = self.regs.get(op_reg) & 0xFF
            res = (cur + src) & 0xFF
            if kind == "reg":
                self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | res)
            elif kind == "mem8" or kind == "mem":
                cur_mem = self.mem.read_u8(val)
                self.mem.write_u8(val, (cur_mem + cur) & 0xFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x03:
            # add r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            self.regs.set(op_reg,
                          (self.regs.get(op_reg) + src) & ((1 << (op_size * 8)) - 1))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x29:
            # sub r/m, r
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "mem64":
                tgt = self.mem.read_u64(val)
                res = (tgt - self.regs.get(op_reg)) & 0xFFFFFFFFFFFFFFFF
                self.mem.write_u64(val, res)
            elif kind == "reg":
                tgt = self.regs.get(val)
                res = (tgt - self.regs.get(op_reg)) & ((1 << (op_size * 8)) - 1)
                self.regs.set(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x09:
            # or r/m, r
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                self.regs.set(val, self.regs.get(val) | self.regs.get(op_reg))
            elif kind == "mem64":
                self.mem.write_u64(val,
                                    self.mem.read_u64(val) | self.regs.get(op_reg))
            elif kind == "mem32":
                self.mem.write_u32(val,
                                    self.mem.read_u32(val)
                                    | (self.regs.get(op_reg) & 0xFFFFFFFF))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x0B:
            # or r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(op_reg, (self.regs.get(op_reg) | src) & mask)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x2B:
            # sub r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            else:
                src = self.mem.read_u64(val)
            self.regs.set(op_reg,
                          (self.regs.get(op_reg) - src) & ((1 << (op_size * 8)) - 1))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x11:
            # adc r/m, r
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            mask = (1 << (op_size * 8)) - 1
            if kind == "reg":
                tgt = self.regs.get(val)
                res = (tgt + self.regs.get(op_reg) + self.regs.cf) & mask
                self._cmp_arith(tgt, self.regs.get(op_reg), res, op_size)
                self.regs.set(val, res)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
                res = (tgt + self.regs.get(op_reg) + self.regs.cf) & 0xFFFFFFFFFFFFFFFF
                self._cmp_arith(tgt, self.regs.get(op_reg), res, 8)
                self.mem.write_u64(val, res)
            elif kind == "mem32":
                tgt = self.mem.read_u32(val)
                res = (tgt + (self.regs.get(op_reg) & 0xFFFFFFFF)
                       + self.regs.cf) & 0xFFFFFFFF
                self._cmp_arith(tgt, self.regs.get(op_reg), res, op_size)
                self.mem.write_u32(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x13:
            # adc r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            mask = (1 << (op_size * 8)) - 1
            new = (self.regs.get(op_reg) + src + self.regs.cf) & mask
            self._cmp_arith(self.regs.get(op_reg), src, new, op_size)
            self.regs.set(op_reg, new)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x15:
            # adc eax, imm32 (or rax with REX.W)
            imm, _ = self._read_imm(ip, 4)
            mask = (1 << (op_size * 8)) - 1
            new = (self.regs.get(op_reg) + imm + self.regs.cf) & mask
            self._cmp_arith(self.regs.get(op_reg), imm, new, op_size)
            self.regs.set(op_reg, new)
            self.regs.set(15, ip + 4)
            return
        if op == 0x19:
            # sbb r/m, r
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            mask = (1 << (op_size * 8)) - 1
            if kind == "reg":
                tgt = self.regs.get(val)
                res = (tgt - self.regs.get(op_reg) - self.regs.cf) & mask
                self._cmp_arith(tgt, self.regs.get(op_reg), res, op_size)
                self.regs.set(val, res)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
                res = (tgt - self.regs.get(op_reg) - self.regs.cf) & 0xFFFFFFFFFFFFFFFF
                self._cmp_arith(tgt, self.regs.get(op_reg), res, 8)
                self.mem.write_u64(val, res)
            elif kind == "mem32":
                tgt = self.mem.read_u32(val)
                res = (tgt - (self.regs.get(op_reg) & 0xFFFFFFFF)
                       - self.regs.cf) & 0xFFFFFFFF
                self._cmp_arith(tgt, self.regs.get(op_reg), res, op_size)
                self.mem.write_u32(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x1B:
            # sbb r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            mask = (1 << (op_size * 8)) - 1
            new = (self.regs.get(op_reg) - src - self.regs.cf) & mask
            self._cmp_arith(self.regs.get(op_reg), src, new, op_size)
            self.regs.set(op_reg, new)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x1D:
            # sbb eax, imm32
            imm, _ = self._read_imm(ip, 4)
            mask = (1 << (op_size * 8)) - 1
            new = (self.regs.get(op_reg) - imm - self.regs.cf) & mask
            self._cmp_arith(self.regs.get(op_reg), imm, new, op_size)
            self.regs.set(op_reg, new)
            self.regs.set(15, ip + 4)
            return
        if op == 0x0D:
            # or eax, imm32 (or rax with REX.W)
            imm, _ = self._read_imm(ip, 4)
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(op_reg, (self.regs.get(op_reg) | imm) & mask)
            self.regs.cf = 0
            self.regs.of = 0
            self.regs.set(15, ip + 4)
            return
        if op == 0x0C:
            # or al, imm8
            imm, _ = self._read_imm(ip, 1)
            self.regs.set(REG_RAX, (self.regs.get(REG_RAX) & ~0xFF) | imm)
            self.regs.cf = 0
            self.regs.of = 0
            self.regs.set(15, ip + 1)
            return
        if op == 0x31:
            # xor r/m, r
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "mem64":
                tgt = self.mem.read_u64(val)
                res = tgt ^ self.regs.get(op_reg)
                self.mem.write_u64(val, res)
            elif kind == "reg":
                tgt = self.regs.get(val)
                res = tgt ^ self.regs.get(op_reg)
                self.regs.set(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x33:
            # xor r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            else:
                src = self.mem.read_u64(val)
            self.regs.set(op_reg, self.regs.get(op_reg) ^ src)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x32:
            # xor r/m8, r8
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            cur = self.regs.get(op_reg) & 0xFF
            res = cur ^ src
            if kind == "reg":
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            elif kind == "mem8" or kind == "mem":
                self.mem.write_u8(val, res & 0xFF)
            else:
                self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x3D:
            # cmp eax, imm32 (or rax, imm32 with REX.W)
            imm, n = self._read_imm(ip, 4 if not rex_w else 8)
            self._cmp(self.regs.get(REG_RAX), imm, op_size)
            self.regs.set(15, ip + n)
            return
        if op == 0x05:
            # add eax, imm32 (or rax, imm32 with REX.W)
            imm, n = self._read_imm(ip, 4 if not rex_w else 8)
            mask = (1 << (op_size * 8)) - 1
            old = self.regs.get(REG_RAX)
            new = (old + imm) & mask
            self.regs.set(REG_RAX, new)
            self._cmp_arith(old, imm, new, op_size)
            self.regs.set(15, ip + n)
            return
        if op == 0x0D:
            # or eax, imm32 (or rax with REX.W)
            imm, n = self._read_imm(ip, 4 if not rex_w else 8)
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(REG_RAX, (self.regs.get(REG_RAX) | imm) & mask)
            self.regs.cf = 0
            self.regs.of = 0
            self.regs.set(15, ip + n)
            return
        if op == 0x25:
            # and eax, imm32 (or rax with REX.W)
            imm, n = self._read_imm(ip, 4 if not rex_w else 8)
            self._cmp(self.regs.get(REG_RAX), imm, op_size)
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(REG_RAX, (self.regs.get(REG_RAX) & imm) & mask)
            self.regs.cf = 0
            self.regs.of = 0
            self.regs.set(15, ip + n)
            return
        if op == 0x2D:
            # sub eax, imm32 (or rax with REX.W)
            imm, n = self._read_imm(ip, 4 if not rex_w else 8)
            mask = (1 << (op_size * 8)) - 1
            old = self.regs.get(REG_RAX)
            new = (old - imm) & mask
            self.regs.set(REG_RAX, new)
            self._cmp_arith(old, imm, new, op_size)
            self.regs.set(15, ip + n)
            return
        if op == 0x35:
            # xor eax, imm32 (or rax with REX.W)
            imm, n = self._read_imm(ip, 4 if not rex_w else 8)
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(REG_RAX, (self.regs.get(REG_RAX) ^ imm) & mask)
            self.regs.cf = 0
            self.regs.of = 0
            self.regs.set(15, ip + n)
            return
        if op == 0x3B:
            # cmp r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            else:
                src = self.mem.read_u64(val)
            self._cmp(self.regs.get(op_reg), src, op_size)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x84:
            # test r/m8, r8
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            self._cmp(self.regs.get(op_reg) & 0xFF, src, 1)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x8C:
            # mov r/m, sreg -- in flat 64-bit mode segment registers
            # are vestigial, so just return a flat selector.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 2)
            if kind == "reg":
                self.regs.set(val, 0)
            else:
                self.mem.write_u16(val, 0)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xFE:
            # Byte inc/dec: /0 inc r/m8, /1 dec r/m8.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
            else:
                tgt = self.mem.read_u8(val)
            if reg == 0:
                res = (tgt + 1) & 0xFF
            elif reg == 1:
                res = (tgt - 1) & 0xFF
            else:
                res = tgt
            if kind == "reg":
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                self.mem.write_u8(val, res & 0xFF)
            self.regs.set(15, rm_addr + n)
            return
        # NOTE: The 0xFF handler is consolidated later in this function
        # (see "Group 5 unified handler" below).  Keeping a stub here
        # would shadow it.  Removing the duplicate ensures /2 (call r/m),
        # /4 (jmp r/m), /3 (call far), /5 (jmp far) all dispatch to the
        # unified handler.
        if op == 0x85:
            # test r/m, r
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            self._cmp(self.regs.get(op_reg), src, op_size)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x87:
            # xchg r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                a = self.regs.get(op_reg)
                b = self.regs.get(val)
                self.regs.set(op_reg, b)
                self.regs.set(val, a)
            elif kind == "mem64":
                m = self.mem.read_u64(val)
                r = self.regs.get(op_reg)
                self.mem.write_u64(val, r)
                self.regs.set(op_reg, m)
            elif kind == "mem32":
                m = self.mem.read_u32(val)
                r = self.regs.get(op_reg) & 0xFFFFFFFF
                self.mem.write_u32(val, r)
                # The high 32 bits of the register are zeroed on 32-bit xchg.
                self.regs.set(op_reg, m & 0xFFFFFFFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xA8:
            # test al, imm8
            imm, _ = self._read_imm(ip, 1)
            self._cmp(self.regs.get(op_reg) & 0xFF, imm, 1)
            self.regs.set(15, ip + 1)
            return
        if op == 0xA9:
            # test eax, imm32 (or rax with REX.W)
            imm, _ = self._read_imm(ip, 4)
            self._cmp(self.regs.get(op_reg), imm, op_size)
            self.regs.set(15, ip + 4)
            return
        if op == 0x39:
            # cmp r/m, r
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                tgt = self.regs.get(val)
            else:
                tgt = self.mem.read_u64(val)
            self._cmp(tgt, self.regs.get(op_reg), op_size)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x22:
            # and r8, r/m8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            res = (self.regs.get(op_reg) & 0xFF) & src
            self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x20:
            # and r/m8, r8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
                res = tgt & (self.regs.get(op_reg) & 0xFF)
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                tgt = self.mem.read_u8(val)
                self.mem.write_u8(val, tgt & (self.regs.get(op_reg) & 0xFF))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x08:
            # or r/m8, r8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
                res = tgt | (self.regs.get(op_reg) & 0xFF)
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                tgt = self.mem.read_u8(val)
                self.mem.write_u8(val, tgt | (self.regs.get(op_reg) & 0xFF))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x10:
            # adc r/m8, r8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
                res = (tgt + (self.regs.get(op_reg) & 0xFF)
                       + self.regs.cf) & 0xFF
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                tgt = self.mem.read_u8(val)
                res = (tgt + (self.regs.get(op_reg) & 0xFF)
                       + self.regs.cf) & 0xFF
                self.mem.write_u8(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x12:
            # adc r8, r/m8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            res = ((self.regs.get(op_reg) & 0xFF) + src + self.regs.cf) & 0xFF
            self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x18:
            # sbb r/m8, r8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
                res = (tgt - (self.regs.get(op_reg) & 0xFF) - self.regs.cf) & 0xFF
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                tgt = self.mem.read_u8(val)
                res = (tgt - (self.regs.get(op_reg) & 0xFF) - self.regs.cf) & 0xFF
                self.mem.write_u8(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x1A:
            # sbb r8, r/m8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            res = ((self.regs.get(op_reg) & 0xFF) - src - self.regs.cf) & 0xFF
            self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x28:
            # sub r/m8, r8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
                res = (tgt - (self.regs.get(op_reg) & 0xFF)) & 0xFF
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                tgt = self.mem.read_u8(val)
                self.mem.write_u8(val,
                                  (tgt - (self.regs.get(op_reg) & 0xFF)) & 0xFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x2A:
            # sub r8, r/m8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            res = ((self.regs.get(op_reg) & 0xFF) - src) & 0xFF
            self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x30:
            # xor r/m8, r8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
                res = tgt ^ (self.regs.get(op_reg) & 0xFF)
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                tgt = self.mem.read_u8(val)
                self.mem.write_u8(val, tgt ^ (self.regs.get(op_reg) & 0xFF))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x32:
            # xor r8, r/m8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            res = ((self.regs.get(op_reg) & 0xFF) ^ src) & 0xFF
            self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x38:
            # cmp r/m8, r8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            tgt = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            self._cmp(tgt, self.regs.get(op_reg) & 0xFF, 1)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x3A:
            # cmp r8, r/m8 (8-bit)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            src = (self.regs.get(val) & 0xFF) if kind == "reg" else self.mem.read_u8(val)
            self._cmp(self.regs.get(op_reg) & 0xFF, src, 1)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x23:
            # and r, r/m
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(op_reg, self.regs.get(op_reg) & src & mask)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x24:
            # and al, imm8
            imm, _ = self._read_imm(ip, 1)
            self.regs.set(op_reg, (self.regs.get(op_reg) & ~0xFF) | ((self.regs.get(op_reg) & 0xFF) & imm))
            self.regs.set(15, ip + 1)
            return
        if op == 0x25:
            # and eax, imm32 (or rax with REX.W)
            imm, _ = self._read_imm(ip, 4)
            self.regs.set(op_reg, self.regs.get(op_reg) & imm)
            self.regs.set(15, ip + 4)
            return
        if op == 0x8D:
            # lea r, [m]
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b)
            if kind in ("mem", "mem8", "mem16", "mem32", "mem64"):
                self.regs.set(op_reg, val & 0xFFFFFFFFFFFFFFFF)
            else:
                raise EmulatorDecodeError("lea with register operand")
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xFF:
            # Group 5 unified handler:
            #   /0 inc r/m, /1 dec r/m, /2 call near r/m, /3 call far m16:64,
            #   /4 jmp near r/m, /5 jmp far m16:64, /6 push r/m.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if reg == 0:        # inc r/m
                if kind == "reg":
                    res = (self.regs.get(val) + 1) & ((1 << (op_size * 8)) - 1)
                    self.regs.set(val, res)
                elif kind == "mem64":
                    res = (self.mem.read_u64(val) + 1) & 0xFFFFFFFFFFFFFFFF
                    self.mem.write_u64(val, res)
                else:
                    res = (self.mem.read_u32(val) + 1) & 0xFFFFFFFF
                    self.mem.write_u32(val, res)
            elif reg == 1:    # dec r/m
                if kind == "reg":
                    res = (self.regs.get(val) - 1) & ((1 << (op_size * 8)) - 1)
                    self.regs.set(val, res)
                elif kind == "mem64":
                    res = (self.mem.read_u64(val) - 1) & 0xFFFFFFFFFFFFFFFF
                    self.mem.write_u64(val, res)
                else:
                    res = (self.mem.read_u32(val) - 1) & 0xFFFFFFFF
                    self.mem.write_u32(val, res)
            elif reg == 2:    # call near r/m (RIP-relative or indirect)
                if kind == "reg":
                    target = self.regs.get(val)
                else:
                    target = self.mem.read_u64(val)
                self._push(rm_addr + n)
                self.regs.set(15, target)
                return
            elif reg == 3:    # call far m16:64 (segment:offset) — flat mode.
                # In 64-bit flat memory model, far calls behave like near
                # calls because the CS selector is implicit.  Some Win10
                # runtimes use this form via __unwind-related helpers.
                target = self.mem.read_u64(val) if kind != "reg" else self.regs.get(val)
                self._push(rm_addr + n)
                self.regs.set(15, target)
                return
            elif reg == 4:    # jmp near r/m
                if kind == "reg":
                    target = self.regs.get(val)
                else:
                    target = self.mem.read_u64(val)
                self.regs.set(15, target)
                return
            elif reg == 5:    # jmp far m16:64 — same flat-mode simplification.
                if kind == "reg":
                    target = self.regs.get(val)
                else:
                    target = self.mem.read_u64(val)
                self.regs.set(15, target)
                return
            elif reg == 6:    # push r/m
                if kind == "reg":
                    src = self.regs.get(val)
                elif kind == "mem64":
                    src = self.mem.read_u64(val)
                else:
                    src = self.mem.read_u32(val)
                self._push(src)
            elif reg == 7:    # /7 is undefined; treat as NOP to keep
                               # going through padded sequences that some
                               # Win10 binaries emit.
                pass
            else:
                raise EmulatorDecodeError(
                    f"unsupported 0xFF /{reg} at 0x{ip-1:x}")
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x80:
            # Byte immediate group 1: /0 add, /1 or, /2 adc, /3 sbb,
            # /4 and, /5 sub, /6 xor, /7 cmp.  Operands are 8-bit.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            imm, m = self._read_imm(rm_addr + n, 1)
            sign_ext = self._signed(imm, 8)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
            else:
                tgt = self.mem.read_u8(val)
            if reg == 0:        # add
                res = (tgt + imm) & 0xFF
                self._cmp_arith(tgt, imm, res, 1)
            elif reg == 1:    # or
                res = tgt | imm
            elif reg == 2:    # adc
                res = (tgt + imm + self.regs.cf) & 0xFF
                self._cmp_arith(tgt, imm + self.regs.cf, res, 1)
            elif reg == 3:    # sbb
                res = (tgt - imm - self.regs.cf) & 0xFF
                self._cmp_arith(tgt, imm + self.regs.cf, res, 1)
            elif reg == 4:    # and
                res = tgt & imm
                self._cmp(tgt, imm, 1)
            elif reg == 5:    # sub
                res = (tgt - imm) & 0xFF
                self._cmp_arith(tgt, imm, res, 1)
            elif reg == 6:    # xor
                res = tgt ^ imm
            elif reg == 7:    # cmp
                self._cmp(tgt, imm, 1)
                res = tgt
            else:
                res = tgt
            if reg != 7:
                if kind == "reg":
                    self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
                elif kind == "mem8" or kind == "mem":
                    self.mem.write_u8(val, res & 0xFF)
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0x81:
            # /4 and, /5 sub, /6 xor, /7 cmp.  Operands are 16/32/64.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, 4)
            sign_ext = self._signed(imm, 32) if op_size == 8 else imm
            mask = (1 << (op_size * 8)) - 1
            if kind == "reg":
                tgt = self.regs.get(val)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
            elif kind == "mem32":
                tgt = self.mem.read_u32(val)
            else:
                tgt = 0
            if reg == 0:        # add
                res = (tgt + sign_ext) & mask
                self._cmp_arith(tgt, sign_ext, res, op_size)
            elif reg == 1:    # or
                res = (tgt | sign_ext) & mask
            elif reg == 2:    # adc (carry -- treat as add)
                res = (tgt + sign_ext + self.regs.cf) & mask
                self._cmp_arith(tgt, sign_ext + self.regs.cf, res, op_size)
            elif reg == 3:    # sbb (borrow -- treat as sub)
                res = (tgt - sign_ext - self.regs.cf) & mask
                self._cmp_arith(tgt, sign_ext + self.regs.cf, res, op_size)
            elif reg == 4:    # and
                res = (tgt & sign_ext) & mask
                self._cmp(tgt, sign_ext, op_size)
            elif reg == 5:    # sub
                res = (tgt - sign_ext) & mask
                self._cmp_arith(tgt, sign_ext, res, op_size)
            elif reg == 6:    # xor
                res = (tgt ^ sign_ext) & mask
            elif reg == 7:    # cmp
                self._cmp(tgt, sign_ext, op_size)
                res = tgt
            else:
                res = tgt
            if reg != 7:
                if kind == "reg":
                    self.regs.set(val, res)
                elif kind == "mem64":
                    self.mem.write_u64(val, res)
                elif kind == "mem32":
                    self.mem.write_u32(val, res)
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0x69:
            # imul r, r/m, imm32
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, 4)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            sign_src = self._signed(src, op_size * 8)
            sign_imm = self._signed(imm, 32)
            res = sign_src * sign_imm
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(op_reg, res & mask)
            self.regs.cf = 0
            self.regs.of = 0
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0x6B:
            # imul r, r/m, imm8
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, 1)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            sign_src = self._signed(src, op_size * 8)
            sign_imm = self._signed(imm, 8)
            res = sign_src * sign_imm
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(op_reg, res & mask)
            self.regs.cf = 0
            self.regs.of = 0
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0xC7:
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, 4)
            if kind == "mem64":
                self.mem.write_u64(val, self._signed(imm, 32))
            elif kind == "mem32":
                self.mem.write_u32(val, imm & 0xFFFFFFFF)
            elif kind == "mem16":
                self.mem.write_u16(val, imm & 0xFFFF)
            elif kind == "mem8":
                self.mem.write_u8(val, imm & 0xFF)
            elif kind == "reg":
                # For register operand, sign-extend imm32 to op_size.
                if op_size == 8:
                    self.regs.set(val, self._signed(imm, 32))
                else:
                    self.regs.set(val, imm & ((1 << (op_size * 8)) - 1))
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0xC6:
            # mov r/m8, imm8 (/0).  Other reg fields are illegal.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            imm, m = self._read_imm(rm_addr + n, 1)
            if kind == "mem8" or kind == "mem":
                self.mem.write_u8(val, imm & 0xFF)
            elif kind == "reg":
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | (imm & 0xFF))
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0xD0:
            # Shift group 2 by 1, 8-bit operands.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
            else:
                tgt = self.mem.read_u8(val)
            if reg == 4:        # shl
                res = (tgt << 1) & 0xFF
            elif reg == 5:    # shr
                res = (tgt >> 1) & 0xFF
            elif reg == 7:    # sar
                res = ((tgt >> 1) | (0x80 if tgt & 0x80 else 0)) & 0xFF
            else:
                res = tgt
            if kind == "reg":
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                self.mem.write_u8(val, res & 0xFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xD1:
            # Shift group 2 by 1, 16/32/64-bit operands.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            mask = (1 << (op_size * 8)) - 1
            if kind == "reg":
                tgt = self.regs.get(val)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
            else:
                tgt = self.mem.read_u32(val) if kind == "mem32" else 0
            if reg == 4:        # shl
                res = (tgt << 1) & mask
            elif reg == 5:    # shr
                res = (tgt >> 1) & mask
            elif reg == 7:    # sar
                sign_bit = 1 << (op_size * 8 - 1)
                res = ((tgt >> 1) | (sign_bit if tgt & sign_bit else 0)) & mask
            else:
                res = tgt
            if kind == "reg":
                self.regs.set(val, res)
            elif kind == "mem64":
                self.mem.write_u64(val, res)
            elif kind == "mem32":
                self.mem.write_u32(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xD2:
            # Shift group 2 by cl, 8-bit operands.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            shift = self.regs.get(REG_RCX) & 0x1F
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
            else:
                tgt = self.mem.read_u8(val)
            if reg == 4:        # shl
                res = (tgt << shift) & 0xFF
            elif reg == 5:    # shr
                res = 0 if shift >= 8 else (tgt >> shift) & 0xFF
            elif reg == 7:    # sar
                if tgt & 0x80:
                    if shift >= 8:
                        res = 0xFF
                    else:
                        res = ((tgt >> shift) | (0xFF << (8 - shift))) & 0xFF
                else:
                    res = 0 if shift >= 8 else (tgt >> shift) & 0xFF
            else:
                res = tgt
            if kind == "reg":
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                self.mem.write_u8(val, res & 0xFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xD3:
            # Shift group 2 by cl, 16/32/64-bit operands.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            shift = self.regs.get(REG_RCX) & 0x3F
            mask = (1 << (op_size * 8)) - 1
            if kind == "reg":
                tgt = self.regs.get(val)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
            else:
                tgt = self.mem.read_u32(val) if kind == "mem32" else 0
            if reg == 4:        # shl
                res = (tgt << shift) & mask
            elif reg == 5:    # shr
                res = 0 if shift >= op_size * 8 else (tgt >> shift) & mask
            elif reg == 7:    # sar
                sign_bit = 1 << (op_size * 8 - 1)
                if tgt & sign_bit:
                    if shift >= op_size * 8:
                        res = mask ^ (mask >> 1)
                    else:
                        sign_mask = ((1 << shift) - 1) << (op_size * 8 - shift)
                        res = ((tgt >> shift) | sign_mask) & mask
                else:
                    res = 0 if shift >= op_size * 8 else (tgt >> shift) & mask
            else:
                res = tgt
            if kind == "reg":
                self.regs.set(val, res)
            elif kind == "mem64":
                self.mem.write_u64(val, res)
            elif kind == "mem32":
                self.mem.write_u32(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xDB:
            # x87 FPU escape.  We don't emulate the FPU stack at all,
            # so the integer state is unchanged for any sub-opcode.
            # We do, however, advance RIP past the operand so the
            # decoder sees the next real instruction.
            _kind, _val, n = self._decode_modrm(rm_addr, mod, rm, rex_b)
            self.regs.set(15, rm_addr + n)
            return
        if op in (0xD8, 0xD9, 0xDA, 0xDC, 0xDD, 0xDE, 0xDF):
            # Other x87 FPU escapes -- same skip-without-state-change
            # pattern as 0xDB above.
            _kind, _val, n = self._decode_modrm(rm_addr, mod, rm, rex_b)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xC0:
            # Shift group 2 by imm8, byte-operand version: /0 rol,
            # /1 ror, /2 rcl, /3 rcr, /4 shl, /5 shr, /7 sar.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            imm, m = self._read_imm(rm_addr + n, 1)
            shift = imm & 0x1F
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
            else:
                tgt = self.mem.read_u8(val)
            bits = 8
            if reg == 4:        # shl
                if shift >= bits:
                    res = 0
                else:
                    res = (tgt << shift) & 0xFF
            elif reg == 5:    # shr
                res = (tgt >> shift) & 0xFF if shift < bits else 0
            elif reg == 7:    # sar
                if shift >= bits:
                    res = 0xFF if tgt & 0x80 else 0
                elif tgt & 0x80:
                    sign_mask = ((1 << shift) - 1) << (bits - shift)
                    res = ((tgt >> shift) | sign_mask) & 0xFF
                else:
                    res = (tgt >> shift) & 0xFF
            elif reg == 0:    # rol
                if shift == 0 or (shift % bits) == 0:
                    res = tgt
                else:
                    s = shift & (bits - 1)
                    res = ((tgt << s) | (tgt >> (bits - s))) & 0xFF
            elif reg == 1:    # ror
                if shift == 0 or (shift % bits) == 0:
                    res = tgt
                else:
                    s = shift & (bits - 1)
                    res = ((tgt >> s) | (tgt << (bits - s))) & 0xFF
            else:            # rcl, rcr -- identity
                res = tgt
            if kind == "reg":
                self.regs.set(val, (self.regs.get(val) & ~0xFF) | res)
            else:
                self.mem.write_u8(val, res & 0xFF)
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0xC1:
            # Shift group 2 by imm8: /0 rol, /1 ror, /2 rcl,
            # /3 rcr, /4 shl, /5 shr, /7 sar.  Operands are 16/32/64.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, 1)
            shift = imm & 0x3F
            mask = (1 << (op_size * 8)) - 1
            if kind == "reg":
                tgt = self.regs.get(val)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
            else:
                tgt = self.mem.read_u32(val) if kind == "mem32" else 0
            if reg == 4:        # shl
                res = (tgt << shift) & mask
            elif reg == 5:    # shr (logical)
                res = (tgt >> shift) & mask if shift < op_size * 8 else 0
            elif reg == 7:    # sar (arithmetic)
                # Replicate sign bit.
                sign_bit = 1 << (op_size * 8 - 1)
                if tgt & sign_bit:
                    # Negative number: arithmetic shift preserves sign.
                    sign_mask = ((1 << shift) - 1) << (op_size * 8 - shift)
                    res = ((tgt >> shift) | sign_mask) & mask
                else:
                    res = (tgt >> shift) & mask
            elif reg == 0:    # rol
                res = ((tgt << shift) | (tgt >> (op_size * 8 - shift))) & mask \
                    if shift else tgt
            elif reg == 1:    # ror
                res = ((tgt >> shift) | (tgt << (op_size * 8 - shift))) & mask \
                    if shift else tgt
            else:            # rcl, rcr -- not implemented, return tgt
                res = tgt
            if kind == "reg":
                self.regs.set(val, res)
            elif kind == "mem64":
                self.mem.write_u64(val, res)
            elif kind == "mem32":
                self.mem.write_u32(val, res)
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0xF7:
            # Group 3 (r/m, /0 test; /4 mul; /5 imul; /6 div; /7 idiv;
            # /2 not; /3 neg).  Operand size is 16/32/64.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                tgt = self.regs.get(val)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
            else:
                tgt = self.mem.read_u32(val) if kind == "mem32" else self.mem.read_u16(val)
            mask = (1 << (op_size * 8)) - 1
            if reg == 0:
                # test r/m, imm32 (sign-extended in 64-bit)
                imm, m = self._read_imm(rm_addr + n, 4)
                self._cmp(tgt, self._signed(imm, 32) if op_size == 8 else imm,
                          op_size)
                self.regs.set(15, rm_addr + n + m)
                return
            if reg == 2:
                res = (~tgt) & mask        # NOT
            elif reg == 3:
                res = (-tgt) & mask        # NEG
            elif reg == 4:
                # MUL r/m -- rax = rax * r/m, of/cf set
                res_full = (self.regs.get(0) * tgt) & ((mask << (op_size // 2)) | mask)
                self.regs.set(0, res_full & mask)
                if op_size == 8:
                    self.regs.set(REG_RDX, (res_full >> 64) & mask)
                self.regs.set(15, rm_addr + n)
                return
            else:
                # div / idiv / imul -- treat as identity
                res = tgt
            if kind == "reg":
                self.regs.set(val, res)
            elif kind == "mem64":
                self.mem.write_u64(val, res)
            elif kind == "mem32":
                self.mem.write_u32(val, res)
            elif kind == "mem16":
                self.mem.write_u16(val, res)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xF6:
            # Group 3 byte-operand version: /0 test, /2 not, /3 neg,
            # /4 mul, /5 imul, /6 div, /7 idiv.  Operand is 8-bit.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                tgt = self.regs.get(val) & 0xFF
            else:
                tgt = self.mem.read_u8(val)
            if reg == 0:        # test r/m8, imm8
                imm, m = self._read_imm(rm_addr + n, 1)
                self._cmp(tgt, imm, 1)
                self.regs.set(15, rm_addr + n + m)
                return
            if reg == 2:        # NOT
                res = (~tgt) & 0xFF
            elif reg == 3:    # NEG
                res = (-tgt) & 0xFF
            elif reg == 4:    # MUL r/m8 (AX = AL * r/m8)
                res = (self.regs.get(REG_RAX) & 0xFF) * tgt
                self.regs.set(REG_RAX,
                              (self.regs.get(REG_RAX) & ~0xFFFF) | (res & 0xFFFF))
                self.regs.set(15, rm_addr + n)
                return
            else:    # div / idiv / imul -- approximate as identity.
                res = tgt
            if kind == "reg":
                self.regs.set(val,
                              (self.regs.get(val) & ~0xFF) | (res & 0xFF))
            else:
                self.mem.write_u8(val, res & 0xFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x83:
            # /0 add r/m, imm8 /1 or r/m, imm8 /5 sub r/m, imm8 /7 cmp r/m, imm8
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, 1)
            sign_ext = self._signed(imm, 8)
            if kind == "reg":
                tgt = self.regs.get(val)
            else:
                tgt = self.mem.read_u64(val) if kind == "mem64" else self.mem.read_u32(val)
            mask = (1 << (op_size * 8)) - 1
            if reg == 0:
                res = (tgt + sign_ext) & mask
                if kind == "reg":
                    self.regs.set(val, res)
                else:
                    self.mem.write_u64(val, res)
                self._cmp_arith(tgt, sign_ext, res, op_size)
            elif reg == 1:
                res = tgt | sign_ext
                if kind == "reg":
                    self.regs.set(val, res)
                else:
                    self.mem.write_u64(val, res)
            elif reg == 5:
                res = (tgt - sign_ext) & mask
                if kind == "reg":
                    self.regs.set(val, res)
                else:
                    self.mem.write_u64(val, res)
                self._cmp_arith(tgt, sign_ext, res, op_size)
            elif reg == 7:
                self._cmp(tgt, sign_ext, op_size)
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0x63:
            # movsxd r64, r/m32 -- sign-extend 32-bit to 64-bit.
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 4)
            if kind == "reg":
                src = self.regs.get(val) & 0xFFFFFFFF
            elif kind == "mem32":
                src = self.mem.read_u32(val)
            elif kind == "mem64":
                src = self.mem.read_u32(val)        # 32-bit read
            else:
                src = 0
            self.regs.set(op_reg, self._signed(src, 32))
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x0F and not rex_w:
            # shouldn't reach here normally
            pass
        raise EmulatorDecodeError(
            f"unsupported opcode 0x{op:02x} at 0x{ip-1:x}")

    def _decode_twobyte(self, op: int, ip: int, rex: int, rex_w: int,
                          rex_r: int, rex_x: int, rex_b: int,
                          op_size: int) -> None:
        # MMX/SSE "skip" -- the legacy and SSE data-move opcodes we
        # don't model state for.  We consume their ModR/M (+ optional
        # SIB/disp) and advance RIP.  State is unchanged.
        if op in (0x6E, 0x7E, 0x6F, 0x7F, 0x10, 0x11, 0x12, 0x13, 0x14,
                  0x15, 0x16, 0x17, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D,
                  0x2E, 0x2F, 0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56,
                  0x57, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
                  0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68,
                  0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0xC2, 0xC3, 0xC4, 0xC5,
                  0xC6, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7,
                  0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF, 0xE0,
                  0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9,
                  0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF, 0xF0, 0xF1, 0xF2,
                  0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB,
                  0xFC, 0xFD, 0xFE, 0xFF):
            modrm = self.mem.read_u8(ip)
            rm_addr = ip + 1
            mod = (modrm >> 6) & 3
            rm = modrm & 7
            _kind, _val, n = self._resolve_rm(rm_addr, mod, rm, rex_b)
            self.regs.set(15, rm_addr + n)
            return
        # Conditional jumps.
        if op in (0x84, 0x85, 0x8C, 0x8E, 0x8D, 0x8F):
            disp, _ = self._read_imm(ip, 4)
            target = ip + 4 + self._signed(disp, 32)
            taken = False
            if op == 0x84:
                taken = self.regs.zf == 1
            elif op == 0x85:
                taken = self.regs.zf == 0
            elif op == 0x8D:
                taken = self.regs.sf == self.regs.of
            elif op == 0x8E:
                taken = self.regs.sf != self.regs.of
            elif op == 0x8C:
                taken = self.regs.cf == 1
            elif op == 0x8F:
                taken = self.regs.cf == 0
            if taken:
                self.regs.set(15, target)
            else:
                self.regs.set(15, ip)
            return
        if op == 0xBA:
            # bt/bts/btr/btc r/m, imm8 -- 0F BA requires a ModR/M and
            # an immediate byte.  Read them here.
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            rm_addr = ip + 1
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, 1)
            if kind == "reg":
                tgt = self.regs.get(val)
            elif kind == "mem64":
                tgt = self.mem.read_u64(val)
            else:
                tgt = self.mem.read_u32(val) if kind == "mem32" else 0
            bit = imm & 0x3F if op_size == 8 else imm & 0x1F
            self.regs.cf = (tgt >> bit) & 1
            new = tgt
            if op_reg == 5:        # bts
                new = tgt | (1 << bit)
            elif op_reg == 6:    # btr
                new = tgt & ~(1 << bit)
            elif op_reg == 7:    # btc
                new = tgt ^ (1 << bit)
            # reg == 4 -> bt (test only, no write)
            if op_reg != 4:
                mask = (1 << (op_size * 8)) - 1
                new &= mask
                if kind == "reg":
                    self.regs.set(val, new)
                elif kind == "mem64":
                    self.mem.write_u64(val, new)
                elif kind == "mem32":
                    self.mem.write_u32(val, new)
            self.regs.set(15, rm_addr + n + m)
            return
        if op == 0xA2:
            # cpuid: returns processor info into eax/ebx/ecx/edx.
            # Synthesize a generic x86-64 / AMD64 result.
            leaf = self.regs.get(REG_RAX)
            if leaf == 0:
                # Highest leaf + vendor ID.
                self.regs.set(REG_RAX, 0x00000020)
                self.regs.set(REG_RBX, 0x68747541)        # 'htuA' (Auth)
                self.regs.set(REG_RCX, 0x444D4163)        # 'DMAc' (AMD)
                self.regs.set(REG_RDX, 0x69746E65)        # 'itne' (enti)
            elif leaf == 1:
                # Family/model/stepping.
                self.regs.set(REG_RAX, 0x00680F00)        # family 6, model 15, stepping 0
                self.regs.set(REG_RBX, 0)
                self.regs.set(REG_RCX, 0)
                self.regs.set(REG_RDX, 0x078082AB)        # basic feature flags
            else:
                self.regs.set(REG_RAX, 0)
                self.regs.set(REG_RBX, 0)
                self.regs.set(REG_RCX, 0)
                self.regs.set(REG_RDX, 0)
            # cpuid reads an extra ModR/M byte in the encoded form (3-byte
            # encoding: 0F A2 ModR/M); skip it.
            self.regs.set(15, ip + 2)
            return
        if op in (0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
              0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F):
            # Long-form conditional jumps (0F 8x disp32).
            disp, _ = self._read_imm(ip, 4)
            target = ip + 4 + self._signed(disp, 32)
            taken = False
            if op == 0x80:    taken = self.regs.of == 1    # JO
            elif op == 0x81: taken = self.regs.of == 0    # JNO
            elif op == 0x82: taken = self.regs.cf == 1    # JB/JC
            elif op == 0x83: taken = self.regs.cf == 0    # JNB/JAE
            elif op == 0x84: taken = self.regs.zf == 1    # JE/JZ
            elif op == 0x85: taken = self.regs.zf == 0    # JNE/JNZ
            elif op == 0x86: taken = self.regs.cf == 1 or self.regs.zf == 1    # JBE
            elif op == 0x87: taken = self.regs.cf == 0 and self.regs.zf == 0   # JA
            elif op == 0x88: taken = self.regs.sf == 1    # JS
            elif op == 0x89: taken = self.regs.sf == 0    # JNS
            elif op == 0x8A: taken = self.regs.pf == 1    # JP/JPE
            elif op == 0x8B: taken = self.regs.pf == 0    # JNP/JPO
            elif op == 0x8C: taken = self.regs.sf != self.regs.of   # JL
            elif op == 0x8D: taken = self.regs.sf == self.regs.of   # JGE
            elif op == 0x8E: taken = self.regs.zf == 1 or self.regs.sf != self.regs.of  # JLE
            elif op == 0x8F: taken = self.regs.zf == 0 and self.regs.sf == self.regs.of  # JG
            self.regs.set(15, target if taken else ip)
            return
        if op == 0x1F:
            # Multi-byte NOP (0F 1F /0).  Parse the ModR/M (+SIB +disp)
            # and advance RIP past everything; the operands are unused.
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            rm = modrm & 7
            rm_addr = ip + 1
            _, _, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xB6:
            # movzx r, r/m8
            modrm = self.mem.read_u8(ip)
            rm_addr = ip + 1
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                src = self.regs.get(val) & 0xFF
            else:
                src = self.mem.read_u8(val)
            self.regs.set(op_reg, src)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xB7:
            modrm = self.mem.read_u8(ip)
            rm_addr = ip + 1
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 2)
            if kind == "reg":
                src = self.regs.get(val) & 0xFFFF
            else:
                src = struct.unpack("<H", self.mem.read(val, 2))[0]
            self.regs.set(op_reg, src)
            self.regs.set(15, rm_addr + n)
            return
        # CMOVcc -- conditional move.
        if 0x40 <= op <= 0x4F:
            modrm = self.mem.read_u8(ip)
            rm_addr = ip + 1
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            elif kind == "mem32":
                src = self.mem.read_u32(val)
            elif kind == "mem16":
                src = struct.unpack("<H", self.mem.read(val, 2))[0]
            elif kind == "mem8":
                src = self.mem.read_u8(val)
            else:
                src = 0
            taken = False
            low = op & 0xF
            # OF SF ZF CF are read from RFLAGS.
            if low == 0x0:    # CMOVO
                taken = self.regs.of == 1
            elif low == 0x1:  # CMOVNO
                taken = self.regs.of == 0
            elif low == 0x2:  # CMOVB / CMOVC / CMOVNAE
                taken = self.regs.cf == 1
            elif low == 0x3:  # CMOVNB / CMOVNC / CMOVAE
                taken = self.regs.cf == 0
            elif low == 0x4:  # CMOVE / CMOVZ
                taken = self.regs.zf == 1
            elif low == 0x5:  # CMOVNE / CMOVNZ
                taken = self.regs.zf == 0
            elif low == 0x6:  # CMOVBE / CMOVNA
                taken = self.regs.cf == 1 or self.regs.zf == 1
            elif low == 0x7:  # CMOVNBE / CMOVA
                taken = self.regs.cf == 0 and self.regs.zf == 0
            elif low == 0x8:  # CMOVS
                taken = self.regs.sf == 1
            elif low == 0x9:  # CMOVNS
                taken = self.regs.sf == 0
            elif low == 0xA:  # CMOVP / CMOVPE
                taken = self.regs.pf == 1
            elif low == 0xB:  # CMOVNP / CMOVPO
                taken = self.regs.pf == 0
            elif low == 0xC:  # CMOVL / CMOVNGE
                taken = self.regs.sf != self.regs.of
            elif low == 0xD:  # CMOVNL / CMOVGE
                taken = self.regs.sf == self.regs.of
            elif low == 0xE:  # CMOVLE / CMOVNG
                taken = self.regs.zf == 1 or self.regs.sf != self.regs.of
            elif low == 0xF:  # CMOVNLE / CMOVG
                taken = self.regs.zf == 0 and self.regs.sf == self.regs.of
            if taken:
                # Mask src to op_size before storing in destination.
                mask = (1 << (op_size * 8)) - 1
                self.regs.set(op_reg, src & mask)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0xAF:
            # imul r, r/m -- two-operand signed multiply.  Flags OF/CF
            # are set when the lower half is truncated; we ignore them.
            modrm = self.mem.read_u8(ip)
            rm_addr = ip + 1
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            mask = (1 << (op_size * 8)) - 1
            if op_size == 1:
                a = self._signed(self.regs.get(op_reg) & 0xFF, 8)
                b = self._signed(src & 0xFF, 8)
                res = (a * b) & mask
                self.regs.set(op_reg,
                              (self.regs.get(op_reg) & ~0xFF) | res)
            elif op_size == 2:
                a = self._signed(self.regs.get(op_reg) & 0xFFFF, 16)
                b = self._signed(src & 0xFFFF, 16)
                res = (a * b) & mask
                self.regs.set(op_reg,
                              (self.regs.get(op_reg) & ~0xFFFF) | res)
            elif op_size == 4:
                a = self._signed(self.regs.get(op_reg) & 0xFFFFFFFF, 32)
                b = self._signed(src & 0xFFFFFFFF, 32)
                res = (a * b) & mask
                self.regs.set(op_reg,
                              (self.regs.get(op_reg) & ~0xFFFFFFFF) | res)
            else:    # 8
                a = self._signed(self.regs.get(op_reg), 64)
                b = self._signed(src, 64)
                res = (a * b) & mask
                self.regs.set(op_reg, res)
            self.regs.set(15, rm_addr + n)
            return
        raise EmulatorDecodeError(
            f"unsupported 2-byte opcode 0F {op:02x} at 0x{ip-2:x}")

    # ------------------------------------------------------------------
    # Flag updates
    # ------------------------------------------------------------------

    def _cmp(self, a: int, b: int, op_size: int) -> None:
        mask = (1 << (op_size * 8)) - 1
        a &= mask
        b &= mask
        r = (a - b) & mask
        self.regs.zf = 1 if r == 0 else 0
        self.regs.sf = 1 if r & (1 << (op_size * 8 - 1)) else 0
        # Carry if borrow occurred (a < b for unsigned subtraction).
        self.regs.cf = 1 if a < b else 0

    def _cmp_arith(self, a: int, b: int, r: int, op_size: int) -> None:
        mask = (1 << (op_size * 8)) - 1
        self.regs.zf = 1 if r == 0 else 0
        self.regs.sf = 1 if r & (1 << (op_size * 8 - 1)) else 0

    # ------------------------------------------------------------------
    # Stack operations
    # ------------------------------------------------------------------

    def _push(self, value: int) -> None:
        rsp = self.regs.get(REG_RSP) - 8
        self.regs.set(REG_RSP, rsp)
        self.mem.write_u64(rsp, value & 0xFFFFFFFFFFFFFFFF)

    def _pop(self) -> int:
        rsp = self.regs.get(REG_RSP)
        value = self.mem.read_u64(rsp)
        self.regs.set(REG_RSP, rsp + 8)
        return value

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, *, max_steps: int = 100_000) -> int:
        """Run until HLT, max_steps reached, or ``stopped`` set."""
        for _ in range(max_steps):
            self.steps += 1
            try:
                self.step()
            except EmulatorHalt:
                return self.exit_code
            if self.stopped:
                return self.exit_code
        return -1


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    emu = Emulator()
    # Hand-assembled program that calls GetTickCount stub via a
    # thunk and then halts.  The thunk is installed by the test
    # caller; here we just verify the emulator runs to a hlt.
    code = (
        b"\x90"                       # nop
        b"\xB8\x2A\x00\x00\x00"        # mov eax, 0x2A
        b"\x48\x83\xC0\x05"            # add rax, 5
        b"\x3D\x2F\x00\x00\x00"        # cmp eax, 0x2F
        b"\x75\x02"                    # jne +2 (skip hlt)
        b"\xF4"                        # hlt
        b"\x90"                        # nop
    )
    emu.mem.write(emu.base, code)
    emu.regs.set(15, emu.base)
    rc = emu.run(max_steps=50)
    if rc != 0:
        return False
    if emu.regs.get(REG_RAX) != 0x2F:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
