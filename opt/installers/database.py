"""
Database Server Installation Script for /opt

This script demonstrates proper installation of a database server
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


def install_database(
    opt_root: str = "/opt",
    etc_opt_root: str = "/etc/opt",
    var_opt_root: str = "/var/opt",
    db_name: str = "database",
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Install a database server to /opt.
    
    Args:
        opt_root: Root directory for opt packages
        etc_opt_root: Root directory for opt configurations
        var_opt_root: Root directory for opt variable data
        db_name: Name of the database package
        verbose: Enable verbose output
        
    Returns:
        Dictionary with installation results
    """
    result = {
        "success": False,
        "package": db_name,
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
        
        result["installed_at"] = str(opt_root_path / db_name)
        
        # Create package structure
        package_path = opt_root_path / db_name
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
            "data": var_opt_path / db_name / "data",
            "logs": var_opt_path / db_name / "logs",
            "backup": var_opt_path / db_name / "backup",
        }
        
        for name, path in subdirs.items():
            path.mkdir(parents=True, exist_ok=True)
            result["paths"][name] = str(path)
        
        # Create database server binary
        bin_path = package_path / "bin" / db_name
        bin_path.write_text(f"""#!/usr/bin/env python3
'''
Database Server
This is a demonstration database server installed to /opt
'''
import sys
import os
import json
import tempfile

class DatabaseServer:
    def __init__(self):
        self.name = '{db_name}'
        self.data_dir = os.environ.get('OPT_PACKAGE_DATA', '{var_opt_path}/{db_name}/data')
        self.log_dir = os.environ.get('OPT_PACKAGE_LOGS', '{var_opt_path}/{db_name}/logs')
        self.config = os.environ.get('OPT_PACKAGE_CONFIG', '{etc_opt_path}/{db_name}')
        self.backup_dir = os.environ.get('OPT_PACKAGE_BACKUP', '{var_opt_path}/{db_name}/backup')
        
    def start(self):
        '''Start the database server'''
        print(f"{{self.name}} starting...")
        print(f"Data directory: {{self.data_dir}}")
        print(f"Log directory: {{self.log_dir}}")
        print(f"Backup directory: {{self.backup_dir}}")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        print("Database server started successfully")
        
    def stop(self):
        '''Stop the database server'''
        print(f"{{self.name}} stopping...")
        print("Database server stopped")
        
    def status(self):
        '''Check server status'''
        print(f"{{self.name}} status:")
        print(f"  Data directory: {{self.data_dir}}")
        print(f"  Log directory: {{self.log_dir}}")
        print(f"  Backup directory: {{self.backup_dir}}")
        print(f"  Configuration: {{self.config}}")
        
    def backup(self, backup_name=None):
        '''Create a backup'''
        if backup_name is None:
            import datetime
            backup_name = f"backup_{{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}}"
            
        backup_path = os.path.join(self.backup_dir, backup_name)
        os.makedirs(backup_path, exist_ok=True)
        print(f"Backup created: {{backup_path}}")
        return backup_path

def main():
    if len(sys.argv) < 2:
        print("Usage: {{sys.argv[0]}} [start|stop|status|backup [name]]")
        return 1
        
    server = DatabaseServer()
    command = sys.argv[1]
    
    if command == "start":
        server.start()
    elif command == "stop":
        server.stop()
    elif command == "status":
        server.status()
    elif command == "backup":
        backup_name = sys.argv[2] if len(sys.argv) > 2 else None
        server.backup(backup_name)
    else:
        print(f"Unknown command: {{command}}")
        print("Commands: start, stop, status, backup [name]")
        return 1
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
""")
        bin_path.chmod(0o755)
        
        # Create database library
        lib_path = package_path / "lib" / "dblib.py"
        lib_path.write_text("""'''
Database library
This provides common functionality for databases installed to /opt
'''
__version__ = "1.0.0"

class SimpleDB:
    '''A simple in-memory database'''
    def __init__(self):
        self.tables = {}
        
    def create_table(self, name, columns):
        '''Create a new table'''
        self.tables[name] = {'columns': columns, 'rows': []}
        
    def insert(self, table, values):
        '''Insert a row'''
        if table not in self.tables:
            raise ValueError(f"Table {{table}} not found")
        self.tables[table]['rows'].append(values)
        
    def select(self, table):
        '''Select all rows from a table'''
        if table not in self.tables:
            raise ValueError(f"Table {{table}} not found")
        return self.tables[table]['rows']
""")
        
        # Create documentation
        doc_path = package_path / "doc" / "README.md"
        doc_path.write_text(f"""# Database Server

This is a demonstration database server installed to /opt according to
Linux Filesystem Hierarchy standards.

## Installation

This database server is installed in /opt/{db_name} with the following structure:

- bin/     - Executable binaries
- lib/     - Library files
- doc/     - Documentation
- data/    - Database files in /var/opt/{db_name}/data
- logs/    - Log files in /var/opt/{db_name}/logs
- backup/  - Backup files in /var/opt/{db_name}/backup

## Usage

Start the database server:

    /opt/{db_name}/bin/{db_name} start

Stop the database server:

    /opt/{db_name}/bin/{db_name} stop

Check server status:

    /opt/{db_name}/bin/{db_name} status

Create a backup:

    /opt/{db_name}/bin/{db_name} backup [backup_name]

## Configuration

Configuration files are stored in /etc/opt/{db_name}/

## Variable Data

- Data files: /var/opt/{db_name}/data/
- Log files: /var/opt/{db_name}/logs/
- Backups: /var/opt/{db_name}/backup/

## Integration

This database server follows the Linux Filesystem Hierarchy Standard (FHS)
for software installed in /opt.
""")
        
        # Create man page
        man_path = package_path / "man" / "man1"
        man_path.mkdir(parents=True, exist_ok=True)
        man_page = man_path / f"{db_name}.1"
        man_page.write_text(rf""".TH {db_name.upper()} 1 "August 2026" "1.0.0" "Database Server Manual"
.SH NAME
{db_name} \- Demonstration database server installed to /opt
.SH SYNOPSIS
.B {db_name}
[\fICOMMAND\fR]
.SH DESCRIPTION
.B {db_name}
is a demonstration database server installed to /opt according to the
Linux Filesystem Hierarchy Standard.
.SH COMMANDS
.TP
.BR start
Start the database server
.TP
.BR stop
Stop the database server
.TP
.BR status
Check server status
.TP
.BR backup
Create a backup
.SH FILES
.TP
.I /opt/{db_name}/bin/{db_name}
The database server executable
.TP
.I /var/opt/{db_name}/data/
Database files
.TP
.I /var/opt/{db_name}/logs/
Log files
.TP
.I /etc/opt/{db_name}/
Configuration files
.SH AUTHOR
UmerOS Development Team
.SH "SEE ALSO"
.BR opt (7)
""")
        
        # Create configuration
        config = OptConfig(str(opt_root), str(etc_opt_root))
        config_path = config.install_config(db_name, {
            "version": "1.0.0",
            "database": {
                "name": db_name,
                "data_directory": str(var_opt_path / db_name / "data"),
                "log_directory": str(var_opt_path / db_name / "logs"),
                "backup_directory": str(var_opt_path / db_name / "backup")
            },
            "directories": {
                "config": str(etc_opt_path / db_name),
                "opt": str(package_path)
            }
        })
        result["paths"]["config"] = str(config_path)
        
        # Setup integration
        integration = OptIntegration(str(opt_root), str(etc_opt_root), str(var_opt_root))
        integration_results = integration.setup_integration(db_name)
        result["paths"]["etc_integration"] = str(integration_results.get("etc", False))
        result["paths"]["var_integration"] = str(integration_results.get("var", False))
        
        result["success"] = True
        
        if verbose:
            print(f"{db_name} Installation Complete!")
            print("=" * 50)
            print(f"Package: {db_name}")
            print(f"Version: 1.0.0")
            print(f"Installation directory: /opt/{db_name}")
            print(f"Configuration: {etc_opt_path}/{db_name}")
            print(f"Variable data: {var_opt_path}/{db_name}")
            print(f"Binary: /opt/{db_name}/bin/{db_name}")
            print(f"Data directory: /var/opt/{db_name}/data")
            print(f"Log files: /var/opt/{db_name}/logs")
            print(f"Backups: /var/opt/{db_name}/backup")
            print()
            print(f"To start the database server:")
            print(f"    /opt/{db_name}/bin/{db_name} start")
            print()
            print(f"To stop the database server:")
            print(f"    /opt/{db_name}/bin/{db_name} stop")
            print()
            print(f"To check status:")
            print(f"    /opt/{db_name}/bin/{db_name} status")
            print()
            print(f"To create a backup:")
            print(f"    /opt/{db_name}/bin/{db_name} backup")
        
    except Exception as e:
        result["errors"].append(str(e))
        if verbose:
            print(f"Installation failed: {e}")
    
    return result


if __name__ == "__main__":
    install_database(verbose=True)
