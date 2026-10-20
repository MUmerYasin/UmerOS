"""H182 applier: append the four _selftest() blocks + strengthen the package one.

Idempotent: already-patched modules are skipped.  Every write keeps the CRLF
invariant (``text.count("\\n") == text.count("\\r\\n")``) and re-parses.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path("F:/Pension Person Details/UmerOS")
NET = ROOT / "network"

TARGETS = {
    "dns_resolver.py": "_h182_b1_dns.py",
    "tcp_server.py": "_h182_b2_tcp.py",
    "http_client.py": "_h182_b3_http.py",
    "network_stack.py": "_h182_b4_stack.py",
}

#: Unique tail of ``network/__init__.py`` used as the insertion anchor.
INIT_ANCHOR = '''    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
'''

INIT_LOOP = '''    # H182: every leaf module now carries its own ``_selftest()``, so run them
    # all from here too -- ``python network/__init__.py`` becomes a one-command
    # regression check for the whole subsystem.
    for _module_name in (
        "dns_resolver",
        "http_client",
        "network_stack",
        "tcp_server",
        "vpn_tunnel",
    ):
        _module = _il.import_module(f"{__name__}.{_module_name}")
        _checker = getattr(_module, "_selftest", None)
        if _checker is None:
            print(
                f"{__name__} selftest FAIL: {_module_name} has no _selftest()",
                file=_sys.stderr,
            )
            return False
        if not _checker():
            print(
                f"{__name__} selftest FAIL: {_module_name}._selftest() failed",
                file=_sys.stderr,
            )
            return False
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
'''


def load_block(script_name: str) -> str:
    """Read a block file and return only its BLOCK constant."""
    source = ROOT / script_name
    namespace: dict[str, str] = {}
    exec(compile(source.read_bytes().decode("utf-8"), str(source), "exec"), namespace)
    return namespace["BLOCK"]


# --- the four leaf modules ----------------------------------------------------
for target, block_file in TARGETS.items():
    path = NET / target
    raw = path.read_bytes().decode("utf-8")

    if "def _selftest" in raw:
        print(f"skipped {target} (already patched)")
        continue

    assert raw.endswith("\r\n"), f"{target}: does not end with a newline"
    assert raw.count("\n") == raw.count("\r\n"), f"{target}: mixed line endings"

    block = load_block(block_file)
    assert "\r" not in block, f"{target}: block file contains CR"
    block = block.replace("\n", "\r\n").rstrip("\r\n")

    body = raw.rstrip("\r\n")
    new = body + "\r\n\r\n\r\n" + block + "\r\n"

    ast.parse(new)
    assert new.count("\n") == new.count("\r\n"), f"{target}: CRLF invariant broken"
    assert new.count("def _selftest() -> bool:") == 1, f"{target}: unexpected _selftest count"
    assert new.count("def _selftest_async() -> bool:") == 1, f"{target}: missing async selftest"
    path.write_bytes(new.encode("utf-8"))
    print(f"appended _selftest to {target}")

# --- strengthen network/__init__.py's package selftest -------------------------
path = NET / "__init__.py"
raw = path.read_bytes().decode("utf-8")
lf = raw.replace("\r\n", "\n")

if "for _module_name in (" in lf:
    print("skipped __init__.py (already strengthened)")
else:
    assert lf.count(INIT_ANCHOR) == 1, "package selftest anchor not found exactly once"
    out = lf.replace(INIT_ANCHOR, INIT_LOOP, 1)
    final = out.replace("\n", "\r\n")
    ast.parse(final)
    assert final.count("\n") == final.count("\r\n"), "__init__.py: CRLF invariant broken"
    assert final.count("def _selftest() -> bool:") == 1, "__init__.py: unexpected _selftest count"
    path.write_bytes(final.encode("utf-8"))
    print("strengthened network/__init__.py package selftest")

# --- report ---------------------------------------------------------------------
for name in list(TARGETS) + ["__init__.py"]:
    tree = ast.parse((NET / name).read_bytes().decode("utf-8"))
    has = any(
        isinstance(node, ast.FunctionDef) and node.name == "_selftest"
        for node in tree.body
    )
    print(f"  {name}: _selftest={'present' if has else 'MISSING'}")
    assert has, f"{name}: _selftest missing after patch"
print("done")
