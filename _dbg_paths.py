"""Debug win_path."""
import sys
sys.path.insert(0, '.')
from compatibility import win_path
m = win_path.DosPathMapper(compat_root='/compat')
print('C:\\Windows ->', repr(m.to_posix(r'C:\Windows')))
print('C:\\Windows\\System32 ->', repr(m.to_posix(r'C:\Windows\System32')))
print('D:test.txt ->', repr(m.to_posix(r'D:test.txt')))
m.set_drive_cwd('D', r'D:\Projects\UmerOS')
print('D:readme.txt ->', repr(m.to_posix(r'D:readme.txt')))
