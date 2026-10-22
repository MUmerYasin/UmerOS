"""H192 applier D: remove() success reporting + installer guards/selftests."""
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
# 1. opt/config.py - fix my own selftest assertion (debug key was dropped)
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "config.py"
text, crlf = load(p)
old = '''        assert cfg.get_config("demo", provider="acme") == {"version": "2.0.0"}
        assert cfg.get_config("demo") == {"version": "1.0.0"}
'''
new = '''        assert cfg.get_config("demo", provider="acme") == {"version": "2.0.0"}
        assert cfg.get_config("demo") == {"version": "1.0.0", "debug": False}
'''
text = sub(text, old, new, "config selftest 1b")
save(p, text, crlf)
print("opt/config.py assertion fixed")

# ══════════════════════════════════════════════════════════════════════════
# 2. opt/manager.py - a REFUSED removal must not report success
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "manager.py"
text, crlf = load(p)
marker = 'result["errors"].append(f"Removal failed: {str(e)}")'
assert text.count(marker) == 1
i = text.index(marker)
needle = 'result["success"] = True'
j = text.rindex(needle, 0, i)
text = (
    text[:j]
    + "result[\"success\"] = not result[\"errors\"]"
    + text[j + len(needle):]
)
# document the change at the assignment site
old = '''            result["success"] = not result["errors"]
            
        except Exception as e:
            result["errors"].append(f"Removal failed: {str(e)}")'''
new = '''            # A refused (traversal) or failed removal must not report
            # success: callers gate on this flag.
            result["success"] = not result["errors"]

        except Exception as e:
            result["errors"].append(f"Removal failed: {str(e)}")'''
text = sub(text, old, new, "manager remove success comment")
save(p, text, crlf)
print("opt/manager.py remove() success reporting fixed")

# ══════════════════════════════════════════════════════════════════════════
# 3. the four installers: CWE-22 name guard (where named) + _selftest
# ══════════════════════════════════════════════════════════════════════════
GUARD = '''        # Contain the package name: it is used both as a directory and as a
        # file name below it, so a traversal name would write outside the
        # managed root (CWE-22).
        if {var} in (".", "..") or "/" in {var} or "\\\\" in {var}:
            result["errors"].append(f"Refusing unsafe package name: {{{var}!r}}")
            return result

'''

SELFTESTS = {
    "database": dict(
        var="db_name", func="install_database", pkg="database",
        label="database", extra_name="custom-db",
    ),
    "development": dict(
        var="tools_name", func="install_development_tools", pkg="devtools",
        label="development tools", extra_name="custom-tools",
    ),
    "web_server": dict(
        var="web_server_name", func="install_web_server", pkg="webserver",
        label="web server", extra_name="custom-web",
    ),
}

