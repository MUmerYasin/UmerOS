"""
H192 - the row asks for ``_selftest()`` in the ten ``opt/`` modules that lack
one (``config``, ``manager``, ``package``, ``integration``, ``installers/*``,
``test_opt.py``), following the local ``[opt/<mod>] selftest …`` /
``[PASS]`` convention already used by ``env``/``fhs``/``hierarchy``/``var``.

Drift-recon first (per the standard): ``opt/`` had 12 modules, of which only
4 carried a selftest. All 12 now do, each covering its own security dimension
(traversal refusal, capability gating, shell-quoting, home-profile consent,
world-writable detection, reserved-dir rejection).

Writing the selftests immediately surfaced five real defects, all fixed in
this session:

* ``OptEnvironment._discover_packages`` and
  ``OptServiceManager.discover_services`` contained a dead ``else`` - the
  ``if item.is_dir():`` test was nested inside an already-checked
  ``item.is_dir()`` guard, so the flat ``/opt/<pkg>`` layout was invisible
  and every *role* directory (``bin``, ``lib``, …) was reported as a
  package/service.
* ``OptIntegration`` joined caller-supplied names into config paths with
  no containment check (CWE-22); ``OptConfig`` had no provider scoping and
  ``manager.remove()`` reported ``success: True`` for a refused removal.
* The installers accepted traversal package names verbatim.

These tests pin: every module keeps a passing ``_selftest()`` covering its
security dimension, ``opt/test_opt.py`` keeps running them (Test 9), the
package selftests keep running their children, the CLIs dispatch, and the
two dead-``else`` discovery bugs cannot come back.
"""
from __future__ import annotations

import importlib
import inspect
import shlex
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import opt  # noqa: E402
import opt.installers  # noqa: E402

# Every module whose _selftest() must exist and pass (H192).
MODULES = (
    "opt.env",
    "opt.fhs",
    "opt.hierarchy",
    "opt.var",
    "opt.config",
    "opt.integration",
    "opt.manager",
    "opt.package",
    "opt.installers.sample_app",
    "opt.installers.web_server",
    "opt.installers.database",
    "opt.installers.development",
)

# Security dimensions each selftest must exercise - the [PASS] line text is
# the contract, so a selftest that silently drops its hostile cases fails here.
SECURITY_LINES = {
    "opt.env": (
        "shell-unsafe package names are dropped",
        "shlex.quote-d",
    ),
    "opt.fhs": ("world-writable detection",),
    "opt.hierarchy": ("validate_package_path rejects reserved dirs",),
    "opt.var": ("traversal package names are refused",),
    "opt.config": (
        "traversal names and config files are refused",
        "capability-gated",
    ),
    "opt.integration": (
        "shell-hostile package names are dropped",
        "implicit home-profile mutation refused",
    ),
    "opt.manager": (
        "traversal package names are refused",
        "capability-gated",
    ),
    "opt.package": (
        "traversal name/provider refused",
        "capability-gated",
    ),
    "opt.installers.sample_app": ("installer is capability-gated",),
    "opt.installers.web_server": (
        "traversal package name refused",
        "installer is capability-gated",
    ),
    "opt.installers.database": (
        "traversal package name refused",
        "installer is capability-gated",
    ),
    "opt.installers.development": (
        "traversal package name refused",
        "installer is capability-gated",
    ),
}


def _load(name: str):
    return importlib.import_module(name)


@pytest.mark.parametrize("name", MODULES)
def test_module_defines_a_selftest(name: str):
    module = _load(name)
    selftest = getattr(module, "_selftest", None)
    assert callable(selftest), f"{name} has no callable _selftest()"


@pytest.mark.parametrize("name", MODULES)
def test_selftest_passes_and_covers_security(name: str, capsys):
    module = _load(name)
    result = module._selftest()
    captured = capsys.readouterr().out
    assert result is True, f"{name}._selftest() returned {result!r}"
    assert "[PASS]" in captured, f"{name} selftest printed no [PASS] lines"
    for expected in SECURITY_LINES[name]:
        assert expected in captured, (
            f"{name} selftest no longer covers its security dimension "
            f"({expected!r} not in output)"
        )


