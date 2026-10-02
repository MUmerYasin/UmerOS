from compatibility import long_path as lp

def step(msg, expected, got):
    ok = expected == got
    print(("OK   " if ok else "FAIL "), msg)
    if not ok:
        print("       expected:", repr(expected))
        print("       got:     ", repr(got))
    return ok

all_ok = True
p = lp.parse_long_path(r"\\?\C:\Windows\System32\kernel32.dll")
all_ok &= step("1 prefix", lp.LongPathPrefix.WIN32_EXTENDED, p.prefix)
all_ok &= step("2 drive", "C", p.drive)
all_ok &= step("3 parts", ("Windows", "System32", "kernel32.dll"), p.path_parts)
all_ok &= step("4 to_string", r"\\?\C:\Windows\System32\kernel32.dll", p.to_string())
all_ok &= step("5 to_native", r"C:\Windows\System32\kernel32.dll", p.to_native())

p = lp.parse_long_path(r"\\?\UNC\server\share\dir\file.txt")
all_ok &= step("6 prefix", lp.LongPathPrefix.WIN32_UNC, p.prefix)
all_ok &= step("7 is_unc", True, p.is_unc)
all_ok &= step("8 server", "server", p.server)
all_ok &= step("9 share", "share", p.share)
all_ok &= step("10 parts", ("dir", "file.txt"), p.path_parts)
all_ok &= step("11 to_string", r"\\?\UNC\server\share\dir\file.txt", p.to_string())
all_ok &= step("12 to_native", r"\\server\share\dir\file.txt", p.to_native())

p = lp.parse_long_path(r"\\.\COM1")
all_ok &= step("13 prefix", lp.LongPathPrefix.WIN32_DEVICE, p.prefix)
all_ok &= step("14 to_native", "COM1", p.to_native())

p = lp.parse_long_path(r"\\?\C:/Windows/System32")
all_ok &= step("15 prefix", lp.LongPathPrefix.WIN32_EXTENDED, p.prefix)
all_ok &= step("16 drive", "C", p.drive)
all_ok &= step("17 parts", ("Windows", "System32"), p.path_parts)

p = lp.parse_long_path(r"C:\Windows")
all_ok &= step("18 prefix", lp.LongPathPrefix.NONE, p.prefix)
all_ok &= step("19 drive", "C", p.drive)

p = lp.parse_long_path("")
all_ok &= step("20 prefix", lp.LongPathPrefix.NONE, p.prefix)

short = r"C:\Windows"
all_ok &= step("21 wrap short", short, lp.wrap_if_needed(short, drive="C"))

long = "C:\\" + "\\".join(["a" * 50] * 10)
wrapped = lp.wrap_if_needed(long, drive="C")
all_ok &= step("22 starts", True, wrapped.startswith("\\\\?\\C:\\"))
all_ok &= step("23 len", False, len(wrapped) <= lp.MAX_WIN32_PATH)

s = lp.make_extended("d", ("foo", "bar"))
p = lp.parse_long_path(s)
all_ok &= step("24 drive", "d", p.drive)
all_ok &= step("25 parts", ("foo", "bar"), p.path_parts)

s = lp.make_extended_unc("srv", "sh", ("x", "y"))
p = lp.parse_long_path(s)
all_ok &= step("26 is_unc", True, p.is_unc)
all_ok &= step("27 server", "srv", p.server)
all_ok &= step("28 share", "sh", p.share)
all_ok &= step("29 parts", ("x", "y"), p.path_parts)

all_ok &= step("30 too short", False, lp.is_too_long_for_win32("x" * (lp.MAX_WIN32_PATH - 1)))
all_ok &= step("31 too long", True, lp.is_too_long_for_win32("x" * lp.MAX_WIN32_PATH))

print("ALL OK:", all_ok)