for stem, spec in SELFTESTS.items():
    p = ROOT / "opt" / "installers" / f"{stem}.py"
    text, crlf = load(p)
    var, func, pkg = spec["var"], spec["func"], spec["pkg"]

    # guard before the first path construction from the name
    anchor = f'        result["installed_at"] = str(opt_root_path / {var})'
    assert text.count(anchor) == 1, f"{stem}: installed_at anchor"
    text = text.replace(anchor, GUARD.format(var=var) + anchor)

    selftest = f'''def _selftest() -> bool:
    """Run basic self-tests for the {spec['label']} installer."""
    import tempfile

    print("[opt/installers/{stem}] selftest \\u2026")

    with tempfile.TemporaryDirectory() as td:
        opt = Path(td) / "opt"
        etc = Path(td) / "etc-opt"
        var_root = Path(td) / "var-opt"

        # 1  a full install succeeds and creates the standard layout
        result = {func}(str(opt), str(etc), str(var_root), verbose=False)
        assert result["success"] is True, result["errors"]
        assert result["errors"] == []
        assert (opt / "{pkg}" / "bin" / "{pkg}").exists()
        for role in ("bin", "lib", "include", "doc", "info", "man", "src"):
            assert (opt / "{pkg}" / role).is_dir(), role
        assert (etc / "{pkg}" / "config.json").exists()
        assert (var_root / "{pkg}" / ".opt-integration").exists()
        print("  [PASS] installer creates the full /opt layout")

        # 2  a custom package name is honoured
        named = {func}(
            str(opt), str(etc), str(var_root),
            {var}="{spec['extra_name']}", verbose=False,
        )
        assert named["success"] is True, named["errors"]
        assert (opt / "{spec['extra_name']}" / "bin" / "{spec['extra_name']}").exists()
        print("  [PASS] custom package name honoured")

        # 3  idempotent
        again = {func}(str(opt), str(etc), str(var_root), verbose=False)
        assert again["success"] is True, again["errors"]
        print("  [PASS] installer is idempotent")

        # 4  traversal names are refused, nothing escapes the root (CWE-22)
        escape = {func}(
            str(opt), str(etc), str(var_root),
            {var}="../../pwned-escape", verbose=False,
        )
        assert escape["success"] is False
        assert escape["errors"]
        assert not (opt / ".." / ".." / "pwned-escape").resolve().exists()
        print("  [PASS] traversal package name refused")

        # 5  cap-gate: the installer's privileged writes fail closed
        from core.capability_gate import gate as _gate
        previous = _gate.strict
        try:
            _gate.set_strict(True)
            gated = {func}(
                str(opt), str(etc), str(var_root),
                {var}="gated-{pkg}", verbose=False,
            )
            assert gated["success"] is False, "installer bypassed the capability gate"
            assert gated["errors"], "gate denial not reported"
        finally:
            _gate.set_strict(previous)
        print("  [PASS] installer is capability-gated")

    print("[opt/installers/{stem}] selftest PASSED")
    return True


'''
    old_main = f'if __name__ == "__main__":\n    {func}(verbose=True)\n'
    assert text.count(old_main) == 1, f"{stem}: main anchor"
    text = text.replace(
        old_main,
        'if __name__ == "__main__":\n'
        "    # Self-test first: fail fast if the installer regressed.\n"
        "    if not _selftest():\n"
        "        raise SystemExit(1)\n"
        f"    {func}(verbose=True)\n",
    )
    idx = text.index('if __name__ == "__main__":')
    text = text[:idx] + selftest + text[idx:]
    save(p, text, crlf)
    print(f"opt/installers/{stem}.py OK")

# ══════════════════════════════════════════════════════════════════════════
# 4. sample_app.py: name is a literal, so only the selftest is needed
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "installers" / "sample_app.py"
text, crlf = load(p)
selftest = '''def _selftest() -> bool:
    """Run basic self-tests for the sample-app installer."""
    import tempfile

    print("[opt/installers/sample_app] selftest \\u2026")

    with tempfile.TemporaryDirectory() as td:
        opt = Path(td) / "opt"
        etc = Path(td) / "etc-opt"
        var_root = Path(td) / "var-opt"

        # 1  a full install succeeds and creates the standard layout
        result = install_sample_app(str(opt), str(etc), str(var_root), verbose=False)
        assert result["success"] is True, result["errors"]
        assert result["errors"] == []
        assert (opt / "sample-app" / "bin" / "sample-app").exists()
        for role in ("bin", "lib", "include", "doc", "info", "man", "src"):
            assert (opt / "sample-app" / role).is_dir(), role
        assert (etc / "sample-app" / "config.json").exists()
        assert (var_root / "sample-app" / ".opt-integration").exists()
        assert (opt / "sample-app" / "man" / "man1" / "sample-app.1").exists()
        print("  [PASS] installer creates the full /opt layout")

        # 2  idempotent
        again = install_sample_app(str(opt), str(etc), str(var_root), verbose=False)
        assert again["success"] is True, again["errors"]
        print("  [PASS] installer is idempotent")

        # 3  cap-gate: the installer's privileged writes fail closed
        from core.capability_gate import gate as _gate
        previous = _gate.strict
        try:
            _gate.set_strict(True)
            gated = install_sample_app(
                str(opt), str(etc), str(var_root), verbose=False
            )
            assert gated["success"] is False, "installer bypassed the capability gate"
            assert gated["errors"], "gate denial not reported"
        finally:
            _gate.set_strict(previous)
        print("  [PASS] installer is capability-gated")

    print("[opt/installers/sample_app] selftest PASSED")
    return True


'''
old_main = 'if __name__ == "__main__":\n    install_sample_app(verbose=True)\n'
assert text.count(old_main) == 1, "sample_app main anchor"
text = text.replace(
    old_main,
    'if __name__ == "__main__":\n'
    "    # Self-test first: fail fast if the installer regressed.\n"
    "    if not _selftest():\n"
    "        raise SystemExit(1)\n"
    "    install_sample_app(verbose=True)\n",
)
idx = text.index('if __name__ == "__main__":')
text = text[:idx] + selftest + text[idx:]
save(p, text, crlf)
print("opt/installers/sample_app.py OK")
