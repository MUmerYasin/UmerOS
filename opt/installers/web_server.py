"""
Web Server Installation Script for /opt

This script demonstrates proper installation of a web server
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


def install_web_server(
    opt_root: str = "/opt",
    etc_opt_root: str = "/etc/opt",
    var_opt_root: str = "/var/opt",
    web_server_name: str = "webserver",
    port: int = 8080,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Install a web server to /opt.
    
    Args:
        opt_root: Root directory for opt packages
        etc_opt_root: Root directory for opt configurations
        var_opt_root: Root directory for opt variable data
        web_server_name: Name of the web server package
        port: Port to listen on
        verbose: Enable verbose output
        
    Returns:
        Dictionary with installation results
    """
    result = {
        "success": False,
        "package": web_server_name,
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
        
        result["installed_at"] = str(opt_root_path / web_server_name)
        
        # Create package structure
        package_path = opt_root_path / web_server_name
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
            "htdocs": package_path / "htdocs",
            "logs": var_opt_path / web_server_name / "logs",
            "data": var_opt_path / web_server_name / "data",
        }
        
        for name, path in subdirs.items():
            path.mkdir(parents=True, exist_ok=True)
            result["paths"][name] = str(path)
        
        # Create web server binary
        bin_path = package_path / "bin" / web_server_name
        bin_path.write_text(f"""#!/usr/bin/env python3
'''
Web Server
This is a demonstration web server installed to /opt
'''
import sys
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: {{sys.argv[0]}} [start|stop|status]")
        return 1
        
    command = sys.argv[1]
    
    if command == "start":
        server.start()
    elif command == "stop":
        server.stop()
    elif command == "status":
        server.status()
    else:
        print(f"Unknown command: {{command}}")
        print("Commands: start, stop, status")
        return 1
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
""")
        bin_path.chmod(0o755)
        
        # Create web server library
        lib_path = package_path / "lib" / "weblib.py"
        lib_path.write_text("""'''
Web server library
This provides common functionality for web servers installed to /opt
'''
__version__ = "1.0.0"

def create_route(pattern, handler):
    '''Create a URL route'''
    return {'pattern': pattern, 'handler': handler}

def create_response(status=200, headers=None, body=''):
    '''Create an HTTP response'''
    return {
        'status': status,
        'headers': headers or {},
        'body': body
    }
""")
        
        # Create default web page
        htdocs_path = package_path / "htdocs" / "index.html"
        htdocs_path.write_text(f"""<!DOCTYPE html>
<html>
<head>
    <title>Web Server - Sample App</title>
</head>
<body>
    <h1>Welcome to the Web Server</h1>
    <p>This web server was installed to /opt.</p>
    <hr>
    <p>Package: {web_server_name}</p>
    <p>Version: 1.0.0</p>
    <p>Port: {port}</p>
</body>
</html>
""")
        
        # Create documentation
        doc_path = package_path / "doc" / "README.md"
        doc_path.write_text(f"""# Web Server

This is a demonstration web server installed to /opt according to
Linux Filesystem Hierarchy standards.

## Installation

This web server is installed in /opt/{web_server_name} with the following structure:

- bin/     - Executable binaries
- lib/     - Library files
- doc/     - Documentation
- htdocs/  - Web content
- logs/    - Log files in /var/opt/{web_server_name}/logs

## Usage

Start the web server:

    /opt/{web_server_name}/bin/{web_server_name} start

Stop the web server:

    /opt/{web_server_name}/bin/{web_server_name} stop

Check server status:

    /opt/{web_server_name}/bin/{web_server_name} status

## Configuration

Configuration files are stored in /etc/opt/{web_server_name}/

## Variable Data

Log files are stored in /var/opt/{web_server_name}/logs/

## Default Web Content

The default web content is served from /opt/{web_server_name}/htdocs/

## Integration

This web server follows the Linux Filesystem Hierarchy Standard (FHS)
for software installed in /opt.
""")
        
        # Create configuration
        config = OptConfig(str(opt_root), str(etc_opt_root))
        config_path = config.install_config(web_server_name, {
            "version": "1.0.0",
            "server": {
                "port": port,
                "docroot": str(package_path / "htdocs"),
                "host": "0.0.0.0"
            },
            "logging": {
                "level": "INFO",
                "directory": str(var_opt_path / web_server_name / "logs")
            },
            "directories": {
                "config": str(etc_opt_path / web_server_name),
                "data": str(var_opt_path / web_server_name / "data")
            }
        })
        result["paths"]["config"] = str(config_path)
        
        # Setup integration
        integration = OptIntegration(str(opt_root), str(etc_opt_root), str(var_opt_root))
        integration_results = integration.setup_integration(web_server_name)
        result["paths"]["etc_integration"] = str(integration_results.get("etc", False))
        result["paths"]["var_integration"] = str(integration_results.get("var", False))
        
        result["success"] = True
        
        if verbose:
            print(f"{web_server_name} Installation Complete!")
            print("=" * 50)
            print(f"Package: {web_server_name}")
            print(f"Version: 1.0.0")
            print(f"Installation directory: /opt/{web_server_name}")
            print(f"Configuration: {etc_opt_path}/{web_server_name}")
            print(f"Variable data: {var_opt_path}/{web_server_name}")
            print(f"Binary: /opt/{web_server_name}/bin/{web_server_name}")
            print(f"Web content: /opt/{web_server_name}/htdocs")
            print(f"Log files: /var/opt/{web_server_name}/logs")
            print()
            print(f"To start the server:")
            print(f"    /opt/{web_server_name}/bin/{web_server_name} start")
            print()
            print(f"To stop the server:")
            print(f"    /opt/{web_server_name}/bin/{web_server_name} stop")
            print()
            print(f"To check status:")
            print(f"    /opt/{web_server_name}/bin/{web_server_name} status")
            print()
            print(f"To access the web server:")
            print(f"    http://localhost:{port}")
        
    except Exception as e:
        result["errors"].append(str(e))
        if verbose:
            print(f"Installation failed: {e}")
    
    return result


if __name__ == "__main__":
    install_web_server(verbose=True)
