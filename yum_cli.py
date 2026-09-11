# yum_cli.py
"""Utility functions for interacting with YUM package manager.

Provides simple wrappers to list installed packages and retrieve package
information. Designed for use within the UmerOS project.
"""

import subprocess
from typing import List, Dict


def run_yum_command(args: List[str]) -> str:
    """Execute a yum command and return its stdout as a string.

    Parameters
    ----------
    args: List[str]
        Arguments to pass to yum (e.g., ["list", "installed"]).

    Returns
    -------
    str
        The stdout output of the command.
    """
    result = subprocess.run(["yum"] + args, capture_output=True, text=True, check=False)
    return result.stdout


def list_installed_packages() -> List[Dict[str, str]]:
    """Return a list of installed packages.

    The function runs ``yum list installed`` and parses the output into a list of
    dictionaries with keys ``name``, ``version`` and ``repo``.
    """
    raw = run_yum_command(["list", "installed", "--quiet"])
    return parse_yum_list_output(raw)


def parse_yum_list_output(output: str) -> List[Dict[str, str]]:
    """Parse the output of ``yum list installed``.

    The typical format (skipping header lines) is:
        <name>.<arch>   <version>   <repo>
    This parser extracts the package name (without architecture), version and
    repository.
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
    """Retrieve detailed information about a specific package using ``yum info``.

    Returns a dictionary of key/value pairs extracted from the command output.
    """
    raw = run_yum_command(["info", package_name])
    info: Dict[str, str] = {}
    for line in raw.splitlines():
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.strip()] = value.strip()
    return info

if __name__ == "__main__":
    import json
    print(json.dumps(list_installed_packages(), indent=2))
