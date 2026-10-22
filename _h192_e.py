"""H192 applier E: package selftests run children + test_opt.py wiring."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(p: Path):
    raw = p.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def save(p: Path, text: str, crlf: bool) -> None:
    p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def sub(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    assert n == 1, f"{label}: expected 1 occurrence, found {n}"
    return text.replace(old, new)


# ══════════════════════════════════════════════════════════════════════════
# opt/__init__.py - run every child's selftest
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "__init__.py"
text, crlf = load(p)

old = '''def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"opt selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True
'''
new = '''# Modules whose own _selftest() the package selftest runs (H192).
_SELFTEST_MODULES = (
    "env", "fhs", "hierarchy", "var", "config",
    "integration", "manager", "package",
)


def _selftest() -> bool:
    """Verify the public surface is importable and every child passes."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"opt selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    # Run each child's own _selftest so one command checks the subsystem
    # instead of only the import surface.
    failures = []
    for mod_name in _SELFTEST_MODULES:
        try:
            module = importlib.import_module(f"{__name__}.{mod_name}")
        except ImportError as exc:
            failures.append(f"{mod_name}: {exc}")
            continue
        child = getattr(module, "_selftest", None)
        if child is not None and child() is not True:
            failures.append(mod_name)
    if failures:
        print(f"opt selftest FAIL: {failures}", file=sys.stderr)
        return False
    return True
'''
text = sub(text, old, new, "opt __init__ selftest")
save(p, text, crlf)
print("opt/__init__.py OK")

# ══════════════════════════════════════════════════════════════════════════
# opt/installers/__init__.py - run every installer's selftest
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "installers" / "__init__.py"
text, crlf = load(p)

old = '''def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"opt.installers selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True
'''
new = '''# Installer modules whose own _selftest() the package selftest runs (H192).
_SELFTEST_MODULES = ("sample_app", "web_server", "database", "development")


def _selftest() -> bool:
    """Verify the public surface is importable and every installer passes."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"opt.installers selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    # Run each installer's own _selftest so one command checks them all.
    failures = []
    for mod_name in _SELFTEST_MODULES:
        try:
            module = importlib.import_module(f"{__name__}.{mod_name}")
        except ImportError as exc:
            failures.append(f"{mod_name}: {exc}")
            continue
        child = getattr(module, "_selftest", None)
        if child is not None and child() is not True:
            failures.append(mod_name)
    if failures:
        print(f"opt.installers selftest FAIL: {failures}", file=sys.stderr)
        return False
    return True
'''
text = sub(text, old, new, "installers __init__ selftest")
save(p, text, crlf)
print("opt/installers/__init__.py OK")

# ══════════════════════════════════════════════════════════════════════════
# opt/test_opt.py - Test 9: run every module selftest, and register it
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "test_opt.py"
text, crlf = load(p)

test9 = '''def test_module_selftests():
    """Test 9: per-module _selftest() functions (H192)."""
    print("\\n" + "=" * 60)
    print("Test 9: Module Selftests")
    print("=" * 60)

    from opt import config as opt_config
    from opt import env as opt_env
    from opt import fhs as opt_fhs
    from opt import hierarchy as opt_hierarchy
    from opt import integration as opt_integration
    from opt import manager as opt_manager
    from opt import package as opt_package
    from opt import var as opt_var
    from opt.installers import database, development, sample_app, web_server

    modules = [
        ("opt.env", opt_env),
        ("opt.fhs", opt_fhs),
        ("opt.hierarchy", opt_hierarchy),
        ("opt.var", opt_var),
        ("opt.config", opt_config),
        ("opt.integration", opt_integration),
        ("opt.manager", opt_manager),
        ("opt.package", opt_package),
        ("opt.installers.sample_app", sample_app),
        ("opt.installers.web_server", web_server),
        ("opt.installers.database", database),
        ("opt.installers.development", development),
    ]

    for name, module in modules:
        assert hasattr(module, "_selftest"), f"{name} has no _selftest()"
        assert module._selftest() is True, f"{name} selftest failed"
        print(f"\\u2713 {name} selftest passed")

    return True


'''
anchor = "def run_all_tests():"
assert text.count(anchor) == 1, "test_opt runner anchor"
text = text.replace(anchor, test9 + anchor)

old = '''        ("Full Integration", test_integration),
    ]
'''
new = '''        ("Full Integration", test_integration),
        ("Module Selftests", test_module_selftests),
    ]
'''
text = sub(text, old, new, "test_opt runner registration")
save(p, text, crlf)
print("opt/test_opt.py OK")