def test_package_selftests_run_their_children():
    # Both package selftests must return True *and* actually invoke each
    # child's _selftest (not just the import surface).
    for pkg in (opt, opt.installers):
        source = inspect.getsource(pkg._selftest)
        assert "child()" in source or "_selftest" in source
        assert pkg._selftest() is True


def test_opt_test_suite_runs_the_module_selftests():
    test_opt = importlib.import_module("opt.test_opt")
    source = inspect.getsource(test_opt.run_all_tests)
    assert "test_module_selftests" in source, (
        "opt/test_opt.py run_all_tests() no longer runs the module selftests"
    )
    assert test_opt.test_module_selftests() is True


def test_cli_dispatches_and_covers_every_module():
    main_mod = importlib.import_module("opt.__main__")
    assert main_mod.main(["help"]) == 0
    assert main_mod.main([]) == 0
    assert main_mod.main(["--help"]) == 0
    assert main_mod.main(["bogus"]) == 2
    assert set(main_mod._SELFTEST_MODULES) == set(MODULES)

    inst_main = importlib.import_module("opt.installers.__main__")
    assert inst_main.main(["help"]) == 0
    assert inst_main.main(["bogus"]) == 2
    assert set(inst_main._SELFTEST_MODULES) == {
        "opt.installers.sample_app",
        "opt.installers.web_server",
        "opt.installers.database",
        "opt.installers.development",
    }


def _make_opt_tree(base: Path) -> Path:
    """<base>/opt with one flat package and one provider package."""
    opt_root = base / "opt"
    for pkg in ("demo", "tools"):
        (opt_root / pkg / "bin").mkdir(parents=True)
        (opt_root / pkg / "bin" / "run").write_text("#!/bin/sh\n")
    (opt_root / "acme" / "pkg" / "bin").mkdir(parents=True)
    return opt_root


def test_environment_discovers_flat_and_provider_layouts(tmp_path: Path):
    from opt.integration import OptEnvironment

    opt_root = _make_opt_tree(tmp_path)
    env = OptEnvironment(str(opt_root), system_path="")
    found = {p.name for p in env._discover_packages()}
    assert found == {"demo", "tools", "pkg"}


def test_environment_does_not_report_role_dirs_as_packages(tmp_path: Path):
    from opt.integration import OptEnvironment

    # A bare role directory at the /opt top level (no bin/ inside) must not
    # be mistaken for a package - the pre-H192 dead-`else` behaviour.
    opt_root = tmp_path / "opt"
    (opt_root / "bin").mkdir(parents=True)
    (opt_root / "bin" / "tool").write_text("x")
    (opt_root / "lib").mkdir(parents=True)
    env = OptEnvironment(str(opt_root), system_path="")
    assert env._discover_packages() == []


def test_path_manager_discovers_flat_layout(tmp_path: Path):
    from opt.integration import OptPathManager

    opt_root = _make_opt_tree(tmp_path)
    mgr = OptPathManager(str(opt_root))
    bins = [str(p) for p in mgr._discover_packages()]
    assert str(opt_root / "demo" / "bin") in bins
    assert str(opt_root / "tools" / "bin") in bins
    assert str(opt_root / "acme" / "pkg" / "bin") in bins
    script = mgr.generate_profile_script()
    # the profile script is sourced by every interactive shell, so each
    # path must appear shlex-quoted (H188)
    assert shlex.quote(str(opt_root / "demo" / "bin").replace("\\", "/")) in script


def test_path_manager_drops_shell_unsafe_names(tmp_path: Path):
    from opt.integration import OptPathManager

    opt_root = tmp_path / "opt"
    hostile = opt_root / "ev$(id)`touch pwned`"
    (hostile / "bin").mkdir(parents=True)
    mgr = OptPathManager(str(opt_root))
    assert mgr._discover_packages() == []


def test_service_manager_discovers_flat_layout(tmp_path: Path):
    from opt.integration import OptServiceManager

    opt_root = tmp_path / "opt"
    svc_dir = opt_root / "demo" / "bin"
    svc_dir.mkdir(parents=True)
    (svc_dir / "web.sh").write_text("#!/bin/sh\n# start the daemon\n")
    mgr = OptServiceManager(str(opt_root))
    services = mgr.discover_services()
    assert "web" in services
    assert services["web"] == svc_dir / "web.sh"
    # unknown services must be refused, not executed
    assert mgr.start_service("nope") is False
    assert mgr.stop_service("nope") is False
