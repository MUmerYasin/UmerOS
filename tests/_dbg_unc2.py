"""Debug UNC path more."""
import sys
sys.path.insert(0, '.')
from compatibility import win_path

# Reproduce the exact test scenario
m = win_path.DosPathMapper(compat_root='C:/tmp/compat')
# r"\\server\share\path" in Python is a raw string with 2 backslashes followed by server, backslash, share, backslash, path
test = '\\\\server\\share\\path'  # this is the raw string equivalent
print('input:', repr(test))
print('result:', repr(m.to_posix(test)))
