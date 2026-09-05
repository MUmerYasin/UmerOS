"""Trace the recursion in win_path."""
import sys
import os
import tempfile
sys.path.insert(0, '.')
from compatibility import win_path
import re

tmp = tempfile.mkdtemp()
compat = os.path.join(tmp, "compat")
m = win_path.DosPathMapper(compat_root=compat)
m.set_drive_cwd("D", r"D:\Projects\UmerOS")

# Patch the function to trace
orig = m._to_posix_inner
depth = [0]
def traced(dos_path):
    depth[0] += 1
    if depth[0] > 30:
        print(f"DEPTH>30, dos_path={dos_path!r}")
        raise SystemExit
    res = orig(dos_path)
    depth[0] -= 1
    return res
m._to_posix_inner = traced

# Test the regex
import compatibility.win_path as wp
_DRIVE_RE = wp._DRIVE_RE
print("regex:", r"^([A-Za-z]):([^\\].*)?$")
test_strs = ["D:readme.txt", "D:\\readme.txt", "D:\\readme.txt"]
for s in test_strs:
    print(f"  {s!r} -> case4 match =", re.match(r"^([A-Za-z]):([^\\].*)?$", s.lower()) is not None)
    print(f"  {s!r} -> case5 match =", _DRIVE_RE.match(s) is not None)

result = m.to_posix("D:readme.txt")
print('result:', result)
