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
    df: int = 0

    def get(self, idx: int) -> int:
        return self.r[idx] & 0xFFFFFFFFFFFFFFFF

    def set(self, idx: int, value: int) -> None:
        self.r[idx] = value & 0xFFFFFFFFFFFFFFFF

    def snapshot(self) -> Dict[str, int]:
        out = {REG_NAMES[i]: self.r[i] for i in range(16)}
        out.update({"cf": self.cf, "pf": self.pf, "zf": self.zf,
                    "sf": self.sf, "of": self.of, "df": self.df})
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
        # Block-JIT cache: ip -> compiled callable that runs the
        # block from start until a control-flow boundary.  Each entry
        # is the (function, length) tuple.  The function takes the
        # emulator's runtime state as a single dict-like argument
        # and updates the registers/memory/flags in place.
        self._block_cache: Dict[int, Tuple[Callable, int]] = {}
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
        # Win64 calling convention: first 4 integer args are in
        # RCX, RDX, R8, R9.  We capture them at thunk entry (the
        # caller's `call [IAT]` already set them) and forward to the
        # Python implementation as positional arguments.
        rcx = self.regs.get(REG_RCX)
        rdx = self.regs.get(REG_RDX)
        r8 = self.regs.get(8)        # REG_R8 -- not exported as a constant
        r9 = self.regs.get(9)        # REG_R9
        # Tolerate both ``callable_()`` (kernel32 plain functions) and
        # ``callable_(emu)`` (stubs that want the emulator).
        import inspect as _inspect
        try:
            sig = _inspect.signature(callable_)
        except (TypeError, ValueError):
            sig = None
        if sig is None:
            result = callable_()
        else:
            n_params = len(sig.parameters)
            if n_params == 0:
                result = callable_()
            elif n_params == 1:
                # ``callable_(emu)`` -- still prefer the emulator
                # over passing any of the registers.
                result = callable_(self)
            else:
                # ``callable_(rcx, rdx, r8, r9)`` -- forward the
                # caller-supplied registers.
                args = (rcx, rdx, r8, r9)[:n_params]
                result = callable_(*args)
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
        if op == 0xC8:
            # enter imm16, imm8 -- undefined in long mode; we treat
            # it as a stack-alloc + push rbp, the typical use.
            size, _ = self._read_imm(ip, 2)
            nesting, _ = self._read_imm(ip + 2, 1)
            if nesting:
                # Simplified: push rbp once.
                self._push(self.regs.get(REG_RBP))
            self.regs.set(REG_RSP,
                          (self.regs.get(REG_RSP) - size)
                          & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip + 4)
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
        if op in (0xE0, 0xE1, 0xE2, 0xE3):
            # LOOPNE/LOOPE/LOOP/JECXZ -- 32-bit-only instructions
            # (invalid in long mode).  Some Win64 binaries that are
            # compiled for IA64 and shipped in the CRT keep these as
            # relic bytes.  Skip the imm8 displacement.
            self.regs.set(15, ip + 1)
            return
        if op == 0xC4:
            # VEX 3-byte prefix (0xC4 vex1 vex2 opcode modrm...).
            # Layout: ip+0 = 0xC4, ip+1 = VEX byte 1, ip+2 = VEX
            # byte 2, ip+3 = opcode, ip+4 = ModR/M.
            modrm = self.mem.read_u8(ip + 4)
            mod = (modrm >> 6) & 3
            rm = modrm & 7
            base = 5
            if mod == 1:
                base += 1
            elif mod == 2:
                base += 4
            elif mod == 0 and rm == 4:
                base += 1    # SIB
            elif mod == 0 and rm == 5:
                base += 4    # disp32
            self.regs.set(15, ip + base)
            return
        if op == 0xC5:
            # VEX 2-byte prefix (0xC5 vex opcode modrm...).
            # Layout: ip+0 = 0xC5, ip+1 = VEX byte, ip+2 = opcode,
            # ip+3 = ModR/M.
            modrm = self.mem.read_u8(ip + 3)
            mod = (modrm >> 6) & 3
            rm = modrm & 7
            base = 4
            if mod == 1:
                base += 1
            elif mod == 2:
                base += 4
            elif mod == 0 and rm == 4:
                base += 1
            elif mod == 0 and rm == 5:
                base += 4
            self.regs.set(15, ip + base)
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
            # movsb/movsw/movsd/movsq -- copy [rsi] to [rdi] with df
            # direction.  In 64-bit mode, the operand size is 8
            # bytes (movsq).  We honour df for completeness.
            size = 1 << (2 if op == 0xA4 else 3)  # 1 / 8
            rdi = self.regs.get(REG_RDI)
            rsi = self.regs.get(REG_RSI)
            if size == 1:
                self.mem.write_u8(rdi, self.mem.read_u8(rsi))
            else:
                self.mem.write_u64(rdi, self.mem.read_u64(rsi))
            step = size
            if self.regs.df:
                step = -step
            self.regs.set(REG_RDI, (rdi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(REG_RSI, (rsi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0xAA:
            # stosb/stosq -- store AL/RAX to [rdi].  Size is 1 in
            # 64-bit mode, or 8 with REX.W.
            size = 8 if rex_w else 1
            rdi = self.regs.get(REG_RDI)
            if size == 1:
                self.mem.write_u8(rdi, self.regs.get(REG_RAX) & 0xFF)
                step = 1
            else:
                self.mem.write_u64(rdi, self.regs.get(REG_RAX))
                step = 8
            if self.regs.df:
                step = -step
            self.regs.set(REG_RDI, (rdi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0xAB:
            # stosd/stosq -- store EAX/RAX to [rdi].  Operand size
            # depends on REX.W or operand-size prefix.
            size = 8 if rex_w else 4
            rdi = self.regs.get(REG_RDI)
            if size == 8:
                self.mem.write_u64(rdi, self.regs.get(REG_RAX))
                step = 8
            else:
                self.mem.write_u32(rdi, self.regs.get(REG_RAX) & 0xFFFFFFFF)
                step = 4
            if self.regs.df:
                step = -step
            self.regs.set(REG_RDI, (rdi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0xAC:
            # lodsb/lodsq -- load [rsi] into AL/RAX.
            size = 8 if rex_w else 1
            rsi = self.regs.get(REG_RSI)
            if size == 1:
                self.regs.set(REG_RAX,
                              (self.regs.get(REG_RAX) & ~0xFF)
                              | self.mem.read_u8(rsi))
                step = 1
            else:
                self.regs.set(REG_RAX, self.mem.read_u64(rsi))
                step = 8
            if self.regs.df:
                step = -step
            self.regs.set(REG_RSI, (rsi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0xAD:
            # lodsd/lodsq -- load [rsi] into EAX/RAX.
            size = 8 if rex_w else 4
            rsi = self.regs.get(REG_RSI)
            if size == 8:
                self.regs.set(REG_RAX, self.mem.read_u64(rsi))
                step = 8
            else:
                self.regs.set(REG_RAX,
                              (self.regs.get(REG_RAX) & 0xFFFFFFFF00000000)
                              | self.mem.read_u32(rsi))
                step = 4
            if self.regs.df:
                step = -step
            self.regs.set(REG_RSI, (rsi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0xAE:
            # scasb/scasq -- compare AL/RAX with [rdi].
            size = 8 if rex_w else 1
            rdi = self.regs.get(REG_RDI)
            if size == 1:
                v = self.mem.read_u8(rdi)
                self._cmp(self.regs.get(REG_RAX) & 0xFF, v, 1)
                step = 1
            else:
                v = self.mem.read_u64(rdi)
                self._cmp(self.regs.get(REG_RAX), v, 8)
                step = 8
            if self.regs.df:
                step = -step
            self.regs.set(REG_RDI, (rdi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0xA6:
            # cmpsb -- compare [rsi] with [rdi].
            rsi = self.regs.get(REG_RSI)
            rdi = self.regs.get(REG_RDI)
            self._cmp(self.mem.read_u8(rsi), self.mem.read_u8(rdi), 1)
            step = 1
            if self.regs.df:
                step = -step
            self.regs.set(REG_RSI, (rsi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(REG_RDI, (rdi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0xA7:
            # cmpsd (compare [rsi] with [rdi], quad in 64-bit mode).
            size = 8 if rex_w else 4
            rsi = self.regs.get(REG_RSI)
            rdi = self.regs.get(REG_RDI)
            if size == 8:
                self._cmp(self.mem.read_u64(rsi),
                          self.mem.read_u64(rdi), 8)
                step = 8
            else:
                self._cmp(self.mem.read_u32(rsi),
                          self.mem.read_u32(rdi), 4)
                step = 4
            if self.regs.df:
                step = -step
            self.regs.set(REG_RSI, (rsi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(REG_RDI, (rdi + step) & 0xFFFFFFFFFFFFFFFF)
            self.regs.set(15, ip)
            return
        if op == 0x9F:  # LAHF
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
        if op == 0xF0:
            # LOCK prefix -- ignore (we are single-threaded).
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
        if op == 0x88:
            # mov r/m8, r8 (byte form)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            byte_val = self.regs.get(op_reg) & 0xFF
            if kind == "reg":
                self.regs.set(val,
                              (self.regs.get(val) & ~0xFF) | byte_val)
            else:
                self.mem.write_u8(val, byte_val)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x8A:
            # mov r8, r/m8 (byte form)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            if kind == "reg":
                src = self.regs.get(val) & 0xFF
            else:
                src = self.mem.read_u8(val)
            self.regs.set(op_reg,
                          (self.regs.get(op_reg) & ~0xFF) | src)
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
        if op == 0x21:
            # and r/m32, r32
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            src = (self.regs.get(val) if kind == "reg"
                   else self.mem.read_u64(val))
            tgt = (self.regs.get(op_reg) if kind == "reg"
                   else self.mem.read_u64(val))
            mask = (1 << (op_size * 8)) - 1
            res = tgt & src & mask
            if kind == "reg":
                self.regs.set(op_reg, res)
            elif kind == "mem64":
                self.mem.write_u64(val, res)
            else:
                self.mem.write_u32(val, res & 0xFFFFFFFF)
            self.regs.set(15, rm_addr + n)
            return
        if op == 0x26:
            # (segment prefix, handled elsewhere -- but a bare 0x26
            # reaching here means we mis-decoded; treat as NOP.)
            self.regs.set(15, ip)
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
                  0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0xAE, 0xC2, 0xC3, 0xC4,
                  0xC5, 0xC6, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6,
                  0xD7, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF,
                  0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8,
                  0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF, 0xF0, 0xF1,
                  0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA,
                  0xFB, 0xFC, 0xFD, 0xFE, 0xFF):
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
        # SETcc r/m8 (0F 90-9F)
        if 0x90 <= op <= 0x9F:
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            rm = modrm & 7
            rm_addr = ip + 1
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, 1)
            taken = self._test_cc(op - 0x90)
            byte_val = 0xFF if taken else 0x00
            if kind == "reg":
                self.regs.set(val,
                              (self.regs.get(val) & ~0xFF) | byte_val)
            else:
                self.mem.write_u8(val, byte_val)
            self.regs.set(15, rm_addr + n)
            return
        # BSF r, r/m (0F BC) and BSR r, r/m (0F BD)
        if op in (0xBC, 0xBD):
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            rm_addr = ip + 1
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            if kind == "reg":
                src = self.regs.get(val)
            elif kind == "mem64":
                src = self.mem.read_u64(val)
            else:
                src = self.mem.read_u32(val)
            self.regs.zf = 1 if src == 0 else 0
            if src != 0:
                idx = 0
                if op == 0xBC:      # bsf: lowest set bit
                    while not (src >> idx) & 1:
                        idx += 1
                else:               # bsr: highest set bit
                    idx = src.bit_length() - 1
                self.regs.set(op_reg, idx)
            self.regs.set(15, rm_addr + n)
            return
        # BSWAP r32/r64 (0F C8-CF)
        if 0xC8 <= op <= 0xCF:
            reg = (op - 0xC8) + (8 if rex_b else 0)
            v = self.regs.get(reg)
            if op_size == 8:
                b = v.to_bytes(8, "little")
                self.regs.set(reg, int.from_bytes(b, "big"))
            else:
                v32 = v & 0xFFFFFFFF
                b = v32.to_bytes(4, "little")
                self.regs.set(reg,
                              (v & ~0xFFFFFFFF)
                              | int.from_bytes(b, "big"))
            self.regs.set(15, ip)
            return
        # MOVZX r, r/m8 (0F B6) and MOVSX r, r/m8 (0F BE)
        if op in (0xB6, 0xBE, 0xB7, 0xBF):
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            rm_addr = ip + 1
            src_size = 1 if op in (0xB6, 0xBE) else 2
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b,
                                            src_size)
            if kind == "reg":
                src = self.regs.get(val) & ((1 << (src_size * 8)) - 1)
            elif src_size == 1:
                src = self.mem.read_u8(val)
            else:
                src = self.mem.read_u16(val)
            if op in (0xBE, 0xBF):      # sign-extend
                src = self._signed(src, src_size * 8) & (
                    (1 << (op_size * 8)) - 1)
            mask = (1 << (op_size * 8)) - 1
            self.regs.set(op_reg, src & mask)
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

    def _test_cc(self, low: int) -> bool:
        """Evaluate condition-code ``low`` (0x0-0xF) against flags.

        The mapping matches both the short (0x70-0x7F), long
        (0x0F 0x80-0x8F), SETcc (0x0F 0x90-0x9F) and CMOVcc
        (0x0F 0x40-0x4F) opcode families.
        """
        return (
            (low == 0x0 and self.regs.of == 1)
            or (low == 0x1 and self.regs.of == 0)
            or (low == 0x2 and self.regs.cf == 1)
            or (low == 0x3 and self.regs.cf == 0)
            or (low == 0x4 and self.regs.zf == 1)
            or (low == 0x5 and self.regs.zf == 0)
            or (low == 0x6 and (self.regs.cf == 1 or self.regs.zf == 1))
            or (low == 0x7 and self.regs.cf == 0 and self.regs.zf == 0)
            or (low == 0x8 and self.regs.sf == 1)
            or (low == 0x9 and self.regs.sf == 0)
            or (low == 0xA and self.regs.pf == 1)
            or (low == 0xB and self.regs.pf == 0)
            or (low == 0xC and self.regs.sf != self.regs.of)
            or (low == 0xD and self.regs.sf == self.regs.of)
            or (low == 0xE and (self.regs.zf == 1
                                or self.regs.sf != self.regs.of))
            or (low == 0xF and self.regs.zf == 0
                and self.regs.sf == self.regs.of)
        )

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
    # Basic-block JIT
    # ------------------------------------------------------------------
    #
    # The interpreter above dispatches one instruction at a time
    # through a giant if-elif chain.  For tight loops (e.g. memcpy)
    # this is dominated by Python function-call overhead.  The
    # block JIT instead decodes a *basic block* (a run of
    # instructions ending in a control-flow boundary) once, emits
    # the corresponding Python source, and ``exec()``s it.  CPython
    # then compiles that source to bytecode which runs at near-native
    # Python speed -- typically 5-20x faster than the dispatch loop.
    #
    # The compiled function takes no arguments and operates on the
    # emulator's runtime state through a single ``s`` dict that
    # carries references to the register list, flag scalars, and a
    # bytearray view of memory.  This minimises attribute lookups.

    _JIT_REGS = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
                 "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15")

    def _jit_state(self) -> Dict[str, Any]:
        """Return a dict that the JIT'd code uses for state."""
        return {
            "r": self.regs.r,
            "cf": self.regs.cf,
            "zf": self.regs.zf,
            "sf": self.regs.sf,
            "of": self.regs.of,
            "pf": self.regs.pf,
            "df": self.regs.df,
            # Memory: each Memory instance exposes ``_pages`` (a
            # dict of page-aligned bytearray pages).  JIT'd code
            # reads/writes through the small helpers below.
        }

    @staticmethod
    def _jit_load_u8(state: Dict[str, Any], addr: int) -> int:
        page = addr & ~0xFFF
        p = state["pages"].get(page)
        if p is None:
            return 0
        return p[addr & 0xFFF]

    @staticmethod
    def _jit_store_u8(state: Dict[str, Any], addr: int, val: int) -> None:
        page = addr & ~0xFFF
        p = state["pages"].get(page)
        if p is None:
            return
        p[addr & 0xFFF] = val & 0xFF

    @staticmethod
    def _jit_load_u32(state: Dict[str, Any], addr: int) -> int:
        page = addr & ~0xFFF
        p = state["pages"].get(page)
        if p is None:
            return 0
        o = addr & 0xFFF
        if o <= 0xFFC:
            return (p[o]
                    | (p[o + 1] << 8)
                    | (p[o + 2] << 16)
                    | (p[o + 3] << 24))
        return (state["_l"](state, addr)
                | (state["_l"](state, addr + 1) << 8)
                | (state["_l"](state, addr + 2) << 16)
                | (state["_l"](state, addr + 3) << 24))

    @staticmethod
    def _jit_store_u32(state: Dict[str, Any], addr: int, val: int) -> None:
        page = addr & ~0xFFF
        p = state["pages"].get(page)
        if p is None:
            return
        o = addr & 0xFFF
        if o <= 0xFCF:
            p[o] = val & 0xFF
            p[o + 1] = (val >> 8) & 0xFF
            p[o + 2] = (val >> 16) & 0xFF
            p[o + 3] = (val >> 24) & 0xFF
            return
        state["_s"](state, addr, val & 0xFF)
        state["_s"](state, addr + 1, (val >> 8) & 0xFF)
        state["_s"](state, addr + 2, (val >> 16) & 0xFF)
        state["_s"](state, addr + 3, (val >> 24) & 0xFF)

    @staticmethod
    def _jit_load_u64(state: Dict[str, Any], addr: int) -> int:
        return (state["_l32"](state, addr)
                | (state["_l32"](state, addr + 4) << 32))

    @staticmethod
    def _jit_store_u64(state: Dict[str, Any], addr: int, val: int) -> None:
        state["_s32"](state, addr, val & 0xFFFFFFFF)
        state["_s32"](state, addr + 4, (val >> 32) & 0xFFFFFFFF)

    def _build_jit_state(self) -> Dict[str, Any]:
        """Build the state dict used by the JIT'd functions.

        Includes the register list, flag scalars, memory pages, and
        fast load/store helpers (so the JIT code does not have to
        re-resolve attribute lookups at runtime).
        """
        s = self._jit_state()
        s["pages"] = self.mem._pages
        s["_l"] = self._jit_load_u8
        s["_s"] = self._jit_store_u8
        s["_l32"] = self._jit_load_u32
        s["_s32"] = self._jit_store_u32
        s["_l64"] = self._jit_load_u64
        s["_s64"] = self._jit_store_u64
        return s

    def _emit_block(self, ip: int) -> Optional[Tuple[Callable, int]]:
        """Decode a basic block starting at ``ip`` and return a
        compiled function that runs the block plus the byte length.

        Returns ``None`` if the block contains an opcode we don't
        know how to JIT; the caller will then fall back to the
        per-instruction interpreter.
        """
        # Header for the generated function.  We read all register
        # values into local variables at entry, all flags into
        # locals, and the memory helpers are bound by name.  At
        # exit we write locals back to ``s["r"]`` / ``s["cf"]``
        # etc. and return the new RIP.  Locals are dramatically
        # faster than dict lookups in CPython.
        body: List[str] = []
        block_start = ip
        max_block_bytes = 4096
        # How many x86 instructions we allow in a single block.
        max_insns = 256
        insns = 0
        # Track which REX was last seen (only meaningful for the
        # 0F escape and for the 40-4F prefix loop).
        last_op_size = 4
        last_rex_w = False
        while ip - block_start < max_block_bytes and insns < max_insns:
            start_ip = ip
            b0 = self.mem.read_u8(ip)
            # REX prefix loop
            rex = 0
            while 0x40 <= b0 <= 0x4F:
                rex = b0 - 0x40
                ip += 1
                b0 = self.mem.read_u8(ip)
            rex_w = bool(rex & 0x8)
            rex_r = (rex & 0x4) << 1
            rex_x = (rex & 0x2) << 2
            rex_b = bool(rex & 0x1)
            op_size = 8 if rex_w else 4
            last_op_size = op_size
            last_rex_w = rex_w

            # Two-byte opcode escape
            if b0 == 0x0F:
                b1 = self.mem.read_u8(ip + 1)
                ip += 2
                result = self._emit_twobyte(b1, ip, rex, rex_w, rex_r, rex_x, rex_b, op_size, body)
                if result is None:
                    # Can't compile -- emit a fallback marker and
                    # return.  The caller will run the fallback for
                    # the uncompiled prefix.
                    return None
                ip, terminated = result
                insns += 1
                if terminated:
                    return self._compile_block(block_start, body, ip - block_start)
                continue

            # Operand-size / address-size / segment override / REP
            # / LOCK prefixes.  LOCK has no effect in our single-
            # threaded emulator so we ignore it.
            if b0 in (0x66, 0x67, 0xF0, 0xF2, 0xF3, 0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65):
                ip += 1
                b0 = self.mem.read_u8(ip)
                # Re-check REX after prefix
                rex = 0
                while 0x40 <= b0 <= 0x4F:
                    rex = b0 - 0x40
                    ip += 1
                    b0 = self.mem.read_u8(ip)
                rex_w = bool(rex & 0x8)
                rex_r = (rex & 0x4) << 1
                rex_x = (rex & 0x2) << 2
                rex_b = bool(rex & 0x1)
                op_size = 8 if rex_w else 4

            # Hand the one-byte opcode to the dedicated emitter.
            ip += 1
            try:
                result = self._emit_onebyte(
                    b0, ip, rex, rex_w, rex_r, rex_x, rex_b, op_size, body)
            except NotImplementedError:
                result = None
            if result is None:
                # Unknown opcode.  Discard any partially emitted body
                # and let the caller fall back to step() at block_start.
                return None
            ip, terminated = result
            insns += 1
            if terminated:
                length = ip - block_start
                if not self._validate_block(block_start, length):
                    log.debug(
                        "jit: rejecting block 0x%x (len %d) -- "
                        "interpreter disagrees on length",
                        block_start, length)
                    return None
                return self._compile_block(block_start, body, length)
        # Hit the max_insns / max_block_bytes guard without reaching a
        # control-flow instruction.  We deliberately refuse to JIT this:
        # a truncated block would leave r[15] pointing at whatever the
        # last emitted instruction happened to set, which desyncs the
        # decoder.  The interpreter handles it one instruction at a time.
        return None

    def _validate_block(self, start: int, length: int) -> bool:
        """Cross-check a JIT block's decoded length against an
        independent instruction-length walk.

        The JIT emitter computes instruction sizes on its own, separate
        from ``step()``.  Any disagreement (a wrong ModR/M length, a
        missed prefix, a bad RIP-relative displacement) would desync the
        decoder and eventually run off into garbage.

        We deliberately do **not** execute the instructions here: that
        would fire Win32 thunks and mutate memory as a side effect of
        "validating".  Instead we walk the byte stream computing only
        instruction lengths, using the same ModR/M/SIB rules the
        interpreter uses but without touching any state.
        """
        ip = start
        end = start + length
        guard = 0
        while ip < end:
            nxt = self._instruction_length(ip)
            if nxt is None or nxt <= ip:
                return False
            ip = nxt
            guard += 1
            if guard > 1024:
                return False
        return ip == end

    def _instruction_length(self, ip: int) -> Optional[int]:
        """Return the address of the instruction after the one at
        ``ip``, or ``None`` if the length can't be determined.

        This is a pure read of the byte stream -- no register or memory
        writes, no thunk dispatch.
        """
        b0 = self.mem.read_u8(ip)
        while 0x40 <= b0 <= 0x4F:      # REX prefixes
            ip += 1
            b0 = self.mem.read_u8(ip)
        if b0 in (0x66, 0x67, 0xF0, 0xF2, 0xF3,
                  0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65):
            ip += 1
            b0 = self.mem.read_u8(ip)
            while 0x40 <= b0 <= 0x4F:
                ip += 1
                b0 = self.mem.read_u8(ip)
        ip += 1                        # opcode byte

        # Opcodes with no ModR/M and no immediate.
        no_modrm = {
            0x04, 0x05, 0x0C, 0x0D, 0x14, 0x15, 0x1C, 0x1D, 0x24, 0x25,
            0x2C, 0x2D, 0x34, 0x35, 0x3C, 0x3D,
            0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
            0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F,
            0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57,
            0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
            0x60, 0x61, 0x63, 0x90, 0x91, 0x98, 0x99, 0x9C, 0x9D,
            0x9E, 0x9F, 0xA4, 0xA5, 0xA6, 0xA7, 0xAA, 0xAB,
            0xAC, 0xAD, 0xAE, 0xAF,
            0xC2, 0xC3, 0xC9, 0xCA, 0xCC, 0xCD, 0xD7,
            0xE8, 0xE9, 0xEA, 0xEB, 0xF4, 0xF5, 0xF8, 0xF9,
            0xFA, 0xFB, 0xFC, 0xFD,
        }
        # ModR/M + imm8/imm16/imm32/imm64.
        modrm_imm8 = {
            0x80, 0x82, 0x83, 0xC0, 0xC1, 0xC6,
            0x6A, 0x6B, 0xA8, 0xA9, 0xB0, 0xB1, 0xB2, 0xB3, 0xB4,
            0xB5, 0xB6, 0xB7, 0xC8, 0xE0, 0xE1, 0xE2, 0xE3,
            0xE4, 0xE5, 0xE6, 0xE7, 0xD4, 0xD5,
        }
        modrm_imm16 = {0xC2,}
        modrm_imm32 = {0x81, 0xA1, 0xA2, 0xA3, 0xC2}
        modrm_rel32 = {0x0F80, 0x0F81, 0x0F82, 0x0F83, 0x0F84, 0x0F85,
                       0x0F86, 0x0F87, 0x0F88, 0x0F89, 0x0F8A, 0x0F8B,
                       0x0F8C, 0x0F8D, 0x0F8E, 0x0F8F}

        if b0 == 0x0F:
            b1 = self.mem.read_u8(ip)
            ip += 1
            two = 0x0F00 | b1
            if two in modrm_rel32:
                modrm = self.mem.read_u8(ip)
                ip += 1 + self._modrm_tail(ip, modrm)
                return ip + 4
            # All other 0F opcodes we're willing to reason about take a
            # ModR/M and nothing else.
            modrm = self.mem.read_u8(ip)
            ip += 1 + self._modrm_tail(ip, modrm)
            return ip
        if b0 in no_modrm:
            return ip
        if 0x70 <= b0 <= 0x7F:         # Jcc rel8
            return ip + 1
        if b0 in modrm_imm8:
            modrm = self.mem.read_u8(ip)
            ip += 1 + self._modrm_tail(ip, modrm)
            return ip + 1
        if b0 in modrm_imm16:
            modrm = self.mem.read_u8(ip)
            ip += 1 + self._modrm_tail(ip, modrm)
            return ip + 2
        if b0 in modrm_imm32:
            modrm = self.mem.read_u8(ip)
            ip += 1 + self._modrm_tail(ip, modrm)
            return ip + 4
        if 0xB8 <= b0 <= 0xBF:         # mov r, imm32/imm64
            rex = self.mem.read_u8(ip - 1)
            return ip + (8 if (rex & 0x8) else 4)
        if 0x50 <= b0 <= 0x5F:
            return ip
        if b0 in (0x6C, 0x6D, 0x6E, 0x6F):
            return ip
        if 0x70 <= b0 <= 0x7F:
            return ip + 1
        # Generic ModR/M opcode.
        modrm = self.mem.read_u8(ip)
        ip += 1 + self._modrm_tail(ip, modrm)
        return ip

    @staticmethod
    def _modrm_tail(ip: int, modrm: int) -> int:
        """Return the byte length of the SIB + displacement that
        follows a ModR/M byte, *without* reading memory.

        ``ip`` is the address just past the ModR/M byte.
        """
        mod = (modrm >> 6) & 3
        rm = modrm & 7
        if mod == 0:
            if rm == 5:
                return 4             # disp32
            if rm == 4:
                return 1             # SIB
            return 0
        if mod == 1:
            if rm == 4:
                return 2             # SIB + disp8
            return 1                 # disp8
        return 5 if rm == 4 else 4   # SIB + disp32, or disp32

    def _compile_block(self, start: int, body: List[str], length: int
                        ) -> Tuple[Callable, int]:
        """Build a Python function from a list of source lines and
        compile + cache it."""
        src = (
            "def _block(s, _push, _pop, _l, _s, _l32, _s32, _l64, _s64):\n"
            "    r = s['r']\n"
            "    cf = s['cf']\n"
            "    zf = s['zf']\n"
            "    sf = s['sf']\n"
            "    of = s['of']\n"
            "    pf = s['pf']\n"
            "    df = s['df']\n"
            + "\n".join(body)
            + "\n    s['cf'] = cf\n"
            + "    s['zf'] = zf\n"
            + "    s['sf'] = sf\n"
            + "    s['of'] = of\n"
            + "    s['pf'] = pf\n"
            + "    s['df'] = df\n"
            + "    return r[15]\n"
        )
        ns: Dict[str, Any] = {
            "_push": self._jit_push,
            "_pop": self._jit_pop,
            "_l": self._jit_load_u8,
            "_s": self._jit_store_u8,
            "_l32": self._jit_load_u32,
            "_s32": self._jit_store_u32,
            "_l64": self._jit_load_u64,
            "_s64": self._jit_store_u64,
        }
        code = compile(src, f"<block-0x{start:x}>", "exec")
        exec(code, ns)
        return ns["_block"], length

    def _emit_onebyte(self, op: int, ip: int, rex: int, rex_w: int,
                      rex_r: int, rex_x: int, rex_b: int,
                      op_size: int, body: List[str]
                      ) -> Optional[Tuple[int, bool]]:
        """Append Python source lines for one x86 one-byte instruction
        to ``body``.  Returns ``(new_ip, terminated)`` or ``None`` if
        the opcode cannot be compiled in the JIT.
        """
        r = "r"
        # nop
        if op == 0x90:
            return (ip, False)
        # mov r, imm (B8-BF)
        if 0xB8 <= op <= 0xBF:
            reg = (op - 0xB8) + (8 if rex_b else 0)
            n = op_size
            imm, _ = self._read_imm(ip, n)
            body.append(f"    {r}[{reg}] = {imm}")
            return (ip + n, False)
        # mov r8, imm8 (B0-B7)
        if 0xB0 <= op <= 0xB7:
            reg = (op - 0xB0) + (8 if rex_b else 0)
            imm, _ = self._read_imm(ip, 1)
            if reg < 8:
                body.append(f"    {r}[{reg}] = ({r}[{reg}] & ~0xFF) | {imm}")
            else:
                body.append(f"    {r}[{reg}] = {imm}")
            return (ip + 1, False)
        # push reg (50-57)
        if 0x50 <= op <= 0x57:
            reg = (op - 0x50) + (8 if rex_b else 0)
            body.append(f"    _push(r, s, {r}[{reg}])")
            return (ip, False)
        # pop reg (58-5F)
        if 0x58 <= op <= 0x5F:
            reg = (op - 0x58) + (8 if rex_b else 0)
            body.append(f"    {r}[{reg}] = _pop(r, s)")
            return (ip, False)
        # ret
        if op == 0xC3:
            body.append("    r[15] = _pop(r, s)")
            return (ip, True)
        # ret imm16
        if op == 0xC2:
            imm, _ = self._read_imm(ip, 2)
            body.append(f"    r[15] = _pop(r, s)")
            body.append(f"    r[4] = (r[4] + {imm}) & 0xFFFFFFFFFFFFFFFF")
            return (ip + 2, True)
        # jmp rel32
        if op == 0xE9:
            disp, _ = self._read_imm(ip, 4)
            target = (ip + 4) + self._signed(disp, 32)
            body.append(f"    r[15] = {target}")
            return (ip + 4, True)
        # jmp rel8
        if op == 0xEB:
            disp, _ = self._read_imm(ip, 1)
            target = (ip + 1) + self._signed(disp, 8)
            body.append(f"    r[15] = {target}")
            return (ip + 1, True)
        # call rel32
        if op == 0xE8:
            disp, _ = self._read_imm(ip, 4)
            target = (ip + 4) + self._signed(disp, 32)
            body.append(f"    _push(r, s, {ip + 4})")
            body.append(f"    r[15] = {target}")
            return (ip + 4, True)
        # short conditional jump
        if 0x70 <= op <= 0x7F:
            disp, _ = self._read_imm(ip, 1)
            target = (ip + 1) + self._signed(disp, 8)
            cond = self._cond_expr(op)
            body.append(f"    if {cond}:")
            body.append(f"        r[15] = {target}")
            body.append("    else:")
            body.append(f"        r[15] = {ip + 1}")
            return (ip + 1, True)
        # ---- Group with ModR/M (memory / register) ----
        # Try a generic ModR/M emitter for the common ALU / data-move
        # opcodes.  We bail out (return None) for SIB / RIP-relative /
        # non-register r/m cases so the caller falls back to the
        # per-instruction interpreter.
        if op in (0x89, 0x8B, 0x01, 0x03, 0x09, 0x0B, 0x21, 0x23,
                  0x29, 0x2B, 0x31, 0x33, 0x39, 0x3B, 0x85, 0x84,
                  0x86, 0x87, 0x8D, 0x88, 0x8A):
            return self._emit_modrm_op(
                op, ip, rex, rex_w, rex_r, rex_x, rex_b, op_size, body)
        # sub/add r/m, imm32 (81 /0..7)
        if op == 0x81:
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            if mod == 3 and op_size == 8 and reg in (0, 5):
                # add r64, imm32 (sign-extended)  or  sub r64, imm32
                target_reg = (rm + (8 if rex_b else 0)) & 0xF
                imm, _ = self._read_imm(ip + 1, 4)
                se = self._signed(imm, 32)
                if reg == 0:
                    body.append(f"    {r}[{target_reg}] = ({r}[{target_reg}] + {se}) & 0xFFFFFFFFFFFFFFFF")
                else:
                    body.append(f"    {r}[{target_reg}] = ({r}[{target_reg}] - {se}) & 0xFFFFFFFFFFFFFFFF")
                return (ip + 5, False)
            # ModR/M forms with /4 (and), /6 (xor), /7 (cmp) and
            # 32-bit /0, /1, /5 are not JIT'd yet.
            return None
        # sub/add/and/or/xor r/m64, imm8 (REX.W 83 /0, /4, /5, etc.)
        if op == 0x83:
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            if mod == 3 and op_size == 8 and reg in (0, 5):
                target_reg = (rm + (8 if rex_b else 0)) & 0xF
                imm, _ = self._read_imm(ip + 1, 1)
                se = self._signed(imm, 8)
                if reg == 0:
                    body.append(f"    {r}[{target_reg}] = ({r}[{target_reg}] + {se}) & 0xFFFFFFFFFFFFFFFF")
                else:
                    body.append(f"    {r}[{target_reg}] = ({r}[{target_reg}] - {se}) & 0xFFFFFFFFFFFFFFFF")
                return (ip + 2, False)
            return None
        # sub rsp, imm / add rsp, imm (48 81 /4 /0 etc.)
        # We handle the immediate forms 81 /0..7, 83 /0..7, 8D (lea)
        # below as needed.
        # Fall back: we don't JIT this opcode.
        return None

    def _emit_twobyte(self, op: int, ip: int, rex: int, rex_w: bool,
                      rex_r: int, rex_x: int, rex_b: bool,
                      op_size: int, body: List[str]
                      ) -> Optional[Tuple[int, bool]]:
        """Append Python source for a 0F-prefixed instruction."""
        # Long-form conditional jumps (0F 80-8F)
        if 0x80 <= op <= 0x8F:
            disp, _ = self._read_imm(ip, 4)
            target = (ip + 4) + self._signed(disp, 32)
            cond = self._cond_expr(0x80 + (op - 0x80) + 0x10)  # remap
            body.append(f"    if {cond}:")
            body.append(f"        r[15] = {target}")
            body.append("    else:")
            body.append(f"        r[15] = {ip + 4}")
            return (ip + 4, True)
        # CMOVcc r, r/m (0F 40-4F)
        if 0x40 <= op <= 0x4F:
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
            target_reg = (rm + (8 if rex_b else 0)) & 0xF
            if mod == 3:
                mask = (1 << (op_size * 8)) - 1
                cond = self._cond_expr(op - 0x40)
                body.append(f"    if {cond}:")
                body.append(
                    f"        r[{op_reg}] = r[{target_reg}] & {mask}")
                return (ip + 1, False)
            return None
        # SETcc r/m8 (0F 90-9F)
        if 0x90 <= op <= 0x9F:
            modrm = self.mem.read_u8(ip)
            mod = (modrm >> 6) & 3
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            target_reg = (rm + (8 if rex_b else 0)) & 0xF
            cond = self._cond_expr(op - 0x90)
            if mod == 3:
                body.append(f"    if {cond}:")
                body.append(f"        r[{target_reg}] |= 0xFF")
                body.append("    else:")
                body.append(f"        r[{target_reg}] &= ~0xFF")
                body.append(f"    r[{target_reg}] &= 0xFFFFFFFFFFFFFFFF")
                return (ip + 1, False)
            return None
        # BSF / BSR (0F BC / 0F BD) and BSWAP (0F C8-CF)
        if op in (0xBC, 0xBD, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE,
                  0xCF):
            return None
        return None

    def _emit_modrm_op(self, op: int, ip: int, rex: int, rex_w: int,
                        rex_r: int, rex_x: int, rex_b: int,
                        op_size: int, body: List[str]
                        ) -> Optional[Tuple[int, bool]]:
        """Common ModR/M emitter for the most-used opcodes.

        Supports only the register/register and register/[rsp+disp8]
        / [rsp+disp32] / [rbp+disp8] addressing modes.  Anything with
        SIB, RIP-relative, or non-rsp/rbp base registers bails out
        (``return None``) so the per-instruction interpreter takes
        over.
        """
        modrm = self.mem.read_u8(ip)
        mod = (modrm >> 6) & 3
        reg = (modrm >> 3) & 7
        rm = modrm & 7
        op_reg = (reg + rex_r) & 0xF if (rex & 0x4) else reg
        target_reg = (rm + (8 if rex_b else 0)) & 0xF

        # Determine operand size in bytes.
        size = 8 if op_size == 8 else 4
        if op in (0x84, 0x86, 0xA8):    # byte-form test/xchg
            size = 1

        # reg-reg form (mod=3)
        if mod == 3:
            self._emit_alu_reg_reg(
                op, op_size, op_reg, target_reg, size, body)
            return (ip + 1, False)

        # Memory form.  We compute the effective address as a Python
        # expression and the number of bytes the whole instruction
        # occupies (modrm + sib + disp).  RIP-relative (mod=0, rm=5)
        # is resolved at *emit* time against the end of this
        # instruction, which is why we need nbytes first.
        #
        # Only simple SIB (base=rsp/rbp, no index) is supported;
        # anything else bails out to the interpreter.
        disp = 0
        have_disp = False
        nbytes = 1                      # modrm byte
        if mod == 0:
            if rm == 5:
                # RIP-relative: addr = next_insn_ip + disp32.
                disp = self._signed(self.mem.read_u32(ip + 1), 32)
                have_disp = True
                nbytes += 4
            elif rm == 4:
                sib = self.mem.read_u8(ip + 1)
                if sib != 0x24:
                    return None        # indexed SIB
                nbytes += 1            # the SIB byte itself
            else:
                pass                    # [reg], no extra bytes
        elif mod == 1:
            if rm == 4:
                sib = self.mem.read_u8(ip + 1)
                if sib != 0x24:
                    return None
                nbytes += 1
                disp = self._signed(self.mem.read_u8(ip + 2), 8)
                have_disp = True
            else:
                disp = self._signed(self.mem.read_u8(ip + 1), 8)
                have_disp = True
            nbytes += 1
        elif mod == 2:
            if rm == 4:
                sib = self.mem.read_u8(ip + 1)
                if sib != 0x24:
                    return None
                nbytes += 1
                disp = self._signed(self.mem.read_u32(ip + 2), 32)
                have_disp = True
                nbytes += 4
            else:
                disp = self._signed(self.mem.read_u32(ip + 1), 32)
                have_disp = True
                nbytes += 4
        else:
            return None

        # Build the address expression now that nbytes is known.
        end_ip = ip + nbytes
        if mod == 0 and rm == 5:
            # RIP-relative, resolved statically at emit time.
            addr_expr = f"0x{(end_ip + disp) & 0xFFFFFFFFFFFFFFFF:x}"
        elif rm == 4:
            base = "r[4]"              # rsp (SIB base with rex_b=0)
            addr_expr = (f"({base} + {disp})" if have_disp else base)
        elif mod == 0:
            base_reg = target_reg
            addr_expr = f"r[{base_reg}]"
        else:
            base_reg = (rm + (8 if rex_b else 0)) & 0xF
            addr_expr = (f"(r[{base_reg}] + {disp})" if have_disp
                         else f"r[{base_reg}]")

        if size == 8:
            load_fn = "_l64"
            store_fn = "_s64"
        elif size == 4:
            load_fn = "_l32"
            store_fn = "_s32"
        else:
            load_fn = "_l"
            store_fn = "_s"

        self._emit_alu_mem(
            op, op_size, op_reg, addr_expr, load_fn, store_fn, size, body)
        return (ip + nbytes, False)

    def _emit_alu_reg_reg(self, op: int, op_size: int,
                          dst: int, src: int, size: int,
                          body: List[str]) -> None:
        """Emit a reg,reg ALU op."""
        r = "r"
        mask = (1 << (op_size * 8)) - 1
        if op == 0x89:    # mov r/m, r -- reg,reg form
            body.append(f"    {r}[{dst}] = {r}[{src}] & 0xFFFFFFFFFFFFFFFF")
            return
        if op == 0x88:    # mov r/m8, r8 -- byte form
            body.append(f"    {r}[{dst}] = ({r}[{dst}] & ~0xFF) | ({r}[{src}] & 0xFF)")
            return
        if op == 0x8B:    # mov r, r/m -- reg,reg form
            body.append(f"    {r}[{dst}] = {r}[{src}] & 0xFFFFFFFFFFFFFFFF")
            return
        if op == 0x8A:    # mov r8, r/m8 -- byte form
            body.append(f"    {r}[{dst}] = ({r}[{dst}] & ~0xFF) | ({r}[{src}] & 0xFF)")
            return
        if op == 0x01:    # add r/m, r
            body.append(
                f"    {r}[{dst}] = ({r}[{dst}] + {r}[{src}]) & {mask}")
            return
        if op == 0x03:    # add r, r/m
            body.append(
                f"    {r}[{dst}] = ({r}[{dst}] + {r}[{src}]) & {mask}")
            return
        if op == 0x29:    # sub r/m, r
            body.append(
                f"    {r}[{dst}] = ({r}[{dst}] - {r}[{src}]) & {mask}")
            return
        if op == 0x2B:    # sub r, r/m
            body.append(
                f"    {r}[{dst}] = ({r}[{dst}] - {r}[{src}]) & {mask}")
            return
        if op == 0x09:    # or r/m, r
            body.append(f"    {r}[{dst}] = ({r}[{dst}] | {r}[{src}]) & {mask}")
            return
        if op == 0x0B:    # or r, r/m
            body.append(f"    {r}[{dst}] = ({r}[{dst}] | {r}[{src}]) & {mask}")
            return
        if op == 0x21:    # and r/m, r
            body.append(f"    {r}[{dst}] = ({r}[{dst}] & {r}[{src}]) & {mask}")
            return
        if op == 0x23:    # and r, r/m
            body.append(f"    {r}[{dst}] = ({r}[{dst}] & {r}[{src}]) & {mask}")
            return
        if op == 0x31:    # xor r/m, r
            body.append(f"    {r}[{dst}] = ({r}[{dst}] ^ {r}[{src}]) & {mask}")
            return
        if op == 0x33:    # xor r, r/m
            body.append(f"    {r}[{dst}] = ({r}[{dst}] ^ {r}[{src}]) & {mask}")
            return
        if op == 0x39:    # cmp r/m, r
            a = f"({r}[{dst}] & {mask})"
            b = f"({r}[{src}] & {mask})"
            body.append(f"    cf = 1 if {a} < {b} else 0")
            body.append(f"    zf = 1 if {a} == {b} else 0")
            return
        if op == 0x3B:    # cmp r, r/m
            a = f"({r}[{dst}] & {mask})"
            b = f"({r}[{src}] & {mask})"
            body.append(f"    cf = 1 if {a} < {b} else 0")
            body.append(f"    zf = 1 if {a} == {b} else 0")
            return
        if op == 0x85:    # test r, r/m
            a = f"({r}[{dst}] & {mask})"
            b = f"({r}[{src}] & {mask})"
            body.append(f"    cf = 0")
            body.append(f"    zf = 1 if ({a} & {b}) == 0 else 0")
            return
        if op == 0x87:    # xchg r, r/m
            body.append(
                f"    _t = {r}[{dst}]; {r}[{dst}] = {r}[{src}]; "
                f"{r}[{src}] = _t")
            return
        raise NotImplementedError(f"unsupported ALU reg,reg 0x{op:02x}")
        # NOTE: _emit_block() catches NotImplementedError and falls back
        # to the per-instruction interpreter for this block, so raising
        # here is the correct "I don't know this opcode" signal.

    def _emit_alu_mem(self, op: int, op_size: int, dst_reg: int,
                      addr_expr: str, load_fn: str, store_fn: str,
                      size: int, body: List[str]) -> None:
        """Emit an r/m (memory),r ALU op."""
        r = "r"
        mask = (1 << (op_size * 8)) - 1
        # mov [m], r (89)
        if op == 0x89:
            body.append(
                f"    {store_fn}(s, {addr_expr}, {r}[{dst_reg}])")
            return
        # mov [m]8, r8 (88) -- byte store
        if op == 0x88:
            body.append(
                f"    {store_fn}(s, {addr_expr}, {r}[{dst_reg}] & 0xFF)")
            return
        # mov r, [m] (8B)
        if op == 0x8B:
            body.append(
                f"    {r}[{dst_reg}] = {load_fn}(s, {addr_expr})")
            return
        # mov r8, [m]8 (8A) -- byte load
        if op == 0x8A:
            body.append(
                f"    {r}[{dst_reg}] = ({r}[{dst_reg}] & ~0xFF) | "
                f"({load_fn}(s, {addr_expr}) & 0xFF)")
            return
        # lea (8D): dst_reg = address itself, no memory access
        if op == 0x8D:
            body.append(
                f"    {r}[{dst_reg}] = {addr_expr} & 0xFFFFFFFFFFFFFFFF")
            return
        # cmp [m], r (39) / cmp r, [m] (3B)
        if op == 0x39:
            a = f"({load_fn}(s, {addr_expr}) & {mask})"
            b = f"({r}[{dst_reg}] & {mask})"
            body.append(f"    cf = 1 if {a} < {b} else 0")
            body.append(f"    zf = 1 if {a} == {b} else 0")
            return
        if op == 0x3B:
            a = f"({r}[{dst_reg}] & {mask})"
            b = f"({load_fn}(s, {addr_expr}) & {mask})"
            body.append(f"    cf = 1 if {a} < {b} else 0")
            body.append(f"    zf = 1 if {a} == {b} else 0")
            return
        if op == 0x85:    # test r, [m]
            a = f"({r}[{dst_reg}] & {mask})"
            b = f"({load_fn}(s, {addr_expr}) & {mask})"
            body.append(f"    cf = 0")
            body.append(f"    zf = 1 if ({a} & {b}) == 0 else 0")
            return
        # ALU r/m, r (01 add, 29 sub, 09 or, 21 and, 31 xor)
        op_table = {0x01: "+", 0x29: "-", 0x09: "|",
                    0x21: "&", 0x31: "^"}
        if op in op_table:
            sym = op_table[op]
            body.append(
                f"    {store_fn}(s, {addr_expr}, "
                f"({load_fn}(s, {addr_expr}) {sym} {r}[{dst_reg}]) & {mask})")
            return
        # ALU r, r/m (03 add, 2B sub, 0B or, 23 and, 33 xor)
        op_table2 = {0x03: "+", 0x2B: "-", 0x0B: "|",
                     0x23: "&", 0x33: "^"}
        if op in op_table2:
            sym = op_table2[op]
            line = (
                f"    {r}[{dst_reg}] = "
                f"({r}[{dst_reg}] {sym} {load_fn}(s, {addr_expr})) & {mask}"
            )
            body.append(line)
            return
        raise NotImplementedError(f"unsupported ALU mem 0x{op:02x}")

    @staticmethod
    def _cond_expr(op: int) -> str:
        """Return a Python boolean expression for a Jcc condition."""
        # 70..7F short, 80..8F long.  Each has the same low nibble.
        low = op & 0xF
        return {
            0x0: "of == 1", 0x1: "of == 0",
            0x2: "cf == 1", 0x3: "cf == 0",
            0x4: "zf == 1", 0x5: "zf == 0",
            0x6: "cf == 1 or zf == 1",
            0x7: "cf == 0 and zf == 0",
            0x8: "sf == 1", 0x9: "sf == 0",
            0xA: "pf == 1", 0xB: "pf == 0",
            0xC: "sf != of", 0xD: "sf == of",
            0xE: "zf == 1 or sf != of",
            0xF: "zf == 0 and sf == of",
        }[low]

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, *, max_steps: int = 100_000,
            hot_loop_window: int = 4096,
            hot_loop_range: int = 0x4000,
            hot_loop_min_steps: int = 5_000,
            hot_loop_max_skips: int = 1024,
            hot_loop_short_circuit: bool = False,
            use_jit: bool = True) -> int:
        """Run until HLT, max_steps reached, or ``stopped`` set.

        When ``use_jit`` is true (the default), basic blocks are
        compiled to Python bytecode and run as one function call
        each.  This typically yields 5-20x the throughput of the
        per-instruction dispatch loop.  Blocks we can't compile
        fall back to ``step()``.
        """
        from collections import deque
        recent: "deque[int]" = deque(maxlen=hot_loop_window)
        detections = 0
        # Build the state dict once.  The JIT'd functions read
        # ``s['r']``, ``s['cf']`` etc. and write back the same way.
        state = self._build_jit_state()

        def _push(r, s, val: int) -> None:
            r[4] = (r[4] - 8) & 0xFFFFFFFFFFFFFFFF
            s["_s64"](s, r[4], val)

        def _pop(r, s) -> int:
            v = s["_l64"](s, r[4])
            r[4] = (r[4] + 8) & 0xFFFFFFFFFFFFFFFF
            return v

        # Inject the helpers into the namespace used by the JIT.
        # Each new block is compiled with these bound as defaults
        # so we don't have to pass them in explicitly.
        self._jit_push = _push
        self._jit_pop = _pop

        # Bind JIT helpers as plain functions so the JIT'd code does
        # not pay attribute-lookup cost on every load/store.
        jit_l = self._jit_load_u8
        jit_s = self._jit_store_u8
        jit_l32 = self._jit_load_u32
        jit_s32 = self._jit_store_u32
        jit_l64 = self._jit_load_u64
        jit_s64 = self._jit_store_u64
        for _ in range(max_steps):
            self.steps += 1
            rip_before = self.regs.get(15)
            recent.append(rip_before)
            if use_jit:
                cached = self._block_cache.get(rip_before)
                if cached is None:
                    try:
                        compiled = self._emit_block(rip_before)
                    except Exception:
                        compiled = None
                    if compiled is None:
                        # Couldn't compile -- fall back to step.
                        try:
                            self.step()
                        except EmulatorHalt:
                            return self.exit_code
                        if self.stopped:
                            return self.exit_code
                        continue
                    self._block_cache[rip_before] = compiled
                    cached = compiled
                fn, _length = cached
                # Refresh the flag scalars from the authoritative register
                # file before running the block.  Non-compilable blocks run
                # through ``step()``, which writes ``self.regs`` directly;
                # the flag copies held in ``state`` would otherwise be stale,
                # so a compiled block could branch on the wrong condition
                # (e.g. a stale ZF wrongly taking a ``jne``).
                state["cf"] = self.regs.cf
                state["zf"] = self.regs.zf
                state["sf"] = self.regs.sf
                state["of"] = self.regs.of
                state["pf"] = self.regs.pf
                state["df"] = self.regs.df
                # Refresh the page dict in case new pages were
                # mapped by the loader after we cached the block.
                state["pages"] = self.mem._pages
                try:
                    new_rip = fn(state, _push, _pop,
                                 jit_l, jit_s, jit_l32, jit_s32,
                                 jit_l64, jit_s64)
                    self.regs.set(15, new_rip)
                    # Write the block's flag results back to the register
                    # file so a following interpreter ``step()`` (or the
                    # next block) observes them.
                    self.regs.cf = state["cf"]
                    self.regs.zf = state["zf"]
                    self.regs.sf = state["sf"]
                    self.regs.of = state["of"]
                    self.regs.pf = state["pf"]
                    self.regs.df = state["df"]
                except EmulatorHalt:
                    return self.exit_code
                if self.stopped:
                    return self.exit_code
            else:
                try:
                    self.step()
                except EmulatorHalt:
                    return self.exit_code
                if self.stopped:
                    return self.exit_code
            # Hot-loop detection.  ``min``/``max`` over a large window is
            # O(window) per call, so we track a cheap running
            # "narrow window" bound instead: we only need to know
            # whether the last ``hot_loop_window`` RIPs stay inside a
            # small address range.  Checking every ``1 << 13`` steps
            # is plenty -- a hot loop executes millions of steps.
            if (self.steps > hot_loop_min_steps
                    and len(recent) == hot_loop_window
                    and (self.steps & 0x1FFF) == 0):
                lo = min(recent)
                hi = max(recent)
                if hi - lo < hot_loop_range:
                    detections += 1
                    if detections > hot_loop_max_skips:
                        log.warning(
                            "emulator: %d hot loops detected; "
                            "aborting run at 0x%x (pure-Python "
                            "cannot emulate multi-MB startup loops)",
                            detections - 1, rip_before)
                        self.stopped = True
                        return self.exit_code
                    # Only short-circuit if the loop body looks
                    # like a SIMD memory copy (lots of 0xC4 / 0xC5
                    # VEX prefix bytes in the loop body range).
                    simd_count = 0
                    span = hi - lo
                    if span < 0x2000:
                        try:
                            for off in range(lo, hi + 1):
                                b = self.mem.read_u8(off)
                                if b in (0xC4, 0xC5):
                                    simd_count += 1
                        except Exception:
                            pass
                    if simd_count < 4:
                        log.debug(
                            "emulator: hot loop at 0x%x "
                            "(range 0x%x, %d steps) -- not "
                            "acting, letting it run",
                            rip_before, hi - lo, self.steps)
                        detections -= 1
                        recent.clear()
                        continue
                    if not hot_loop_short_circuit:
                        # Detection-only mode.  We deliberately do NOT
                        # rewrite the machine state here: a partially
                        # reconstructed loop-exit state is worse than
                        # just running the loop, because the program
                        # then executes garbage.
                        detections -= 1
                        recent.clear()
                        continue
                    log.warning(
                        "emulator: hot loop detected near 0x%x "
                        "(range 0x%x, %d steps) -- short-circuiting "
                        "as memcpy(dst=rcx, src=rdx, count=r8) "
                        "(detection #%d)",
                        rip_before, hi - lo, self.steps, detections)
                    # MSVC AVX memcpy shape:
                    #   <unrolled vmovdqa stores>
                    #   add rcx, 0x100 ; sub r8, 0x100
                    #   cmp r8, 0x100  ; jae loop
                    # Do the whole copy in Python, then jump to the
                    # loop's *fall-through* (the tail handler) with the
                    # pointers already advanced, instead of re-running
                    # the unrolled body a million times.
                    #
                    # The back-edge branch sits at the top of the
                    # window.  Find it and target the instruction right
                    # after it -- that is the natural exit.
                    exit_ip = self._loop_exit_address(hi, lo)
                    if exit_ip is None:
                        exit_ip = hi + (hi - lo) + 0x10
                    rcx = self.regs.get(1)
                    rdx = self.regs.get(2)
                    r8 = self.regs.get(8)
                    if 0 < r8 < 0x1000_0000:
                        try:
                            self.mem.write(rcx, self.mem.read(rdx, r8))
                            # Advance the pointers as the loop would
                            # have, and zero the counter so the tail
                            # handler's own `cmp` falls through.
                            self.regs.set(1, rcx + r8)
                            self.regs.set(2, rdx + r8)
                            self.regs.set(8, 0)
                            log.info(
                                "fast memcpy: 0x%x bytes 0x%x -> 0x%x",
                                r8, rdx, rcx)
                        except Exception as exc:
                            log.warning("fast memcpy failed: %s", exc)
                    self.regs.set(15, exit_ip)
                    recent.clear()
        return -1

    def _loop_exit_address(self, hi: int, lo: int) -> Optional[int]:
        """Find the fall-through address of a hot loop whose body ends
        at ``hi``.

        We scan forward from ``lo`` for the conditional branch that
        jumps backwards (a back-edge).  The instruction immediately
        after it is the loop's natural exit.
        """
        span = hi - lo
        if span <= 0 or span > 0x400:
            return None
        for off in range(lo, hi):
            try:
                b = self.mem.read_u8(off)
            except Exception:
                return None
            # short jcc rel8
            if 0x70 <= b <= 0x7F:
                disp = self._signed(self.mem.read_u8(off + 1), 8)
                target = off + 2 + disp
                if target <= off:            # backwards = back-edge
                    return off + 2
            # long jcc rel32
            if b == 0x0F:
                b1 = self.mem.read_u8(off + 1)
                if 0x80 <= b1 <= 0x8F:
                    disp = self._signed(
                        self.mem.read_u32(off + 2), 32)
                    target = off + 6 + disp
                    if target <= off:
                        return off + 6
        return None


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
