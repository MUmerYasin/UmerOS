"""Diagnostic: find where the emulator first leaves the loaded image.

Run:  python _diag_leave.py [max_steps]
"""
import sys

from compatibility.pe_loader import PeFile
from compatibility.win32_runner import Win32Runner

PATH = (r"F:\Pension Person Details\UmerOS\boot\python_vm\build"
        r"\CMakeFiles\4.3.2\CompilerIdC\CMakeCCompilerId.exe")

max_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000

pe = PeFile.from_file(PATH)
base = int(pe.optional_header.image_base)
runner = Win32Runner(image_base=base)
runner.load_pe(pe, raw_image=pe.raw)
emu = runner.emulator

entry = base + pe.optional_header.address_of_entry_point
print(f"entry     : {entry:#x}")
print(f"image base: {base:#x}")

# Image extent: highest section VA + size.
top = base
for sec in pe.sections:
    end = base + sec.virtual_address + sec.virtual_size
    top = max(top, end)
print(f"image top : {top:#x}")

trace = []
first_leave = None
prev = None

for _ in range(max_steps // 200):
    rc = emu.run(max_steps=200)
    rip = emu.regs.get(15)
    trace.append((emu.steps, rip, rc))
    if not (base <= rip < top):
        first_leave = (emu.steps, rip, prev)
        break
    if emu.stopped:
        break
    prev = rip

if first_leave:
    steps, rip, prev = first_leave
    print()
    print(f"*** left the image at step {steps} ***")
    print(f"    last in-image RIP: {prev:#x}")
    print(f"    first out RIP    : {rip:#x}")
    print()
    print("last 12 RIPs:")
    for s, r, _ in trace[-12:]:
        print(f"  {s:>9} {r:#x}")
    print()
    print(f"bytes at last in-image RIP {prev:#x}:")
    print("  ", emu.mem.read(prev, 48).hex(" "))
    print(f"bytes at first out RIP {rip:#x}:")
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
    print(f"  flags cf={emu.regs.cf} zf={emu.regs.zf} sf={emu.regs.sf} "
          f"of={emu.regs.of} df={emu.regs.df}")
else:
    print()
    print("never left the image")
    print("last RIPs:")
    for s, r, _ in trace[-12:]:
        print(f"  {s:>9} {r:#x}")
print(f"steps: {emu.steps}  exit_code: {emu.exit_code}")
