# yum_cli.py
"""Utility functions for interacting with YUM package manager.

Provides wrappers to list installed packages and retrieve package
information using the UmerOS YumManager natively.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the project root to Python path for imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from srv.yum_manager import YumManager


def _get_manager() -> YumManager:
    """Get a default YumManager instance."""
    return YumManager()


def run_yum_command(args: List[str]) -> Dict[str, Any]:
    """Execute a yum-like command using YumManager.

    Parameters
    ----------
    args: List[str]
        Arguments to pass (e.g., ["list", "installed"]).

    Returns
    -------
    Dict[str, Any]
        Dictionary with 'success', 'output', 'error', and 'return_code'.
    """
    if not args:
        return {
            'success': False,
            'output': '',
            'error': 'No command specified',
            'return_code': 1
        }

    cmd = args[0].lower()
    manager = _get_manager()

    try:
        if cmd == 'list':
            if len(args) > 1 and args[1].lower() == 'installed':
                installed = manager.list_installed()
                packages = [{'name': pkg.name, 'version': pkg.version, 'repo': pkg.repo}
                           for pkg in installed]
                return {
                    'success': True,
                    'output': packages,
                    'error': '',
                    'return_code': 0
                }
            else:
                return {
                    'success': False,
                    'output': '',
                    'error': 'Only "list installed" is supported',
                    'return_code': 1
                }

        elif cmd == 'info':
            if len(args) < 2:
                return {
                    'success': False,
                    'output': '',
                    'error': 'Package name required',
                    'return_code': 1
                }
            package_name = args[1]
            info = manager.info(package_name)
            return {
                'success': True,
                'output': info.__dict__ if hasattr(info, '__dict__') else {},
                'error': '',
                'return_code': 0
            }

        elif cmd == 'install':
            packages = args[1:]
            if not packages:
                return {
                    'success': False,
                    'output': '',
                    'error': 'No packages specified',
                    'return_code': 1
                }
            result = manager.install(packages)
            return {
                'success': result.success,
                'output': result.messages,
                'error': result.error or '',
                'return_code': 0 if result.success else 1
            }

        elif cmd == 'remove':
            packages = args[1:]
            if not packages:
                return {
                    'success': False,
                    'output': '',
                    'error': 'No packages specified',
                    'return_code': 1
                }
            result = manager.remove(packages)
            return {
                'success': result.success,
                'output': result.messages,
                'error': result.error or '',
                'return_code': 0 if result.success else 1
            }

        else:
            return {
                'success': False,
                'output': '',
                'error': f'Unsupported command: {cmd}',
                'return_code': 1
            }

    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': str(e),
            'return_code': 1
        }


def list_installed_packages() -> List[Dict[str, str]]:
    """Return a list of installed packages.

    Returns a list of dictionaries with keys 'name', 'version' and 'repo'.
    """
    manager = _get_manager()
    installed = manager.list_installed()
    return [{'name': pkg.name, 'version': pkg.version, 'repo': pkg.repo}
            for pkg in installed]


def parse_yum_list_output(output: str) -> List[Dict[str, str]]:
    """Parse the output of ``yum list installed``.

    Note: This function is kept for backward compatibility but is no longer
    needed with YumManager. Use list_installed_packages() instead.
    """
    packages: List[Dict[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Loaded plugins:") or line.startswith("Installed Packages"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        name_arch, version, repo = parts[0], parts[1], parts[2]
        name = name_arch.rsplit('.', 1)[0]
        packages.append({"name": name, "version": version, "repo": repo})
    return packages


def get_package_info(package_name: str) -> Dict[str, str]:
    """Retrieve detailed information about a specific package.

    Returns a dictionary of key/value pairs for the package.
    """
    manager = _get_manager()
    info = manager.info(package_name)
    if hasattr(info, '__dict__'):
        return info.__dict__
    return {}


if __name__ == "__main__":
    import json
    packages = list_installed_packages()
    print(json.dumps(packages, indent=2))
