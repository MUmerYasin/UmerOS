"""Diagnostic: trace where CMakeCCompilerId.exe actually spends its time.

Run:  python _diag_trace.py [max_steps]
"""
import collections
import sys

from compatibility.pe_loader import PeFile
from compatibility.win32_runner import Win32Runner

PATH = (r"F:\Pension Person Details\UmerOS\boot\python_vm\build"
        r"\CMakeFiles\4.3.2\CompilerIdC\CMakeCCompilerId.exe")

max_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000

pe = PeFile.from_file(PATH)
runner = Win32Runner(image_base=int(pe.optional_header.image_base))
runner.load_pe(pe, raw_image=pe.raw)
emu = runner.emulator

entry = (int(pe.optional_header.image_base)
         + pe.optional_header.address_of_entry_point)
print(f"entry     : {entry:#x}")
print(f"image base: {int(pe.optional_header.image_base):#x}")

# Record the RIP histogram by sampling after each step.
hist = collections.Counter()
samples = []

orig_run = emu.run


def traced_run(**kw):
    """Wrap emu.run so we sample RIP every N steps."""
    # Monkeypatch the emulator's step counter check by polling from a
    # background-free trick: run in slices.
    total = 0
    while total < kw.get("max_steps", max_steps):
        rc = emu.run(max_steps=50_000)
        total += 50_000
        rip = emu.regs.get(15)
        hist[rip] += 1
        samples.append((emu.steps, rip))
        if emu.stopped or rc != -1:
            break
    return rc


rc = traced_run(max_steps=max_steps)
print(f"rc        : {rc}")
print(f"steps     : {emu.steps}")
print(f"final rip : {emu.regs.get(15):#x}")
print(f"exit code : {emu.exit_code}")
print()
print("RIP samples (step, rip):")
for s, r in samples[-25:]:
    print(f"  {s:>10}  {r:#x}")
print()
print("top RIPs:")
for rip, n in hist.most_common(12):
    print(f"  {rip:#x}  x{n}")

# Dump the bytes around the final RIP.
rip = emu.regs.get(15)
print()
print(f"bytes at {rip:#x}:")
try:
    print("  ", emu.mem.read(rip, 64).hex(" "))
except Exception as exc:
    print("   <unreadable>", exc)
print("registers:")
for i in range(16):
    print(f"  r{i:<2} = {emu.regs.get(i):#018x}")
print("flags:", emu.regs.flags, "df:", getattr(emu.regs, "df", None))
