"""Test all _selftest functions in bin/ modules with full tracebacks."""
import sys
import os
import types
import traceback

sys.path.insert(0, r'UmerOS')
os.chdir(r'UmerOS')

# Mock termios for Windows
if 'termios' not in sys.modules:
    termios = types.ModuleType('termios')
    termios.error = OSError
    termios.ICANON = 0o2
    termios.ECHO = 0o10
    termios.TCSANOW = 0
    termios.tcgetattr = lambda fd: [0]*7
    termios.tcsetattr = lambda fd, when, attrs: None
    sys.modules['termios'] = termios

# Mock pwd/spwd/crypt for Windows
if 'pwd' not in sys.modules:
    pwd = types.ModuleType('pwd')
    pwd.getpwnam = lambda u: None
    pwd.getpwuid = lambda u: types.SimpleNamespace(
        pw_name="root", pw_uid=0, pw_gid=0,
        pw_dir="/root", pw_shell="/bin/sh"
    )
    pwd.struct_passwd = lambda t: types.SimpleNamespace(
        pw_name=t[0], pw_uid=t[2], pw_gid=t[3],
        pw_dir=t[5], pw_shell=t[6]
    )
    sys.modules['pwd'] = pwd
else:
    import pwd as _real_pwd
    if not hasattr(_real_pwd, 'getpwuid'):
        _real_pwd.getpwuid = lambda u: types.SimpleNamespace(
            pw_name="root", pw_uid=0, pw_gid=0,
            pw_dir="/root", pw_shell="/bin/sh"
        )
if 'spwd' not in sys.modules:
    spwd = types.ModuleType('spwd')
    spwd.getspnam = lambda u: None
    sys.modules['spwd'] = spwd
if 'crypt' not in sys.modules:
    crypt = types.ModuleType('crypt')
    crypt.crypt = lambda pw, salt: pw
    sys.modules['crypt'] = crypt

# Mock signal.SIGHUP for Windows
import signal
if not hasattr(signal, 'SIGHUP'):
    signal.SIGHUP = 1
if not hasattr(signal, 'SIGQUIT'):
    signal.SIGQUIT = 3
if not hasattr(signal, 'SIGUSR1'):
    signal.SIGUSR1 = 10
if not hasattr(signal, 'SIGUSR2'):
    signal.SIGUSR2 = 12
if not hasattr(signal, 'SIGKILL'):
    signal.SIGKILL = 9
if not hasattr(signal, 'SIGSTOP'):
    signal.SIGSTOP = 17
if not hasattr(signal, 'SIGCONT'):
    signal.SIGCONT = 19
if not hasattr(signal, 'SIGTERM'):
    signal.SIGTERM = 15

# Mock os.getuid/getgid on Windows
if not hasattr(os, 'getuid'):
    os.getuid = lambda: 0
if not hasattr(os, 'getgid'):
    os.getgid = lambda: 0
if not hasattr(os, 'geteuid'):
    os.geteuid = lambda: 0
if not hasattr(os, 'getegid'):
    os.getegid = lambda: 0

files = [
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

passed = 0
failed = 0
errors = 0

for name, module_path in files:
    try:
        mod = __import__(module_path, fromlist=[name])
        if hasattr(mod, '_selftest'):
            try:
                result = mod._selftest()
                if result:
                    print(f"  PASS  {name}")
                    passed += 1
                else:
                    print(f"  FAIL  {name}")
                    failed += 1
            except Exception as e:
                print(f"  ERROR {name}: {e}")
                traceback.print_exc()
                errors += 1
        else:
            print(f"  SKIP  {name} (no _selftest)")
    except Exception as e:
        print(f"  IMPORT ERROR {name}: {e}")
        errors += 1

print(f"\nResults: {passed} passed, {failed} failed, {errors} errors out of {len(files)}")
sys.exit(0 if (failed == 0 and errors == 0) else 1)
