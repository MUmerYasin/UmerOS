"""Trace path resolution."""
import sys, os, tempfile
sys.path.insert(0, '.')
from compatibility import win_path

tmp = tempfile.mkdtemp()
compat = os.path.join(tmp, "compat")
m = win_path.DosPathMapper(compat_root=compat)
m.set_drive_cwd("D", r"D:\Projects\UmerOS")

# Patch helper
orig = m._drive_absolute_to_posix
def traced(drive, rest):
    print(f"  _drive_absolute_to_posix({drive!r}, {rest!r})")
    res = orig(drive, rest)
    print(f"    -> {res!r}")
    return res
m._drive_absolute_to_posix = traced

print('input:', repr("D:readme.txt"))
result = m.to_posix("D:readme.txt")
print('result:', result)
