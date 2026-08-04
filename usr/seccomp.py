"""
USeccomp Module
================
Linux kernel seccomp-BPF security filtering.
Implements syscall filtering with BPF programs.

Reference: docs.kernel.org/userspace-api/seccomp_filter.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
EPERM: int = 13
EFAULT: int = 14


class SeccompMode(IntEnum):
    """Seccomp modes."""
    SECCOMP_MODE_DISABLED: int = 0
    SECCOMP_MODE_STRICT: int = 1
    SECCOMP_MODE_FILTER: int = 2


class SeccompRet(IntEnum):
    """Seccomp return values."""
    SECCOMP_RET_KILL_PROCESS: int = 0x00000000
    SECCOMP_RET_KILL_THREAD: int = 0x00000001
    SECCOMP_RET_TRAP: int = 0x00020000
    SECCOMP_RET_ERRNO: int = 0x00030000
    SECCOMP_RET_USER_NOTIF: int = 0x00040000
    SECCOMP_RET_TRACE: int = 0x00050000
    SECCOMP_RET_LOG: int = 0x00060000
    SECCOMP_RET_ALLOW: int = 0x7fff0000
    SECCOMP_RET_ACTION_MASK: int = 0x7fff0000


class BPFAluOp(IntEnum):
    """BPF ALU operations."""
    BPF_ADD: int = 0x00
    BPF_SUB: int = 0x10
    BPF_MUL: int = 0x20
    BPF_DIV: int = 0x30
    BPF_OR: int = 0x40
    BPF_AND: int = 0x50
    BPF_LSH: int = 0x60
    BPF_RSH: int = 0x70
    BPF_NEG: int = 0x80
    BPF_MOD: int = 0x90
    BPF_XOR: int = 0xa0
    BPF_MOV: int = 0xb0
    BPF_ARSH: int = 0xc0


class BPFJmpOp(IntEnum):
    """BPF JMP operations."""
    BPF_JA: int = 0x00
    BPF_JEQ: int = 0x10
    BPF_JGT: int = 0x20
    BPF_JGE: int = 0x30
    BPF_JSET: int = 0x40
    BPF_JNE: int = 0x50
    BPF_JLT: int = 0xa0
    BPF_JLE: int = 0xb0
    BPF_JSGT: int = 0x60
    BPF_JSGE: int = 0x70
    BPF_JSLT: int = 0xc0
    BPF_JSLE: int = 0xd0


class BPFReg(IntEnum):
    """BPF registers."""
    BPF_REG_A: int = 10
    BPF_REG_X: int = 11
    BPF_REG_R0: int = 0
    BPF_REG_R1: int = 1
    BPF_REG_R2: int = 2
    BPF_REG_R3: int = 3
    BPF_REG_R4: int = 4
    BPF_REG_R5: int = 5
    BPF_REG_R6: int = 6
    BPF_REG_R7: int = 7
    BPF_REG_R8: int = 8
    BPF_REG_R9: int = 9
    BPF_REG_FP: int = 10


class SeccompFilterFlag(IntEnum):
    """Seccomp filter flags."""
    SECCOMP_FILTER_FLAG_TSYNC: int = 1
    SECCOMP_FILTER_FLAG_LOG: int = 2
    SECCOMP_FILTER_FLAG_SPEC_ALLOW: int = 4
    SECCOMP_FILTER_FLAG_NEW_LISTENER: int = 8
    SECCOMP_FILTER_FLAG_TSYNC_ESRCH: int = 16


# ============================================================================
# BPF Structures
# ============================================================================

@dataclass
class BPFInstruction:
    """BPF instruction."""
    code: int = 0
    jt: int = 0
    jf: int = 0
    k: int = 0


@dataclass
class SeccompData:
    """Seccomp data passed to filter."""
    nr: int = 0
    arch: int = 0
    instruction_pointer: int = 0
    args: List[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])


@dataclass
class SeccompFilter:
    """Seccomp BPF filter."""
    filter_id: int
    mode: SeccompMode = SeccompMode.SECCOMP_MODE_FILTER
    prog: List[BPFInstruction] = field(default_factory=list)
    next_filter: Optional[int] = None
    on_exec: bool = False
    tsync: bool = False
    log: bool = False
    allow: bool = False
    defaction: int = SeccompRet.SECCOMP_RET_ALLOW


# ============================================================================
# BPF Interpreter
# ============================================================================

class BPFInterpreter:
    """Simple BPF instruction interpreter for seccomp."""

    def __init__(self) -> None:
        self._acc: int = 0
        self._x: int = 0
        self._mem: List[int] = [0] * 16

    def run(self, prog: List[BPFInstruction], data: SeccompData) -> int:
        self._acc = 0
        self._x = 0
        pc = 0
        while pc < len(prog):
            inst = prog[pc]
            code = inst.code
            class_ = (code & 0x07)
            size = (code & 0x18) >> 3
            mode = (code & 0xe0) >> 5
            op = code & 0xf0
            if class_ == 0x00:
                if code == 0x06:
                    pc += inst.k + 1
                    continue
            elif class_ == 0x01:
                if size == 0x00:
                    if mode == 0x00:
                        self._acc = inst.k
                    elif mode == 0x20:
                        self._acc = data.nr
                    elif mode == 0x40:
                        self._acc = data.arch
                    elif mode == 0x60:
                        if inst.k < 6:
                            self._acc = data.args[inst.k]
                elif size == 0x08:
                    if mode == 0x00:
                        self._x = inst.k
                    elif mode == 0x20:
                        self._x = data.nr
                    elif mode == 0x40:
                        self._x = data.arch
                    elif mode == 0x60:
                        if inst.k < 6:
                            self._x = data.args[inst.k]
            elif class_ == 0x04:
                if size == 0x00:
                    if op == BPFAluOp.BPF_ADD:
                        self._acc += inst.k
                    elif op == BPFAluOp.BPF_SUB:
                        self._acc -= inst.k
                    elif op == BPFAluOp.BPF_AND:
                        self._acc &= inst.k
                    elif op == BPFAluOp.BPF_OR:
                        self._acc |= inst.k
                    elif op == BPFAluOp.BPF_LSH:
                        self._acc <<= inst.k
                    elif op == BPFAluOp.BPF_RSH:
                        self._acc >>= inst.k
                    elif op == BPFAluOp.BPF_MOV:
                        self._acc = inst.k
                elif size == 0x08:
                    if op == BPFAluOp.BPF_ADD:
                        self._acc += self._x
                    elif op == BPFAluOp.BPF_SUB:
                        self._acc -= self._x
                    elif op == BPFAluOp.BPF_AND:
                        self._acc &= self._x
                    elif op == BPFAluOp.BPF_OR:
                        self._acc |= self._x
                    elif op == BPFAluOp.BPF_MOV:
                        self._acc = self._x
            elif class_ == 0x05:
                taken = False
                if op == BPFJmpOp.BPF_JA:
                    taken = True
                elif op == BPFJmpOp.BPF_JEQ:
                    taken = (self._acc == inst.k)
                elif op == BPFJmpOp.BPF_JGT:
                    taken = (self._acc > inst.k)
                elif op == BPFJmpOp.BPF_JGE:
                    taken = (self._acc >= inst.k)
                elif op == BPFJmpOp.BPF_JNE:
                    taken = (self._acc != inst.k)
                elif op == BPFJmpOp.BPF_JSET:
                    taken = bool(self._acc & inst.k)
                if taken:
                    pc += inst.jt + 1
                else:
                    pc += inst.jf + 1
                continue
            elif class_ == 0x07:
                if code == 0x06:
                    return SeccompRet.SECCOMP_RET_ALLOW
            pc += 1
        return SeccompRet.SECCOMP_RET_ALLOW


# ============================================================================
# Seccomp Manager
# ============================================================================

class SeccompManager:
    """Seccomp subsystem manager."""

    def __init__(self) -> None:
        self._filters: Dict[int, SeccompFilter] = {}
        self._next_id: int = 1
        self._interpreter = BPFInterpreter()
        self._proc_filters: Dict[int, List[int]] = {}

    def install_filter(self, pid: int, prog: List[BPFInstruction], flags: int = 0) -> int:
        fid = self._next_id
        self._next_id += 1
        filt = SeccompFilter(
            filter_id=fid,
            prog=prog,
            tsync=bool(flags & SeccompFilterFlag.SECCOMP_FILTER_FLAG_TSYNC),
            log=bool(flags & SeccompFilterFlag.SECCOMP_FILTER_FLAG_LOG),
        )
        self._filters[fid] = filt
        if pid not in self._proc_filters:
            self._proc_filters[pid] = []
        self._proc_filters[pid].append(fid)
        return fid

    def add_filter(self, pid: int, prog: List[BPFInstruction], flags: int = 0) -> int:
        return self.install_filter(pid, prog, flags)

    def evaluate(self, pid: int, data: SeccompData) -> int:
        filters = self._proc_filters.get(pid, [])
        for fid in filters:
            filt = self._filters.get(fid)
            if filt and filt.prog:
                result = self._interpreter.run(filt.prog, data)
                if result != SeccompRet.SECCOMP_RET_ALLOW:
                    return result
        return SeccompRet.SECCOMP_RET_ALLOW

    def set_mode(self, pid: int, mode: SeccompMode) -> int:
        if pid not in self._proc_filters:
            self._proc_filters[pid] = []
        return SUCCESS

    def remove_filter(self, pid: int, filter_id: int) -> int:
        filters = self._proc_filters.get(pid, [])
        if filter_id in filters:
            filters.remove(filter_id)
            self._filters.pop(filter_id, None)
            return SUCCESS
        return EINVAL

    def get_filters(self, pid: int) -> List[SeccompFilter]:
        fids = self._proc_filters.get(pid, [])
        return [self._filters[fid] for fid in fids if fid in self._filters]

    def sync_filters(self, pid: int) -> int:
        filters = self._proc_filters.get(pid, [])
        if not filters:
            return SUCCESS
        return SUCCESS

    def user_notif_ioctl(self, pid: int, cmd: int, arg: int) -> int:
        return SUCCESS


# ============================================================================
# Global Instance
# ============================================================================

_global_seccomp: Optional[SeccompManager] = None


def get_seccomp_manager() -> SeccompManager:
    global _global_seccomp
    if _global_seccomp is None:
        _global_seccomp = SeccompManager()
    return _global_seccomp


def seccomp_install_filter(pid: int, prog: List[BPFInstruction], flags: int = 0) -> int:
    return get_seccomp_manager().install_filter(pid, prog, flags)


def seccomp_evaluate(pid: int, nr: int, arch: int = 0, args: Optional[List[int]] = None) -> int:
    if args is None:
        args = [0, 0, 0, 0, 0, 0]
    data = SeccompData(nr=nr, arch=arch, args=args)
    return get_seccomp_manager().evaluate(pid, data)
