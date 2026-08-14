"""
Sample Application Installation Script for /opt

This script demonstrates proper installation of a sample application
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

def install_sample_app(
    opt_root: str = "/opt",
    etc_opt_root: str = "/etc/opt",
    var_opt_root: str = "/var/opt",
    install_dir: str = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Install a sample application to /opt.
    
    Args:
        opt_root: Root directory for opt packages
        etc_opt_root: Root directory for opt configurations
        var_opt_root: Root directory for opt variable data
        install_dir: Custom installation directory (optional)
        verbose: Enable verbose output
        
    Returns:
        Dictionary with installation results
    """
    result = {
        "success": False,
        "package": "sample-app",
        "version": "1.0.0",
        "installed_at": "",
        "paths": {},
        "errors": []
    }
    
    try:
        # Initialize managers
        opt_root_path = Path(opt_root)
        etc_opt_path = Path(etc_opt_root)
        var_opt_path = Path(var_opt_root)
        
        # Ensure directories exist
        for directory in [opt_root_path, etc_opt_path, var_opt_path]:
            directory.mkdir(parents=True, exist_ok=True)
        
        result["installed_at"] = str(Path("/opt/sample-app"))
        
        # Create package structure
        package_path = opt_root_path / "sample-app"
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
        }
        
        for name, path in subdirs.items():
            path.mkdir(parents=True, exist_ok=True)
            result["paths"][name] = str(path)
        
        # Create sample binary
        bin_path = package_path / "bin" / "sample-app"
        bin_path.write_text("""#!/usr/bin/env python3
'''
Sample Application
This is a demonstration application installed to /opt
'''
import sys
import os

def main():
    print("Sample Application v1.0.0")
    print("=" * 40)
    print("This application was installed to /opt")
    print("Package root: {}".format(os.environ.get('OPT_PACKAGE_ROOT', '/opt/sample-app')))
    print("Configuration: {}".format(os.environ.get('OPT_PACKAGE_CONFIG', '/etc/opt/sample-app')))
    print("Variable data: {}".format(os.environ.get('OPT_PACKAGE_VAR', '/var/opt/sample-app')))
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'version':
            print("\\nVersion: 1.0.0")
        elif sys.argv[1] == 'info':
            print("\\nInstallation directory: {}".format(os.environ.get('OPT_PACKAGE_ROOT', '/opt/sample-app')))
        elif sys.argv[1] == 'config':
            config_dir = os.environ.get('OPT_PACKAGE_CONFIG', '/etc/opt/sample-app')
            print("\\nConfiguration directory: {}".format(config_dir))
        else:
            print("\\nUnknown option: {}".format(sys.argv[1]))
            print("Options: version, info, config")
    else:
        print("\\nUsage: sample-app [option]")
        print("Options: version, info, config")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
""")
        bin_path.chmod(0o755)
        
        # Create sample library
        lib_path = package_path / "lib" / "samplelib.py"
        lib_path.write_text("""'''
Sample library for the sample application
This demonstrates how libraries are organized in /opt
'''
__version__ = "1.0.0"

def sample_function():
    '''A sample function'''
    return "Hello from sample library!"

def calculate(value):
    '''A sample calculation function'''
    return value * 2
""")
        
        # Create documentation
        doc_path = package_path / "doc" / "README.md"
        doc_path.write_text("""# Sample Application

This is a sample application demonstrating proper installation
to /opt according to Linux Filesystem Hierarchy standards.

## Installation

This application is installed in /opt/sample-app with the following structure:

- bin/     - Executable binaries
- lib/     - Library files
- include/ - Header files (if applicable)
- doc/     - Documentation
- info/    - GNU Info documentation
- man/     - Manual pages
- src/     - Source code

## Usage

Run the sample application:

    /opt/sample-app/bin/sample-app

Options:
    version - Show version information
    info    - Show installation information
    config  - Show configuration information

## Configuration

Configuration files are stored in /etc/opt/sample-app/

## Variable Data

Variable data is stored in /var/opt/sample-app/

## Integration

This application follows the Linux Filesystem Hierarchy Standard (FHS)
for software installed in /opt.
""")
        
        # Create man page
        man_path = package_path / "man" / "man1"
        man_path.mkdir(parents=True, exist_ok=True)
        man_page = man_path / "sample-app.1"
        man_page.write_text(r""".TH SAMPLE-APP 1 "August 2026" "1.0.0" "Sample Application Manual"
.SH NAME
sample-app \- Sample application demonstrating /opt installation
.SH SYNOPSIS
.B sample-app
[\fIOPTION\fR]
.SH DESCRIPTION
.B sample-app
is a demonstration application installed to /opt according to the
Linux Filesystem Hierarchy Standard.
.SH OPTIONS
.TP
.BR version
Show version information
.TP
.BR info
Show installation information
.TP
.BR config
Show configuration information
.SH AUTHOR
UmerOS Development Team
.SH "SEE ALSO"
.BR opt (7)
""")
        
        # Create configuration
        config = OptConfig(str(opt_root), str(etc_opt_root))
        config_path = config.install_config("sample-app", {
            "version": "1.0.0",
            "application": {
                "name": "Sample App",
                "debug": False,
                "log_level": "INFO"
            },
            "paths": {
                "log": "/var/opt/sample-app/logs",
                "data": "/var/opt/sample-app/data"
            }
        })
        result["paths"]["config"] = str(config_path)
        
        # Setup integration
        integration = OptIntegration(str(opt_root), str(etc_opt_root), str(var_opt_root))
        integration_results = integration.setup_integration("sample-app")
        result["paths"]["etc_integration"] = str(integration_results.get("etc", False))
        result["paths"]["var_integration"] = str(integration_results.get("var", False))
        
        result["success"] = True
        
        if verbose:
            print("Sample Application Installation Complete!")
            print("=" * 50)
            print(f"Package: sample-app")
            print(f"Version: 1.0.0")
            print(f"Installation directory: /opt/sample-app")
            print(f"Configuration: {etc_opt_root}/sample-app")
            print(f"Variable data: {var_opt_root}/sample-app")
            print(f"Binary: /opt/sample-app/bin/sample-app")
            print()
            print("To run the application:")
            print(f"    /opt/sample-app/bin/sample-app")
            print()
            print("To see version information:")
            print(f"    /opt/sample-app/bin/sample-app version")
            print()
            print("To see documentation:")
            print(f"    cat {package_path}/doc/README.md")
            print()
            print("To see manual page:")
            print(f"    man -M {package_path}/man {package_path}/man/man1/sample-app.1")
        
    except Exception as e:
        result["errors"].append(str(e))
        if verbose:
            print(f"Installation failed: {e}")
    
    return result


if __name__ == "__main__":
    install_sample_app(verbose=True)
