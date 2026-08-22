# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Diagnose which _selftest hangs or fails."""
import sys
import os
import types
import signal
import traceback

sys.path.insert(0, r'UmerOS')
os.chdir(r'UmerOS')

# Mocks
if 'termios' not in sys.modules:
    t = types.ModuleType('termios')
    t.error = OSError
    t.ICANON = 2
    t.ECHO = 8
    t.TCSANOW = 0
    t.tcgetattr = lambda fd: [0]*7
    t.tcsetattr = lambda fd, w, a: None
    sys.modules['termios'] = t
if 'pwd' not in sys.modules:
    p = types.ModuleType('pwd')
    p.getpwnam = lambda u: None
    p.getpwuid = lambda u: types.SimpleNamespace(
        pw_name='root', pw_uid=0, pw_gid=0, pw_dir='/root', pw_shell='/bin/sh')
    p.struct_passwd = lambda t: types.SimpleNamespace(
        pw_name=t[0], pw_uid=t[2], pw_gid=t[3], pw_dir=t[5], pw_shell=t[6])
    sys.modules['pwd'] = p
if 'spwd' not in sys.modules:
    s = types.ModuleType('spwd')
    s.getspnam = lambda u: None
    sys.modules['spwd'] = s
if 'crypt' not in sys.modules:
    c = types.ModuleType('crypt')
    c.crypt = lambda pw, salt: pw
    sys.modules['crypt'] = c
for attr, default in [('SIGHUP',1),('SIGQUIT',3),('SIGUSR1',10),('SIGUSR2',12),
                       ('SIGKILL',9),('SIGSTOP',17),('SIGCONT',19),('SIGTERM',15)]:
    if not hasattr(signal, attr):
        setattr(signal, attr, default)
for attr in ['getuid','getgid','geteuid','getegid']:
    if not hasattr(os, attr):
        setattr(os, attr, lambda: 0)

import importlib

modules_to_test = [
    ("boolean_ops", "bin.boolean_ops"),
    ("system_info", "bin.system_info"),
    ("permissions", "bin.permissions"),
    ("essential_commands", "bin.essential_commands"),
    ("shell", "bin.shell"),
    ("network_cmds", "bin.network_cmds"),
    ("process", "bin.process"),
    ("user_commands", "bin.user_commands"),
    ("csh", "bin.csh"),
    ("ed", "bin.ed"),
]

for name, modpath in modules_to_test:
    print(f"\n=== Testing {name} ===")
    try:
        mod = importlib.import_module(modpath)
        if hasattr(mod, '_selftest'):
            result = mod._selftest()
            print(f"  RESULT: {result}")
        else:
            print(f"  SKIP (no _selftest)")
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        traceback.print_exc()
