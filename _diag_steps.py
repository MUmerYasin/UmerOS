"""Diagnostic: single-step trace of the first N instructions.

Run:  python _diag_steps.py [n]
"""
import sys

from compatibility.pe_loader import PeFile
from compatibility.win32_runner import Win32Runner

PATH = (r"F:\Pension Person Details\UmerOS\boot\python_vm\build"
        r"\CMakeFiles\4.3.2\CompilerIdC\CMakeCCompilerId.exe")

n = int(sys.argv[1]) if len(sys.argv) > 1 else 300

pe = PeFile.from_file(PATH)
base = int(pe.optional_header.image_base)
runner = Win32Runner(image_base=base)
runner.load_pe(pe, raw_image=pe.raw)
emu = runner.emulator

entry = base + pe.optional_header.address_of_entry_point
top = base
for sec in pe.sections:
    top = max(top, base + sec.virtual_address + sec.virtual_size)

print(f"entry {entry:#x}  base {base:#x}  top {top:#x}")
print()

for i in range(n):
    rip = emu.regs.get(15)
    try:
        b = emu.mem.read(rip, 16).hex(" ")
    except Exception as exc:
        b = f"<unreadable {exc}>"
    inside = "IMG" if base <= rip < top else "   "
    print(f"{i:>4} {rip:#012x} {inside} {b}")
    try:
        emu.step()
    except Exception as exc:
        print(f"     !! step failed: {type(exc).__name__}: {exc}")
        break
