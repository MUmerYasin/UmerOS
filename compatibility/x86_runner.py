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
        self.write(addr, struct.pack("<Q", value))

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
        callable_(self)
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
                disp = self._signed(self.mem.read_u32(addr + n), 32)
                n += 4
                base_idx = None
            else:
                base_idx = base
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
        # Parse any REX prefix.
        rex = 0
        if 0x40 <= b0 <= 0x4F:
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
        if op == 0xCC:
            # int 3 - signal breakpoint; the thunk dispatcher handles this.
            cur_rip = self.regs.get(15)
            self._invoke_thunk(cur_rip)
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
        if op == 0x3D:
            # cmp eax, imm32 (or rax, imm32 with REX.W)
            imm, n = self._read_imm(ip, 4 if not rex_w else 8)
            self._cmp(self.regs.get(REG_RAX), imm, op_size)
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
            # /2 call r/m, /4 jmp r/m, /6 push r/m
            if reg == 2:
                kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
                if kind == "reg":
                    target = self.regs.get(val)
                else:
                    target = self.mem.read_u64(val)
                # Return address = next instruction = rm_addr + n.
                self._push(rm_addr + n)
                self.regs.set(15, target)
                return
            if reg == 4:
                kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
                if kind == "reg":
                    target = self.regs.get(val)
                else:
                    target = self.mem.read_u64(val)
                self.regs.set(15, target)
                return
            if reg == 6:
                kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
                if kind == "reg":
                    src = self.regs.get(val)
                else:
                    src = self.mem.read_u64(val)
                self._push(src)
                self.regs.set(15, rm_addr + n)
                return
        if op == 0xC7:
            # mov r/m, imm (size determined by op_size)
            kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
            imm, m = self._read_imm(rm_addr + n, op_size)
            if kind == "mem64":
                self.mem.write_u64(val, imm)
            elif kind == "mem32":
                self.mem.write_u32(val, imm)
            elif kind == "reg":
                self.regs.set(val, imm)
            self.regs.set(15, rm_addr + n + m)
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
        if op == 0x0F and not rex_w:
            # shouldn't reach here normally
            pass
        raise EmulatorDecodeError(
            f"unsupported opcode 0x{op:02x} at 0x{ip-1:x}")

    def _decode_twobyte(self, op: int, ip: int, rex: int, rex_w: int,
                          rex_r: int, rex_x: int, rex_b: int,
                          op_size: int) -> None:
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
