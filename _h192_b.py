"""H192 applier B: opt/manager.py + opt/package.py selftests."""
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
# opt/manager.py
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "manager.py"
text, crlf = load(p)

selftest = '''def _selftest() -> bool:
    """Run basic self-tests for the high-level OptManager."""
    import tempfile

    print("[opt/manager] selftest \\u2026")

    with tempfile.TemporaryDirectory() as td:
        opt = Path(td) / "opt"
        etc = Path(td) / "etc-opt"
        var = Path(td) / "var-opt"
        manager = OptManager(str(opt), str(etc), str(var))

        payload = Path(td) / "tool"
        payload.write_bytes(b"tool-bytes")

        # 1  install records package, binary and config
        result = manager.install(
            "demo", "acme", binaries=[str(payload)], config={"debug": False}
        )
        assert result["success"] is True, result["errors"]
        assert (opt / "acme" / "demo" / "bin" / "tool").exists()
        assert (etc / "acme" / "demo" / "config.json").exists()
        print("  [PASS] install records package, binary and config")

        # 2  database list / get
        assert {p["name"] for p in manager.list()} == {"demo"}
        info = manager.get("demo", "acme")
        assert info["version"] == "1.0.0"
        assert info["provider"] == "acme"
        print("  [PASS] list / get read the package database")

        # 3  integrity is real: the manifest is written and verifies (H190)
        verification = manager.verify("demo", "acme")
        assert all(verification["integrity"].values()), verification
        print("  [PASS] verify checks the SHA3-512 manifest")

        # 4  statistics
        stats = manager.get_stats()
        assert stats["total_packages"] == 1
        assert stats["packages_with_provider"] == 1
        assert stats["packages_without_provider"] == 0
        print("  [PASS] get_stats")

        # 5  update bumps the version
        assert manager.update("demo", "acme", version="2.0.0")["success"] is True
        assert manager.get("demo", "acme")["version"] == "2.0.0"
        print("  [PASS] update bumps the version")

        # 6  structure creation without installing
        created = manager.create_package_structure("struct", "acme")
        assert (opt / "acme" / "struct" / "bin").is_dir()
        assert created["bin"] == opt / "acme" / "struct" / "bin"
        print("  [PASS] create_package_structure")

        # 7  traversal names are refused with no side effects (CWE-22)
        for bad in ("../../etc", ".."):
            bad_result = manager.install(bad)
            assert bad_result["success"] is False, bad_result
            assert bad_result["errors"]
            assert manager.remove(bad)["success"] is False
            try:
                manager.create_package_structure(bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"create_package_structure accepted {bad!r}")
        print("  [PASS] traversal package names are refused")

        # 8  install_binary_to_package reports errors instead of raising
        assert manager.install_binary_to_package("demo", str(payload), "acme").endswith(
            "tool"
        )
        assert manager.install_binary_to_package(
            "demo", str(Path(td) / "missing"), "acme"
        ).startswith("Error:")
        print("  [PASS] install_binary_to_package")

        # 9  cap-gate: install/remove are privileged, fail-closed when strict
        previous = gate.strict
        try:
            gate.set_strict(True)
            try:
                manager.install("gated")
            except PermissionError:
                pass
            else:
                raise AssertionError("install is not capability-gated")
            try:
                manager.remove("demo", "acme")
            except PermissionError:
                pass
            else:
                raise AssertionError("remove is not capability-gated")
        finally:
            gate.set_strict(previous)
        print("  [PASS] install / remove are capability-gated")

        # 10  remove clears package, etc/var trees and the database entry
        removed = manager.remove("demo", "acme")
        assert removed["success"] is True, removed["errors"]
        assert not (opt / "acme" / "demo").exists()
        assert not (etc / "acme" / "demo").exists()
        assert not (var / "acme" / "demo").exists()
        assert manager.get("demo", "acme") is None
        print("  [PASS] remove clears package, etc/var trees and database")

    print("[opt/manager] selftest PASSED")
    return True


'''
old_main = (
    'if __name__ == "__main__":\n'
    "    # Demo usage\n"
    "    import tempfile\n"
    "    import os\n"
)
assert text.count(old_main) == 1, "manager main anchor"
text = text.replace(
    old_main,
    'if __name__ == "__main__":\n'
    "    # Self-test first: fail fast if the subsystem regressed.\n"
    "    if not _selftest():\n"
    "        raise SystemExit(1)\n"
    "\n"
    "    # Demo usage\n"
    "    import tempfile\n"
    "    import os\n",
)
idx = text.index('if __name__ == "__main__":')
text = text[:idx] + selftest + text[idx:]
save(p, text, crlf)
print("opt/manager.py OK")

# ══════════════════════════════════════════════════════════════════════════
# opt/package.py
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "package.py"
text, crlf = load(p)

