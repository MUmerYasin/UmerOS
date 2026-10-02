"""Debug the path recursion."""
import sys
import os
import tempfile
sys.path.insert(0, '.')
from compatibility import win_path

tmp = tempfile.mkdtemp()
compat = os.path.join(tmp, "compat")
m = win_path.DosPathMapper(compat_root=compat)
m.set_drive_cwd("D", r"D:\Projects\UmerOS")
import traceback
try:
    result = m.to_posix("D:readme.txt")
    print('result:', result)
except RecursionError:
    print("RECURSION")
    # Print the last 30 lines of traceback
    tb = traceback.format_stack()
    for line in tb[-20:]:
        print(line)
