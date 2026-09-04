"""Smoke test all compatibility modules."""
import sys
sys.path.insert(0, '.')
mods = ['mz_loader', 'ne_loader', 'pe_loader', 'pe_imports', 'pe_exports',
        'pe_relocations', 'pe_tls', 'pe_resources',
        'registry_hive', 'registry_view', 'registry_paths',
        'win_kernel32', 'win_user32', 'win_gdi32', 'win_advapi32', 'win_ntdll']
for m in mods:
    try:
        mod = __import__('compatibility.' + m, fromlist=[m])
        if not hasattr(mod, '_selftest'):
            print(f'  {m:20s}  (no selftest)')
            continue
        st = mod._selftest()
        print(f'  {m:20s}  {("OK" if st else "FAIL")}')
    except Exception as e:
        print(f'  {m:20s}  FAIL: {type(e).__name__}: {e}')