selftest = '''def _selftest() -> bool:
    """Run basic self-tests for OptPackage and the /opt package manager."""
    import tempfile

    print("[opt/package] selftest \\u2026")

    with tempfile.TemporaryDirectory() as td:
        opt = Path(td) / "opt"
        etc = Path(td) / "etc-opt"
        var = Path(td) / "var-opt"

        # 1  constructor builds the standard FHS layout
        pkg = OptPackage("demo", "acme", str(opt), str(etc), str(var))
        # safe_child resolves paths while tempfile hands back Windows 8.3
        # short names, so compare resolved forms (the H189 lesson)
        assert Path(str(pkg.base_path)).resolve() == (opt / "acme" / "demo").resolve()
        assert Path(str(pkg.etc_path)).resolve() == (etc / "acme" / "demo").resolve()
        assert Path(str(pkg.var_path)).resolve() == (var / "acme" / "demo").resolve()
        for path in (pkg.bin_path, pkg.lib_path, pkg.include_path, pkg.doc_path,
                     pkg.info_path, pkg.man_path, pkg.src_path):
            assert path.is_dir(), path
        assert all(pkg.check_structure().values())
        print("  [PASS] constructor builds the standard layout")

        # 2  traversal names/providers fail closed (CWE-22)
        for bad_name, bad_provider in (("../../etc", ""), ("ok", "../../etc"),
                                       ("..", ""), ("a/../../b", "")):
            try:
                OptPackage(bad_name, bad_provider, str(opt), str(etc), str(var))
            except PathTraversalError:
                pass
            else:
                raise AssertionError(
                    f"traversal accepted: {bad_name!r}/{bad_provider!r}"
                )
        print("  [PASS] traversal name/provider refused")

        # 3  install helpers
        source = Path(td) / "tool"
        source.write_bytes(b"tool")
        assert pkg.install_binary(str(source)) == pkg.bin_path / "tool"
        library = Path(td) / "lib.so"
        library.write_bytes(b"\\x00")
        assert pkg.install_library(str(library)) == pkg.lib_path / "lib.so"
        documentation = Path(td) / "README.md"
        documentation.write_text("# doc", encoding="utf-8")
        assert pkg.install_documentation(str(documentation)) == pkg.doc_path / "README.md"
        man_page = Path(td) / "tool.1"
        man_page.write_text(".TH TOOL 1", encoding="utf-8")
        assert pkg.install_man_page(str(man_page)) == pkg.man_path / "man1" / "tool.1"
        assert len(pkg.get_installed_files()) == 4
        print("  [PASS] install_binary/library/documentation/man_page")

        # 4  launcher/wrapper scripts quote every token (H187)
        launcher = pkg.create_launcher_script("run", "python3", ["-m", "demo; rm -rf /"])
        exec_line = [ln for ln in launcher.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("exec ")][0]
        tokens = shlex.split(exec_line)
        assert tokens[1:3] == ["python3", "-m"], tokens
        assert ";" not in tokens and "rm" not in tokens, tokens
        assert tokens[-1] == "$@"
        wrapper = pkg.create_wrapper_script(
            "wrap", "python3", environment={"MODE": "1"}, pre_args=["--flag"]
        )
        assert "export MODE='1'" in wrapper.read_text(encoding="utf-8")
        for bad_script in ("../escape.sh", "sub/dir.sh", "..", ""):
            try:
                pkg.create_launcher_script(bad_script, "true")
            except ValueError:
                pass
            else:
                raise AssertionError(f"unsafe script name accepted: {bad_script!r}")
        print("  [PASS] launcher/wrapper scripts quote every token")

        # 5  integrity: manifest verification detects tampering (H190)
        pkg.write_manifest()
        assert all(pkg.verify_integrity().values())
        victim = pkg.bin_path / "tool"
        original = victim.read_bytes()
        try:
            victim.write_bytes(b"evil")
            result = pkg.verify_integrity()
            assert result["unmodified"] is False, result
            assert pkg.integrity_details()["modified"] == ["bin/tool"]
        finally:
            victim.write_bytes(original)
        assert all(pkg.verify_integrity().values())
        print("  [PASS] manifest verification detects tampering")

        # 6  remove clears the tree and the manifest
        assert pkg.remove() is True
        assert not pkg.base_path.exists()
        assert not pkg.manifest_path.exists()
        print("  [PASS] remove clears package and manifest")

        # 7  OptManager: install/list/verify_all/stats/remove
        manager = OptManager(str(opt), str(etc), str(var))
        manager.install_package("alpha")
        manager.install_package("beta", "prov")
        assert {e["name"] for e in manager.list_packages()} == {"alpha", "beta"}
        assert manager.verify_all() == {"alpha": True, "prov/beta": True}
        assert manager.get_stats()["total_packages"] == 2
        assert manager.remove_package("alpha") is True
        assert manager.remove_package("../../etc") is False
        assert manager.remove_package("..") is False
        print("  [PASS] OptManager install/list/verify_all/remove")

        # 8  cap-gate: remove is privileged, fail-closed when strict
        gated = OptPackage("gated", "", str(opt), str(etc), str(var))
        previous = gate.strict
        try:
            gate.set_strict(True)
            try:
                gated.remove()
            except PermissionError:
                pass
            else:
                raise AssertionError("remove is not capability-gated")
            try:
                manager.install_package("gated")
            except PermissionError:
                pass
            else:
                raise AssertionError("install_package is not capability-gated")
        finally:
            gate.set_strict(previous)
        print("  [PASS] remove / install_package are capability-gated")

    print("[opt/package] selftest PASSED")
    return True


'''
old_main = 'if __name__ == "__main__":\n    # Demo usage\n    import tempfile\n'
assert text.count(old_main) == 1, "package main anchor"
text = text.replace(
    old_main,
    'if __name__ == "__main__":\n'
    "    # Self-test first: fail fast if the subsystem regressed.\n"
    "    if not _selftest():\n"
    "        raise SystemExit(1)\n"
    "\n"
    "    # Demo usage\n"
    "    import tempfile\n",
)
idx = text.index('if __name__ == "__main__":')
text = text[:idx] + selftest + text[idx:]
save(p, text, crlf)
print("opt/package.py OK")
