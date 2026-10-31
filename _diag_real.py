"""Diagnostic: run CMakeCCompilerId.exe with the REAL compatibility stubs.

Run:  python _diag_real.py [max_steps]
"""
import sys

from compatibility.pe_loader import PeFile
from compatibility.win32_runner import Win32Runner

PATH = (r"F:\Pension Person Details\UmerOS\boot\python_vm\build"
        r"\CMakeFiles\4.3.2\CompilerIdC\CMakeCCompilerId.exe")

max_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000

pe = PeFile.from_file(PATH)
base = int(pe.optional_header.image_base)
# imports=None -> Win32Runner uses dll_loader.HOST_LIBRARIES (the real stubs)
runner = Win32Runner(image_base=base, imports=None)
runner.load_pe(pe, raw_image=pe.raw)
emu = runner.emulator

entry = base + pe.optional_header.address_of_entry_point
emu.regs.set(15, entry)

top = base
for sec in pe.sections:
    top = max(top, base + sec.virtual_address + sec.virtual_size)

print(f"entry {entry:#x}  base {base:#x}  top {top:#x}")

# Where does it go?  Sample RIP every 20k steps.
samples = []
left = None
prev_rip = entry
while emu.steps < max_steps:
    rc = emu.run(max_steps=20_000)
    rip = emu.regs.get(15)
    samples.append((emu.steps, rip))
    if not (base <= rip < top):
        left = (emu.steps, rip, prev_rip)
        break
    prev_rip = rip
    if emu.stopped or rc >= 0:
        break

print(f"steps {emu.steps}  exit_code {emu.exit_code}  stopped {emu.stopped}")
print(f"final rip {emu.regs.get(15):#x}")
print()
print("samples:")
for s, r in samples[-20:]:
    tag = "IMG" if base <= r < top else "   "
    print(f"  {s:>9} {r:#012x} {tag}")
if left:
    steps, rip, prev = left
    print()
    print(f"*** left image at step {steps}: {prev:#x} -> {rip:#x} ***")
    print("bytes before leave:")
    print("  ", emu.mem.read(prev, 48).hex(" "))
    print("bytes at leave:")
    try:
        print("  ", emu.mem.read(rip, 48).hex(" "))
    except Exception as exc:
        print("   <unreadable>", exc)
    print()
    print("registers:")
    for i in range(16):
        v = emu.regs.get(i)
        if v:
            print(f"  r{i:<2} = {v:#018x}")
