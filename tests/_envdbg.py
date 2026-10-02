import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# Manual breakdown
out = bytearray()
k = "PATH"
v = "C:\\Windows;overridden"
out += k.encode("utf-16-le")
out += b"="
out += v.encode("utf-16-le")
out += b"\x00\x00"
out += b"\x00\x00"
with open('_envdbg.txt', 'w', encoding='utf-8') as f:
    f.write(f'len(out) = {len(out)}\n')
    f.write(f'hex = {out.hex()}\n')
    # Each step
    f.write(f'\n')
    f.write(f'k utf-16: {k.encode("utf-16-le").hex()} len={len(k.encode("utf-16-le"))}\n')
    f.write(f'= : {b"=".hex()} len={len(b"=")}\n')
    f.write(f'v utf-16: {v.encode("utf-16-le").hex()} len={len(v.encode("utf-16-le"))}\n')
    f.write(f'\\x00\\x00: {b"\\x00\\x00".hex()} len={len(b"\\x00\\x00")}\n')
    f.write(f'total = {8 + 2 + 42 + 2 + 2}\n')