# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Development Tools Installation Script for /opt

This script demonstrates proper installation of development tools
to /opt following Linux Filesystem Hierarchy standards.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Dict, Any

# Add workspace root to path for imports when running standalone
workspace_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(workspace_root))

from opt.manager import OptManager
from opt.config import OptConfig, OptIntegration
from opt.package import OptPackage


def install_development_tools(
    opt_root: str = "/opt",
    etc_opt_root: str = "/etc/opt",
    var_opt_root: str = "/var/opt",
    tools_name: str = "devtools",
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Install development tools to /opt.
    
    Args:
        opt_root: Root directory for opt packages
        etc_opt_root: Root directory for opt configurations
        var_opt_root: Root directory for opt variable data
        tools_name: Name of the development tools package
        verbose: Enable verbose output
        
    Returns:
        Dictionary with installation results
    """
    result = {
        "success": False,
        "package": tools_name,
        "version": "1.0.0",
        "installed_at": "",
        "paths": {},
        "errors": []
    }
    
    try:
        # Initialize paths
        opt_root_path = Path(opt_root)
        etc_opt_path = Path(etc_opt_root)
        var_opt_path = Path(var_opt_root)
        
        # Ensure directories exist
        for directory in [opt_root_path, etc_opt_path, var_opt_path]:
            directory.mkdir(parents=True, exist_ok=True)
        
        result["installed_at"] = str(opt_root_path / tools_name)
        
        # Create package structure
        package_path = opt_root_path / tools_name
        package_path.mkdir(parents=True, exist_ok=True)
        
        # Create standard subdirectories
        subdirs = {
            "bin": package_path / "bin",
            "lib": package_path / "lib",
            "include": package_path / "include",
            "doc": package_path / "doc",
            "info": package_path / "info",
            "man": package_path / "man",
            "src": package_path / "src",
            "projects": var_opt_path / tools_name / "projects",
            "cache": var_opt_path / tools_name / "cache",
            "temp": var_opt_path / tools_name / "temp",
        }
        
        for name, path in subdirs.items():
            path.mkdir(parents=True, exist_ok=True)
            result["paths"][name] = str(path)
        
        # Create development tools wrapper
        bin_path = package_path / "bin" / tools_name
        bin_path.write_text(f"""#!/usr/bin/env python3
'''
Development Tools
This is a demonstration of development tools installed to /opt
'''
import sys
import os

def main():
    print("Development Tools Suite")
    print("=" * 40)
    print(f"Version: 1.0.0")
    print(f"Installation: /opt/{tools_name}")
    print(f"Configuration: /etc/opt/{tools_name}")
    print(f"Variable data: /var/opt/{tools_name}")
    print()
    print("Available tools:")
    print("  compiler    - Python compiler/wrapper")
    print("  ide         - Simple IDE launcher")
    print("  debugger    - Debugging wrapper")
    print("  profiler    - Profiling wrapper")
    print("  test        - Test runner wrapper")
    print()
    print("Usage: {{sys.argv[0]}} <tool> [options]")
    return 0

if __name__ == '__main__':
    sys.exit(main())
""")
        bin_path.chmod(0o755)
        
        # Create compiler wrapper
        compiler_path = package_path / "bin" / "compiler"
        compiler_path.write_text(f"""#!/usr/bin/env python3
'''
Python Compiler Wrapper
'''
import sys
import os

def compile_file(filename):
    '''Compile a Python file to bytecode'''
    import py_compile
    try:
        py_compile.compile(filename, doraise=True)
        print(f"Compiled: {{filename}}")
        return True
    except py_compile.PyCompileError as e:
        print(f"Compile error: {{e}}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: {{sys.argv[0]}} <file.py> [options]")
        return 1
        
    filename = sys.argv[1]
    
    if not os.path.exists(filename):
        print(f"File not found: {{filename}}")
        return 1
        
    return 0 if compile_file(filename) else 1

if __name__ == '__main__':
    sys.exit(main())
""")
        compiler_path.chmod(0o755)
        
        # Create IDE launcher
        ide_path = package_path / "bin" / "ide"
        ide_path.write_text(f"""#!/usr/bin/env python3
'''
IDE Launcher
'''
import sys
import os

def main():
    print("Starting IDE...")
    print(f"Projects directory: /var/opt/{tools_name}/projects")
    print(f"Cache directory: /var/opt/{tools_name}/cache")
    print()
    print("IDE would start here (placeholder)")
    return 0

if __name__ == '__main__':
    sys.exit(main())
""")
        ide_path.chmod(0o755)
        
        # Create documentation
        doc_path = package_path / "doc" / "README.md"
        doc_path.write_text(f"""# Development Tools

This is a demonstration of development tools installed to /opt according to
Linux Filesystem Hierarchy standards.

## Installation

This development tools suite is installed in /opt/{tools_name} with the following structure:

- bin/      - Executable binaries
- lib/      - Library files
- include/  - Header files
- doc/      - Documentation
- projects/ - User projects in /var/opt/{tools_name}/projects
- cache/    - Cache files in /var/opt/{tools_name}/cache
- temp/     - Temporary files in /var/opt/{tools_name}/temp

## Usage

Run the development tools suite:

    /opt/{tools_name}/bin/{tools_name}

Available tools:

    compiler    - Python compiler/wrapper
    ide         - Simple IDE launcher
    debugger    - Debugging wrapper
    profiler    - Profiling wrapper
    test        - Test runner wrapper

## Configuration

Configuration files are stored in /etc/opt/{tools_name}/

## Variable Data

- Projects: /var/opt/{tools_name}/projects/
- Cache: /var/opt/{tools_name}/cache/
- Temp: /var/opt/{tools_name}/temp/

## Integration

This development tools suite follows the Linux Filesystem Hierarchy Standard (FHS)
for software installed in /opt.
""")
        
        # Create configuration
        config = OptConfig(str(opt_root), str(etc_opt_root))
        config_path = config.install_config(tools_name, {
            "version": "1.0.0",
            "tools": {
                "name": tools_name,
                "projects_directory": str(var_opt_path / tools_name / "projects"),
                "cache_directory": str(var_opt_path / tools_name / "cache"),
                "temp_directory": str(var_opt_path / tools_name / "temp")
            },
            "directories": {
                "config": str(etc_opt_path / tools_name),
                "opt": str(package_path)
            }
        })
        result["paths"]["config"] = str(config_path)
        
        # Setup integration
        integration = OptIntegration(str(opt_root), str(etc_opt_root), str(var_opt_root))
        integration_results = integration.setup_integration(tools_name)
        result["paths"]["etc_integration"] = str(integration_results.get("etc", False))
        result["paths"]["var_integration"] = str(integration_results.get("var", False))
        
        result["success"] = True
        
        if verbose:
            print(f"{tools_name} Installation Complete!")
            print("=" * 50)
            print(f"Package: {tools_name}")
            print(f"Version: 1.0.0")
            print(f"Installation directory: /opt/{tools_name}")
            print(f"Configuration: {etc_opt_path}/{tools_name}")
            print(f"Variable data: {var_opt_path}/{tools_name}")
            print(f"Binary: /opt/{tools_name}/bin/{tools_name}")
            print(f"Projects: /var/opt/{tools_name}/projects")
            print(f"Cache: /var/opt/{tools_name}/cache")
            print(f"Temp: /var/opt/{tools_name}/temp")
            print()
            print(f"To run the development tools suite:")
            print(f"    /opt/{tools_name}/bin/{tools_name}")
            print()
            print(f"Available tools:")
            print(f"    /opt/{tools_name}/bin/compiler")
            print(f"    /opt/{tools_name}/bin/ide")
        
    except Exception as e:
        result["errors"].append(str(e))
        if verbose:
            print(f"Installation failed: {e}")
    
    return result


if __name__ == "__main__":
    install_development_tools(verbose=True)
