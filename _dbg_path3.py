"""Trace drive_relative."""
import sys
import os
import tempfile
sys.path.insert(0, '.')
from compatibility import win_path

tmp = tempfile.mkdtemp()
compat = os.path.join(tmp, "compat")
m = win_path.DosPathMapper(compat_root=compat)
m.set_drive_cwd("D", r"D:\Projects\UmerOS")
try:
    result = m.to_posix("D:readme.txt")
    print('result:', result)
except Exception as e:
    print('error:', type(e).__name__, e)
