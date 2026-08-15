"""
Comprehensive Test Suite for UmerOS /sources Subsystem
======================================================

Verifies bibliography, System V signals, architecture glossary, kernel docs,
and source tree management.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root and sources folder to sys.path
_src_dir = Path(__file__).resolve().parent
_root_dir = _src_dir.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


def test_imports() -> bool:
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)
    try:
        import sources
        from sources import (
            BibliographyRegistry,
            SourceCategory,
            SourceReference,
            SYSTEM_V_SIGNALS,
            SignalDispatcher,
            SignalAction,
            GlossaryRegistry,
            GlossaryEntry,
            KernelDocsRegistry,
            SourceTreeManager,
            SourcesManager,
        )
        print("[OK] All /sources modules and classes imported successfully.")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_bibliography() -> bool:
    print("\n" + "=" * 60)
    print("Test 2: Bibliography Registry & BibTeX Export")
    print("=" * 60)
    from sources.bibliography import BibliographyRegistry, SourceCategory

    reg = BibliographyRegistry()
    all_sources = reg.list_all()
    assert len(all_sources) >= 15, "Expected at least 15 canonical citations"

    # Search
    kern = reg.get("kernighan1984unix")
    assert kern is not None
    assert "Brian W. Kernighan" in kern.authors
    assert kern.category == SourceCategory.BOOK

    search_res = reg.search("kernel")
    assert len(search_res) >= 3

    # BibTeX export
    bibtex = reg.export(format_type="bibtex")
    assert "@book{kernighan1984unix," in bibtex
    assert "@misc{fhs_spec," in bibtex

    # Markdown export
    md = reg.export(format_type="markdown")
    assert "# Linux Filesystem Hierarchy" in md

    print(f"[OK] Bibliography catalog ({len(all_sources)} entries) and BibTeX/MD exports verified.")
    return True


def test_signals() -> bool:
    print("\n" + "=" * 60)
    print("Test 3: UNIX System V & POSIX Signals Engine")
    print("=" * 60)
    from sources.signals import SignalDispatcher, SignalAction, SYSTEM_V_SIGNALS

    dispatcher = SignalDispatcher()

    # Verify standard signal numbers and names
    assert len(SYSTEM_V_SIGNALS) == 31
    assert SYSTEM_V_SIGNALS[1].name == "SIGHUP"
    assert SYSTEM_V_SIGNALS[2].name == "SIGINT"
    assert SYSTEM_V_SIGNALS[9].name == "SIGKILL"
    assert not SYSTEM_V_SIGNALS[9].can_catch
    assert SYSTEM_V_SIGNALS[11].name == "SIGSEGV"
    assert SYSTEM_V_SIGNALS[11].action == SignalAction.CORE_DUMP
    assert SYSTEM_V_SIGNALS[15].name == "SIGTERM"

    # Handler registration
    handled_signals = []

    def custom_term_handler(signum, ctx):
        handled_signals.append(signum)

    dispatcher.register_handler("SIGTERM", custom_term_handler)
    res = dispatcher.send_signal(pid=1234, signum="SIGTERM")
    assert res["success"]
    assert res["action"] == "handled_by_custom_callback"
    assert 15 in handled_signals

    # Uncatchable signal check
    try:
        dispatcher.register_handler("SIGKILL", custom_term_handler)
        assert False, "Should not allow catching SIGKILL"
    except PermissionError:
        pass

    # Default action
    res_int = dispatcher.send_signal(pid=5678, signum="SIGINT")
    assert res_int["action"] == "default_term"

    print("[OK] System V Signals (1-31), handlers, and dispatching verified.")
    return True


def test_glossary() -> bool:
    print("\n" + "=" * 60)
    print("Test 4: Architecture Glossary Registry")
    print("=" * 60)
    from sources.glossary import GlossaryRegistry

    reg = GlossaryRegistry()
    terms = reg.list_all()
    assert len(terms) >= 45

    # Lookup
    fhs = reg.get("FHS")
    assert fhs is not None
    assert "Filesystem Hierarchy Standard" in fhs.definition

    inode = reg.get("inode")
    assert inode is not None
    assert "Index node" in inode.definition

    # Search
    boot_terms = reg.filter_by_category("boot")
    assert len(boot_terms) >= 3

    print(f"[OK] Glossary registry ({len(terms)} terms) and queries verified.")
    return True


def test_kernel_docs() -> bool:
    print("\n" + "=" * 60)
    print("Test 5: Kernel Documentation Specifications Parser")
    print("=" * 60)
    from sources.specs_parser import KernelDocsRegistry

    docs = KernelDocsRegistry.list_docs()
    assert "proc.txt" in docs
    assert "initrd.txt" in docs
    assert "runlevels" in docs

    proc = KernelDocsRegistry.get_doc("proc.txt")
    assert proc is not None
    assert "1.1 /proc/cpuinfo" in proc["sections"]
    assert "1.2 /proc/meminfo" in proc["sections"]

    initrd = KernelDocsRegistry.get_doc("initrd.txt")
    assert "pivot_root" in initrd["sections"]["2. pivot_root Operation"]

    search_res = KernelDocsRegistry.search_docs("runlevel")
    assert len(search_res) >= 1

    print("[OK] Kernel specifications (proc.txt, initrd.txt, runlevels) verified.")
    return True


def test_source_tree() -> bool:
    print("\n" + "=" * 60)
    print("Test 6: Source Tree Manager (/usr/src)")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        src_root = (Path(tmpdir) / "src").resolve()
        from sources.source_tree import SourceTreeManager

        stm = SourceTreeManager(src_root=src_root)
        skeletons = stm.bootstrap()

        assert (src_root / "linux" / "Documentation").exists()
        assert (src_root / "linux" / "drivers").exists()
        assert (src_root / "packages" / "SPECS").exists()
        assert (src_root / "debug").exists()

        # Add dummy source file and search
        sample = src_root / "linux" / "kernel" / "main.c"
        sample.write_text("void umeros_kernel_init(void) { return; }\n", encoding="utf-8")

        matches = stm.search_source_code("umeros_kernel_init")
        assert len(matches) == 1
        assert matches[0]["line_number"] == 1

        print("[OK] SourceTreeManager (/usr/src layout and search) verified.")
        return True


def test_sources_manager_master() -> bool:
    print("\n" + "=" * 60)
    print("Test 7: SourcesManager Master Unified Controller")
    print("=" * 60)
    from sources.manager import SourcesManager

    mgr = SourcesManager()
    summary = mgr.get_summary()

    assert summary["total_bibliography_sources"] >= 15
    assert summary["total_glossary_terms"] >= 45
    assert summary["total_signals_defined"] == 31
    assert summary["total_kernel_specs"] >= 3

    # Unified search
    res = mgr.search_all("initrd")
    assert res["total_matches"] >= 2
    assert len(res["bibliography"]) >= 1
    assert len(res["glossary"]) >= 1
    assert len(res["kernel_docs"]) >= 1

    print("[OK] SourcesManager master coordinator and unified search verified.")
    return True


def test_cli() -> bool:
    print("\n" + "=" * 60)
    print("Test 8: CLI Execution (sources_ctl)")
    print("=" * 60)
    from sources.cli import main as cli_main

    assert cli_main(["summary"]) == 0
    assert cli_main(["list"]) == 0
    assert cli_main(["signals"]) == 0
    assert cli_main(["signals", "SIGINT"]) == 0
    assert cli_main(["glossary", "FHS"]) == 0
    assert cli_main(["kernel-doc", "proc.txt"]) == 0
    assert cli_main(["search", "kernel"]) == 0

    print("[OK] CLI commands executed successfully.")
    return True


def run_all_tests() -> bool:
    tests = [
        test_imports,
        test_bibliography,
        test_signals,
        test_glossary,
        test_kernel_docs,
        test_source_tree,
        test_sources_manager_master,
        test_cli,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            if t():
                passed += 1
            else:
                failed += 1
        except Exception as ex:
            print(f"[FAIL] Exception in {t.__name__}: {ex}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} PASSED, {failed} FAILED (Total: {len(tests)})")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
