"""applier: append the four _selftest() blocks + strengthen the package one.

Every write is guarded: the module must not already define ``_selftest``, the
file must end with a newline, the result must re-parse, and the CRLF invariant
(``text.count("\\n") == text.count("\\r\\n")``) must still hold afterwards.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

NET = Path("UmerOS/network")

TARGETS = {
    "dns_resolver.py": "_h182_b1_dns.py",
    "tcp_server.py": "_h182_b2_tcp.py",
    "http_client.py": "_h182_b3_http.py",
    "network_stack.py": "_h182_b4_stack.py",
}


def load_block(script_name: str) -> str:
    """Read a block file and evaluate only its BLOCK constant."""
    source = Path("UmerOS") / script_name
    namespace: dict[str, str] = {}
    exec(compile(source.read_bytes().decode("utf-8"), str(source), "exec"), namespace)
    return namespace["BLOCK"]


for target, block_file in TARGETS.items():
    path = NET / target
    raw = path.read_bytes().decode("utf-8")

    assert "def _selftest" not in raw, f"{target}: already has a _selftest"
    assert raw.endswith("\r\n"), f"{target}: does not end with a newline"
    assert raw.count("\n") == raw.count("\r\n"), f"{target}: mixed line endings"

    block = load_block(block_file).replace("\n", "\r\n").rstrip("\r\n")
    assert "def _selftest" in block, f"{target}: block file has no _selftest"
    # The block must be pure LF before conversion (no accidental CRLF inside).
    assert "\r" not in load_block(block_file), f"{target}: block file has CR characters"

    body = raw.rstrip("\r\n")
    new = body + "\r\n\r\n\r\n" + block + "\r\n"

    ast.parse(new)
    assert new.count("\n") == new.count("\r\n"), f"{target}: CRLF invariant broken"
    assert new.count("def _selftest() -> bool:") == 1, f"{target}: unexpected _selftest count"
    assert new.count("def _selftest_async() -> bool:") == 1, f"{target}: missing async selftest"
    path.write_bytes(new.encode("utf-8"))
    print(f"appended _selftest to {target}")

# --- strengthen network/__init__.py's existing package selftest ---------------
path = NET / "__init__.py"
raw = path.read_bytes().decode("utf-8")
lf = raw.replace("\r\n", "\n")

old = '''    pkg = _il.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, name)]
    if missing:
        print(
            f"{__name__} selftest FAIL: missing {missing}",
            file=_sys.stderr,
        )
        return False
    return True
'''
assert lf.count(old) == 1, "package selftest body not found exactly once"

new = '''    pkg = _il.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, name)]
    if missing:
        print(
            f"{__name__} selftest FAIL: missing {missing}",
            file=_sys.stderr,
        )
        return False

    # H182: every leaf module now carries its own ``_selftest()``, so run them
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
'''
out = lf.replace(old, new, 1)
final = out.replace("\n", "\r\n")
ast.parse(final)
assert final.count("\n") == final.count("\r\n"), "__init__.py: CRLF invariant broken"
assert final.count("def _selftest") == 1, "__init__.py: unexpected _selftest count"
path.write_bytes(final.encode("utf-8"))
print("strengthened network/__init__.py package selftest")

# --- report -------------------------------------------------------------------
for name in list(TARGETS) + ["__init__.py"]:
    tree = ast.parse((NET / name).read_bytes().decode("utf-8"))
    has = any(
        isinstance(node, ast.FunctionDef) and node.name == "_selftest"
        for node in tree.body
    )
    print(f"  {name}: _selftest={'present' if has else 'MISSING'}")
    assert has, f"{name}: _selftest missing after patch"
print("done")
