"""H192 applier A: opt/integration.py + opt/config.py."""
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
# opt/integration.py
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "integration.py"
text, crlf = load(p)

# F1: OptEnvironment._discover_packages - dead else, flat layout never seen
old = """        for item in self.opt_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a provider directory or a package
                if item.is_dir():
                    for subitem in item.iterdir():
                        if subitem.is_dir() and not subitem.name.startswith('.'):
                            packages.append(subitem)
                else:
                    packages.append(item)
"""
new = """        for item in sorted(self.opt_root.iterdir()):
            if not (item.is_dir() and not item.name.startswith('.')):
                continue
            # The previous `if item.is_dir():` was always true (the
            # enclosing test had already checked it), so the `else` was dead
            # code: the flat /opt/<pkg>/ layout was never discovered and every
            # *role* subdirectory (bin, lib, include, ...) was reported as a
            # package in its own right.
            if (item / "bin").is_dir():
                packages.append(item)
                continue
            for subitem in sorted(item.iterdir()):
                if subitem.is_dir() and not subitem.name.startswith('.'):
                    packages.append(subitem)
"""
text = sub(text, old, new, "integration F1 env discovery")

# F2: OptServiceManager.discover_services - same dead else
old = """        for item in self.opt_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a provider directory or a package
                if item.is_dir():
                    for subitem in item.iterdir():
                        if subitem.is_dir() and not subitem.name.startswith('.'):
                            self._discover_package_services(subitem, services)
                else:
                    self._discover_package_services(item, services)
"""
new = """        for item in sorted(self.opt_root.iterdir()):
            if not (item.is_dir() and not item.name.startswith('.')):
                continue
            # Same dead `else` as OptEnvironment._discover_packages above:
            # services in the flat /opt/<pkg>/ layout were never found.
            if (item / "bin").is_dir() or (item / "sbin").is_dir():
                self._discover_package_services(item, services)
                continue
            for subitem in sorted(item.iterdir()):
                if subitem.is_dir() and not subitem.name.startswith('.'):
                    self._discover_package_services(subitem, services)
"""
text = sub(text, old, new, "integration F2 service discovery")

# F3: module _selftest, inserted before the __main__ demo
selftest = '''def _selftest() -> bool:
    """Run basic self-tests for the /opt integration helpers."""
    import tempfile

    print("[opt/integration] selftest \\u2026")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "opt"
        (root / "demo" / "bin").mkdir(parents=True)
        (root / "demo" / "bin" / "demo").write_text("#!/bin/sh\\n", encoding="utf-8")
        (root / "prov" / "tool" / "bin").mkdir(parents=True)
        (root / "prov" / "tool" / "bin" / "tool").write_text("#!/bin/sh\\n", encoding="utf-8")

        # 1  OptEnvironment: PATH wiring and package variables
        env = OptEnvironment(str(root), system_path="/usr/bin")
        assert env.add_to_path("demo") is True
        assert env.add_to_path("missing") is False
        assert env.get_path_string().startswith(str(root / "demo" / "bin"))
        variables = env.setup_package_environment("demo")
        assert variables["OPT_PACKAGE_ROOT"] == str(root / "demo")
        assert variables["OPT_PACKAGE_BIN"] == str(root / "demo" / "bin")
        print("  [PASS] OptEnvironment PATH and package variables")

        # 2  discovery: flat AND provider layouts, no role dirs as packages
        found = env._discover_packages()
        assert sorted(p.name for p in found) == ["demo", "tool"], found
        print("  [PASS] OptEnvironment discovers flat and provider layouts")

        # 3  OptPathManager discovery
        path_manager = OptPathManager(str(root))
        assert set(path_manager.get_package_paths()) == {"demo", "tool"}
        print("  [PASS] OptPathManager discovers flat and provider layouts")

        # 4  generated profile script quotes every path (H188)
        script = path_manager.generate_profile_script()
        assert "export PATH=" in script
        assert "$(id)" not in script and "`" not in script
        assert str(root / "demo" / "bin").replace("\\\\", "/") in script
        print("  [PASS] generate_profile_script quotes every path")

        # 5  hostile package names are dropped, never interpolated (H188)
        (root / "evil$(id)" / "bin").mkdir(parents=True)
        assert "evil$(id)" not in path_manager.get_package_paths()
        print("  [PASS] shell-hostile package names are dropped")

        # 6  implicit mutation of the user's login file is refused (H188)
        try:
            OptPathManager(str(root)).install_profile_integration()
        except PermissionError:
            pass
        else:
            raise AssertionError("implicit ~/.bashrc mutation was allowed")
        print("  [PASS] implicit home-profile mutation refused")

        # 7  explicit profile path installs and uninstalls cleanly
        profile = Path(td) / "bashrc"
        explicit = OptPathManager(str(root), profile_path=str(profile))
        assert explicit.install_profile_integration() is True
        assert "UmerOS /opt PATH integration" in profile.read_text(encoding="utf-8")
        assert explicit._is_installed() is True
        assert explicit.uninstall_profile_integration() is True
        assert not explicit._is_installed()
        print("  [PASS] profile install/uninstall with an explicit path")

        # 8  OptServiceManager: flat-layout discovery + unknown services
        (root / "svc" / "bin").mkdir(parents=True)
        (root / "svc" / "bin" / "worker").write_text(
            "#!/bin/sh\\n# start stop restart status daemon\\n", encoding="utf-8"
        )
        services = OptServiceManager(str(root)).discover_services()
        assert "worker" in services, services
        manager = OptServiceManager(str(root))
        assert manager.start_service("nope") is False
        assert manager.stop_service("nope") is False
        assert manager.get_service_status("nope").startswith("Service not found")
        print("  [PASS] OptServiceManager discovery and unknown-service handling")

    print("[opt/integration] selftest PASSED")
    return True


'''
old_main = 'if __name__ == "__main__":\n    # Demo usage\n    import tempfile\n'
assert text.count(old_main) == 1, "integration main anchor"
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
# insert the selftest definition before the main block
idx = text.index('if __name__ == "__main__":')
text = text[:idx] + selftest + text[idx:]
save(p, text, crlf)
print("opt/integration.py OK")

