import boot.cmdline as m

def check(label, cond):
    print(label, ':', 'OK' if cond else 'FAIL')
    if not cond:
        raise SystemExit(1)

p2 = m.parse_cmdline('console="ttyS0,115200n8"')
print('console value:', repr(p2['console'].value))
print('console kind :', p2['console'].kind)
print('quoted       :', m.CmdParamKind.QUOTED)
print('expected match:', p2['console'].value == 'ttyS0,115200n8')
print('expected kind :', p2['console'].kind == m.CmdParamKind.QUOTED)
