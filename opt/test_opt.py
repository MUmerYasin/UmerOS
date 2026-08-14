#!/usr/bin/env python3
"""
Comprehensive Test Suite for UmerOS /opt Package Management System

This test script verifies the functionality of the /opt implementation
according to Linux Filesystem Hierarchy standards.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)
    
    try:
        from opt import OptManager, OptPackage, OptConfig
        from opt.manager import OptManager
        from opt.package import OptPackage, OptManager as PackageOptManager
        from opt.config import OptConfig, OptIntegration
        from opt.integration import OptEnvironment, OptPathManager, OptServiceManager
        
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_opt_package():
    """Test OptPackage class."""
    print("\n" + "=" * 60)
    print("Test 2: OptPackage Class")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        
        try:
            from opt.package import OptPackage
            
            # Create package
            package = OptPackage("testapp", opt_root=str(opt_root))
            
            # Verify directory structure
            assert package.base_path.exists(), "Package base path not created"
            assert package.bin_path.exists(), "bin directory not created"
            assert package.lib_path.exists(), "lib directory not created"
            assert package.include_path.exists(), "include directory not created"
            assert package.doc_path.exists(), "doc directory not created"
            assert package.info_path.exists(), "info directory not created"
            assert package.man_path.exists(), "man directory not created"
            assert package.src_path.exists(), "src directory not created"
            
            print("✓ Package directory structure created")
            
            # Create demo binary
            demo_bin = Path(tmpdir) / "demo_app.py"
            demo_bin.write_text('#!/usr/bin/env python3\nprint("Demo")\n')
            
            # Install binary
            installed = package.install_binary(str(demo_bin), "demo")
            assert installed.exists(), "Binary not installed"
            assert os.access(installed, os.X_OK), "Binary not executable"
            
            print("✓ Binary installation successful")
            
            # Create demo documentation
            demo_doc = Path(tmpdir) / "README.md"
            demo_doc.write_text("# Test Documentation\n")
            
            # Install documentation
            installed_doc = package.install_documentation(str(demo_doc))
            assert installed_doc.exists(), "Documentation not installed"
            
            print("✓ Documentation installation successful")
            
            # Create launcher script
            launcher = package.create_launcher_script("launch-demo", "python3", ["-m", "demo"])
            assert launcher.exists(), "Launcher not created"
            assert os.access(launcher, os.X_OK), "Launcher not executable"
            
            print("✓ Launcher script creation successful")
            
            # Verify integrity
            integrity = package.verify_integrity()
            assert all(integrity.values()), f"Integrity check failed: {integrity}"
            
            print("✓ Integrity verification successful")
            
            # Test removal
            removed = package.remove()
            assert removed, "Package removal failed"
            assert not package.base_path.exists(), "Package still exists after removal"
            
            print("✓ Package removal successful")
            
            return True
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_opt_manager():
    """Test OptManager class."""
    print("\n" + "=" * 60)
    print("Test 3: OptManager Class")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        
        try:
            from opt.manager import OptManager
            
            # Create manager
            manager = OptManager(str(opt_root))
            
            # Create demo files
            demo_bin = Path(tmpdir) / "demo.py"
            demo_bin.write_text('#!/usr/bin/env python3\nprint("Demo")\n')
            
            demo_doc = Path(tmpdir) / "README.md"
            demo_doc.write_text("# Test Documentation\n")
            
            # Install package
            result = manager.install(
                "testapp",
                binaries=[str(demo_bin)],
                documents=[str(demo_doc)]
            )
            
            assert result["success"], f"Installation failed: {result['errors']}"
            assert Path(result["paths"]["package"]).exists(), "Package directory not created"
            
            print("✓ Package installation successful")
            
            # List packages
            packages = manager.list()
            assert len(packages) > 0, "No packages listed"
            assert any(p["name"] == "testapp" for p in packages), "testapp not in list"
            
            print("✓ Package listing successful")
            
            # Verify all packages
            results = manager.verify()
            assert "testapp" in results, "testapp not in verification results"
            
            print("✓ Package verification successful")
            
            # Get statistics
            stats = manager.get_stats()
            assert stats["total_packages"] > 0, "No packages in stats"
            
            print("✓ Statistics retrieval successful")
            
            # Remove package
            result = manager.remove("testapp")
            assert result["success"], "Package removal failed"
            
            print("✓ Package removal successful")
            
            return True
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_opt_config():
    """Test OptConfig class."""
    print("\n" + "=" * 60)
    print("Test 4: OptConfig Class")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        etc_opt_root = Path(tmpdir) / "etc_opt"
        
        try:
            from opt.config import OptConfig
            
            # Create config manager
            config = OptConfig(str(opt_root), str(etc_opt_root))
            
            # Install configuration
            config_data = {
                "version": "1.0.0",
                "settings": {
                    "debug": False,
                    "port": 8080
                }
            }
            
            config_path = config.install_config("testapp", config_data)
            assert config_path.exists(), "Configuration not installed"
            
            print("✓ Configuration installation successful")
            
            # Get configuration
            retrieved = config.get_config("testapp")
            assert retrieved is not None, "Configuration not retrieved"
            assert retrieved["version"] == "1.0.0", "Version mismatch"
            assert retrieved["settings"]["port"] == 8080, "Port mismatch"
            
            print("✓ Configuration retrieval successful")
            
            # List configs
            configs = config.list_configs()
            assert "testapp" in configs, "testapp not in config list"
            
            print("✓ Configuration listing successful")
            
            # Remove configuration
            removed = config.remove_config("testapp")
            assert removed, "Configuration removal failed"
            assert not config_path.exists(), "Configuration still exists"
            
            print("✓ Configuration removal successful")
            
            return True
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_opt_integration():
    """Test OptIntegration class."""
    print("\n" + "=" * 60)
    print("Test 5: OptIntegration Class")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        etc_opt_root = Path(tmpdir) / "etc_opt"
        var_opt_root = Path(tmpdir) / "var_opt"
        
        try:
            from opt.config import OptIntegration
            
            # Create integration manager
            integration = OptIntegration(str(opt_root), str(etc_opt_root), str(var_opt_root))
            
            # Install package
            paths = integration.install_package("testapp")
            assert paths["package"].exists(), "Package directory not created"
            assert paths["etc"].exists(), "etc directory not created"
            assert paths["var"].exists(), "var directory not created"
            assert paths["bin"].exists(), "bin directory not created"
            assert paths["lib"].exists(), "lib directory not created"
            assert paths["doc"].exists(), "doc directory not created"
            
            print("✓ Package directory structure created")
            
            # Setup integration
            results = integration.setup_integration("testapp")
            assert results.get("etc", False), "etc integration failed"
            assert results.get("var", False), "var integration failed"
            
            print("✓ Integration setup successful")
            
            # Get package paths
            package_paths = integration.get_package_paths("testapp")
            assert package_paths["opt"].exists(), "opt path not found"
            assert package_paths["etc"].exists(), "etc path not found"
            assert package_paths["var"].exists(), "var path not found"
            
            print("✓ Package paths retrieval successful")
            
            # List packages
            packages = integration.list_packages()
            assert "testapp" in packages, "testapp not in package list"
            
            print("✓ Package listing successful")
            
            # Remove package
            removed = integration.remove_package("testapp")
            assert removed, "Package removal failed"
            
            print("✓ Package removal successful")
            
            return True
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_opt_environment():
    """Test OptEnvironment class."""
    print("\n" + "=" * 60)
    print("Test 6: OptEnvironment Class")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        
        try:
            from opt.integration import OptEnvironment
            
            # Create environment manager
            env = OptEnvironment(str(opt_root))
            
            # Create demo package with bin and lib directories
            demo_bin = opt_root / "demoapp" / "bin"
            demo_lib = opt_root / "demoapp" / "lib"
            demo_bin.mkdir(parents=True)
            demo_lib.mkdir(parents=True)
            
            # Add to PATH
            added = env.add_to_path("demoapp")
            assert added, "Failed to add to PATH"
            
            print("✓ PATH addition successful")
            
            # Add library path
            lib_added = env.add_library_path("demoapp")
            assert lib_added, "Failed to add library path"
            
            print("✓ Library path addition successful")
            
            # Get path string
            path_string = env.get_path_string()
            assert str(demo_bin) in path_string, "bin path not in PATH string"
            
            print("✓ PATH string generation successful")
            
            # Get library path string
            lib_path_string = env.get_library_path_string()
            assert str(opt_root / "demoapp" / "lib") in lib_path_string, "lib path not in library path string"
            
            print("✓ Library path string generation successful")
            
            # Setup package environment
            env_vars = env.setup_package_environment("demoapp")
            assert "OPT_PACKAGE_ROOT" in env_vars, "OPT_PACKAGE_ROOT not in env vars"
            assert "OPT_PACKAGE_BIN" in env_vars, "OPT_PACKAGE_BIN not in env vars"
            assert "OPT_PACKAGE_LIB" in env_vars, "OPT_PACKAGE_LIB not in env vars"
            
            print("✓ Package environment setup successful")
            
            return True
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_sample_installers():
    """Test sample installation scripts."""
    print("\n" + "=" * 60)
    print("Test 7: Sample Installation Scripts")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        etc_opt_root = Path(tmpdir) / "etc_opt"
        var_opt_root = Path(tmpdir) / "var_opt"
        
        try:
            from opt.installers.sample_app import install_sample_app
            
            # Install sample app
            result = install_sample_app(
                opt_root=str(opt_root),
                etc_opt_root=str(etc_opt_root),
                var_opt_root=str(var_opt_root),
                verbose=False
            )
            
            assert result["success"], f"Sample app installation failed: {result['errors']}"
            assert (opt_root / "sample-app" / "bin" / "sample-app").exists(), "Sample app binary not installed"
            assert (opt_root / "sample-app" / "doc" / "README.md").exists(), "Sample app documentation not installed"
            assert (etc_opt_root / "sample-app").exists(), "Sample app config not installed"
            assert (var_opt_root / "sample-app").exists(), "Sample app var data not installed"
            
            print("✓ Sample app installation successful")
            
            # Verify binary is executable
            binary_path = opt_root / "sample-app" / "bin" / "sample-app"
            assert os.access(binary_path, os.X_OK), "Sample app binary not executable"
            
            print("✓ Sample app binary is executable")
            
            # Verify man page exists
            man_path = opt_root / "sample-app" / "man" / "man1" / "sample-app.1"
            assert man_path.exists(), "Sample app man page not installed"
            
            print("✓ Sample app man page installed")
            
            return True
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_integration():
    """Test full integration of all components."""
    print("\n" + "=" * 60)
    print("Test 8: Full Integration")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        etc_opt_root = Path(tmpdir) / "etc_opt"
        var_opt_root = Path(tmpdir) / "var_opt"
        
        try:
            from opt import OptManager
            from opt.config import OptConfig
            
            # Create manager
            manager = OptManager(str(opt_root), str(etc_opt_root), str(var_opt_root))
            
            # Create demo files
            demo_bin = Path(tmpdir) / "demo.py"
            demo_bin.write_text('#!/usr/bin/env python3\nprint("Demo")\n')
            
            # Install package with full integration
            result = manager.install(
                "fulltest",
                version="1.0.0",
                description="Full integration test",
                binaries=[str(demo_bin)],
                config={"test": True, "integration": True}
            )
            
            assert result["success"], f"Full integration install failed: {result['errors']}"
            
            print("✓ Full integration install successful")
            
            # Verify package exists
            package_info = manager.get("fulltest")
            assert package_info is not None, "Package not found in database"
            assert package_info["version"] == "1.0.0", "Version mismatch"
            assert package_info["description"] == "Full integration test", "Description mismatch"
            
            print("✓ Package info retrieval successful")
            
            # Update package
            update_result = manager.update("fulltest", version="2.0.0")
            assert update_result["success"], "Package update failed"
            
            print("✓ Package update successful")
            
            # Verify updated version
            updated_info = manager.get("fulltest")
            assert updated_info["version"] == "2.0.0", "Version not updated"
            
            print("✓ Version update verified")
            
            # Verify all components
            verification = manager.verify("fulltest")
            assert all(verification['integrity'].values()), "Integrity verification failed"
            
            print("✓ Integrity verification successful")
            
            # Get statistics
            stats = manager.get_stats()
            assert stats["total_packages"] == 1, "Package count mismatch"
            
            print("✓ Statistics retrieval successful")
            
            # Remove package
            remove_result = manager.remove("fulltest")
            assert remove_result["success"], "Package removal failed"
            
            print("✓ Full integration removal successful")
            
            return True
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("UmerOS /opt Package Management System - Test Suite")
    print("=" * 60)
    print(f"Running at: {Path.cwd()}")
    print()
    
    tests = [
        ("Module Imports", test_imports),
        ("OptPackage Class", test_opt_package),
        ("OptManager Class", test_opt_manager),
        ("OptConfig Class", test_opt_config),
        ("OptIntegration Class", test_opt_integration),
        ("OptEnvironment Class", test_opt_environment),
        ("Sample Installation Scripts", test_sample_installers),
        ("Full Integration", test_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