# ══════════════════════════════════════════════════════════════════════════
# opt/config.py
# ══════════════════════════════════════════════════════════════════════════
p = ROOT / "opt" / "config.py"
text, crlf = load(p)

# F4: containment helper on OptIntegration
old = '''    def _ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for directory in [self.opt_root, self.etc_opt_root, self.var_opt_root]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def install_package(self, package_name: str, provider: str = "") -> Dict[str, Path]:
'''
new = '''    def _ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for directory in [self.opt_root, self.etc_opt_root, self.var_opt_root]:
            directory.mkdir(parents=True, exist_ok=True)

    def _require_contained(self, package_name: str, provider: str = "") -> None:
        """
        Refuse names that would escape a managed root (CWE-22).

        ``install_package``/``remove_package``/``get_package_paths`` used to
        build their paths with plain ``/`` joins, so a traversal name made
        them mkdir/rmtree *outside* /opt, /etc/opt and /var/opt.
        """
        try:
            for root in (self.opt_root, self.etc_opt_root, self.var_opt_root):
                if provider:
                    safe_child(safe_child(root, provider), package_name)
                else:
                    safe_child(root, package_name)
        except PathTraversalError as exc:
            raise ValueError(f"Refusing unsafe package path: {exc}")

    def install_package(self, package_name: str, provider: str = "") -> Dict[str, Path]:
'''
text = sub(text, old, new, "config F4 helper")

# F5: guard install_package
old = """        gate.require(CAP_FS_ADMIN)

        self._ensure_directories()
        
        if provider:
            package_path = self.opt_root / provider / package_name
"""
new = """        gate.require(CAP_FS_ADMIN)

        self._ensure_directories()
        self._require_contained(package_name, provider)

        if provider:
            package_path = self.opt_root / provider / package_name
"""
text = sub(text, old, new, "config F5 install_package guard")

# F6: guard remove_package (fail closed -> False)
old = """        gate.require(CAP_FS_ADMIN)

        import shutil
        
        if provider:
            opt_path = self.opt_root / provider / package_name
"""
new = """        gate.require(CAP_FS_ADMIN)

        try:
            self._require_contained(package_name, provider)
        except ValueError:
            # Fail closed: never rmtree outside the managed roots.
            return False

        import shutil

        if provider:
            opt_path = self.opt_root / provider / package_name
"""
text = sub(text, old, new, "config F6 remove_package guard")

# F7: guard get_package_paths
old = '''        Returns:
            Dictionary with all package paths
        """
        if provider:
            package_path = self.opt_root / provider / package_name
            etc_path = self.etc_opt_root / provider / package_name
            var_path = self.var_opt_root / provider / package_name
        else:
            package_path = self.opt_root / package_name
            etc_path = self.etc_opt_root / package_name
            var_path = self.var_opt_root / package_name
        
        return {
            "opt": package_path,
            "etc": etc_path,
            "var": var_path,
'''
new = '''        Returns:
            Dictionary with all package paths

        Raises:
            ValueError: if package_name/provider would escape a managed root.
        """
        self._require_contained(package_name, provider)
        if provider:
            package_path = self.opt_root / provider / package_name
            etc_path = self.etc_opt_root / provider / package_name
            var_path = self.var_opt_root / provider / package_name
        else:
            package_path = self.opt_root / package_name
            etc_path = self.etc_opt_root / package_name
            var_path = self.var_opt_root / package_name

        return {
            "opt": package_path,
            "etc": etc_path,
            "var": var_path,
'''
text = sub(text, old, new, "config F7 get_package_paths guard")

