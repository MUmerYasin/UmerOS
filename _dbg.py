import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from compatibility import x86_runner

# Monkey-patch _decode_onebyte to print C7 details
orig_decode = x86_runner.Emulator._decode_onebyte

def patched(self, op, ip, rex, rex_w, rex_r, rex_x, rex_b, op_size):
    if op == 0xC7:
        rm_addr = ip + 1
        modrm = self.mem.read_u8(ip)
        mod = (modrm >> 6) & 3
        reg = (modrm >> 3) & 7
        rm = modrm & 7
        kind, val, n = self._resolve_rm(rm_addr, mod, rm, rex_b, op_size)
        imm, m = self._read_imm(rm_addr + n, 4)
        new_rip = rm_addr + n + m
        sys.stdout.write(f'C7 at 0x{ip-1:x}: rm_addr=0x{rm_addr:x} n={n} m={m} new_rip=0x{new_rip:x} kind={kind}\n')
        sys.stdout.flush()
        # Use orig behavior
    return orig_decode(self, op, ip, rex, rex_w, rex_r, rex_x, rex_b, op_size)

x86_runner.Emulator._decode_onebyte = patched

from compatibility.pe_loader import PeFile
from compatibility.win32_runner import Win32Runner

pe = PeFile.from_file(r'UmerOS\boot\python_vm\build\CMakeFiles\4.3.2\CompilerIdC\CMakeCCompilerId.exe')
runner = Win32Runner(image_base=int(pe.optional_header.image_base))
runner.load_pe(pe, raw_image=pe.raw)
entry_va = int(pe.optional_header.image_base) + pe.optional_header.address_of_entry_point
runner.emulator.regs.set(15, entry_va)

for i in range(12):
    rip = runner.emulator.regs.r[15]
    b = runner.emulator.mem.read(rip, 8).hex()
    sys.stdout.write(f'step {i}: rip=0x{rip:x} bytes={b}\n')
    sys.stdout.flush()
    try:
        runner.emulator.step()
    except Exception as e:
        sys.stdout.write(f'  ERROR: {type(e).__name__}: {e}\n')
        break