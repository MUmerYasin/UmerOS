"""Debug UNC path."""
import sys
sys.path.insert(0, '.')
from compatibility import win_path
m = win_path.DosPathMapper(compat_root='C:/tmp/compat')
result = m.to_posix('BACKSLASH-BACKSLASH-server-BACKSLASH-BACKSLASH-share-BACKSLASH-BACKSLASH-path'.replace('BACKSLASH', chr(92)))
print('result:', repr(result))
import re
print('_UNC_RE:', win_path._UNC_RE.pattern)
test = chr(92) + chr(92) + 'server' + chr(92) + 'share' + chr(92) + 'path'
print('test:', repr(test))
print('match:', win_path._UNC_RE.match(test))