# F8: module _selftest + main wiring
selftest = '''def _selftest() -> bool:
    """Run basic self-tests for OptConfig and OptIntegration."""
    import tempfile

    print("[opt/config] selftest \\u2026")

    with tempfile.TemporaryDirectory() as td:
        opt = Path(td) / "opt"
        etc = Path(td) / "etc-opt"
        var = Path(td) / "var-opt"
        cfg = OptConfig(str(opt), str(etc))

        # 1  install + read back a configuration
        path = cfg.install_config("demo", {"version": "1.0.0", "debug": False})
        # safe_child resolves paths while tempfile hands back Windows 8.3
        # short names, so compare resolved forms (same trick as the H189 tests)
        assert Path(str(path)).resolve() == (etc / "demo" / "config.json").resolve(), path
        assert cfg.get_config("demo") == {"version": "1.0.0", "debug": False}
        print("  [PASS] install_config / get_config round-trip")

        # 2  unknown package reads as None, not an exception
        assert cfg.get_config("absent") is None
        print("  [PASS] unknown package reads as None")

        # 3  schema validation
        assert cfg.validate_config("demo") is True
        assert cfg.validate_config("demo", {"required": ["version"]}) is True
        assert cfg.validate_config("demo", {"required": ["nope"]}) is False
        assert cfg.validate_config("absent") is False
        print("  [PASS] validate_config with and without a schema")

        # 4  listing and removal
        assert "demo" in cfg.list_configs()
        assert cfg.remove_config("demo") is True
        assert cfg.get_config("demo") is None
        assert cfg.remove_config("demo") is False
        print("  [PASS] list_configs / remove_config")

        # 5  traversal is refused, nothing is written outside /etc/opt (CWE-22)
        for bad in ("../../etc", "..", "."):
            try:
                cfg.install_config(bad, {"x": 1})
            except ValueError:
                pass
            else:
                raise AssertionError(f"traversal package name accepted: {bad!r}")
        try:
            cfg.install_config("demo", {"x": 1}, config_file="../../../etc/passwd")
        except ValueError:
            pass
        else:
            raise AssertionError("traversal config file name accepted")
        assert cfg.get_config("../../etc") is None
        print("  [PASS] traversal names and config files are refused")

        # 6  OptIntegration: structure, markers, paths, listing, removal
        integration = OptIntegration(str(opt), str(etc), str(var))
        paths = integration.install_package("app", "acme")
        assert (opt / "acme" / "app" / "bin").is_dir()
        assert paths["etc"] == etc / "acme" / "app"
        markers = integration.setup_integration("app", "acme")
        assert markers == {"etc": True, "var": True}, markers
        assert (etc / "acme" / "app" / ".opt-integration").exists()
        assert (var / "acme" / "app" / ".opt-integration").exists()
        got = integration.get_package_paths("app", "acme")
        assert got["opt"] == opt / "acme" / "app"
        assert "acme" in integration.list_packages()
        print("  [PASS] OptIntegration structure / markers / paths / listing")

        # 7  OptIntegration traversal guards (CWE-22)
        for bad in ("../../etc", ".."):
            try:
                integration.install_package(bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"integration install accepted {bad!r}")
            assert integration.remove_package(bad) is False
            try:
                integration.get_package_paths(bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"integration get_package_paths accepted {bad!r}")
        print("  [PASS] OptIntegration refuses traversal names")

        # 8  removal clears all three trees
        assert integration.remove_package("app", "acme") is True
        assert not (opt / "acme" / "app").exists()
        assert not (etc / "acme" / "app").exists()
        assert not (var / "acme" / "app").exists()
        print("  [PASS] OptIntegration removal clears opt/etc/var")

        # 9  cap-gate: privileged writes are fail-closed when strict
        previous = gate.strict
        try:
            gate.set_strict(True)
            try:
                cfg.install_config("gated", {"x": 1})
            except PermissionError:
                pass
            else:
                raise AssertionError("install_config is not capability-gated")
            try:
                integration.install_package("gated")
            except PermissionError:
                pass
            else:
                raise AssertionError("integration install is not capability-gated")
        finally:
            gate.set_strict(previous)
        assert cfg.get_config("gated") is None
        print("  [PASS] install_config / install_package are capability-gated")

    print("[opt/config] selftest PASSED")
    return True


'''
old_main = 'if __name__ == "__main__":\n    # Demo usage\n    import sys\n'
assert text.count(old_main) == 1, "config main anchor"
text = text.replace(
    old_main,
    'if __name__ == "__main__":\n'
    "    # Self-test first: fail fast if the subsystem regressed.\n"
    "    if not _selftest():\n"
    "        raise SystemExit(1)\n"
    "\n"
    "    # Demo usage\n"
    "    import sys\n",
)
idx = text.index('if __name__ == "__main__":')
text = text[:idx] + selftest + text[idx:]
save(p, text, crlf)
print("opt/config.py OK")
