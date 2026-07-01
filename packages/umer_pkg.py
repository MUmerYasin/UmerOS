#!/usr/bin/env python3
"""
Umer OS Package Manager (umer-pkg)

Manages software installation, removal, listing, and dependency resolution.
Packages are stored in the QFS under /packages/<name>/.
Signatures are verified via the CryptoEngine.

Equivalent to apt/dpkg on Debian or pacman on Arch.

CLI usage (via shell):
    pkg install <name>
    pkg remove <name>
    pkg list
    pkg search <query>
    pkg info <name>
"""

from packages.repository import PackageRepository


class PackageManager:
    """Umer OS package manager."""

    def __init__(self, vfs=None, crypto=None):
        self.repo = PackageRepository()
        self.vfs = vfs
        self.crypto = crypto
        self._installed = {}  # name -> version
        # Pre-install core packages
        self._installed["umer-core"] = "2.0.0"
        print(f"[PKG] Package manager initialized. {len(self._installed)} package(s) installed.")

    def install(self, name: str) -> bool:
        if name in self._installed:
            print(f"[PKG] '{name}' is already installed (v{self._installed[name]}).")
            return True

        pkg = self.repo.get(name)
        if not pkg:
            print(f"[PKG] ERROR: Package '{name}' not found in repository.")
            return False

        # Resolve dependencies first
        for dep in pkg.dependencies:
            if dep not in self._installed:
                print(f"[PKG] Resolving dependency: {dep}")
                if not self.install(dep):
                    return False

        # Simulate download + signature verification
        print(f"[PKG] Downloading {pkg.name} v{pkg.version} ({pkg.size_kb} KB)...")
        if self.crypto:
            payload = f"{pkg.name}-{pkg.version}".encode()
            sig = self.crypto.sign(payload)
            verified = self.crypto.verify(payload, sig)
            print(f"[PKG] Signature verified: {verified}")

        # Install into VFS
        if self.vfs:
            install_path = f"/packages/{pkg.name}"
            self.vfs.mkdir(install_path)
            self.vfs.write_file(
                f"{install_path}/manifest.json",
                f'{{"name":"{pkg.name}","version":"{pkg.version}"}}'.encode()
            )

        self._installed[pkg.name] = pkg.version
        print(f"[PKG] Installed {pkg.name} v{pkg.version}.")
        return True

    def remove(self, name: str) -> bool:
        if name not in self._installed:
            print(f"[PKG] '{name}' is not installed.")
            return False

        if name == "umer-core":
            print("[PKG] ERROR: Cannot remove 'umer-core' — it is a system package.")
            return False

        # Check if other packages depend on this one
        dependents = []
        for installed_name in self._installed:
            pkg = self.repo.get(installed_name)
            if pkg and name in pkg.dependencies:
                dependents.append(installed_name)
        if dependents:
            print(f"[PKG] ERROR: Cannot remove '{name}' — required by: {', '.join(dependents)}")
            return False

        if self.vfs:
            self.vfs.delete(f"/packages/{name}/manifest.json")

        del self._installed[name]
        print(f"[PKG] Removed '{name}'.")
        return True

    def list_installed(self) -> dict:
        return dict(self._installed)

    def search(self, query: str) -> list:
        return self.repo.search(query)

    def info(self, name: str) -> dict:
        pkg = self.repo.get(name)
        if not pkg:
            return {}
        return {
            "name": pkg.name,
            "version": pkg.version,
            "description": pkg.description,
            "size_kb": pkg.size_kb,
            "dependencies": pkg.dependencies,
            "installed": name in self._installed,
        }


def main():
    """Entry point for console_scripts."""
    import sys
    pm = PackageManager()
    args = sys.argv[1:]
    if not args:
        print("Usage: umer-pkg <install|remove|list|search|info> [args]")
        return
    cmd = args[0]
    if cmd == "list":
        for name, ver in pm.list_installed().items():
            print(f"  {name} ({ver})")
    elif cmd == "install" and len(args) > 1:
        pm.install(args[1])
    elif cmd == "remove" and len(args) > 1:
        pm.remove(args[1])
    elif cmd == "search" and len(args) > 1:
        results = pm.search(args[1])
        for p in results:
            print(f"  {p}")
    elif cmd == "info" and len(args) > 1:
        info = pm.info(args[1])
        for k, v in info.items():
            print(f"  {k}: {v}")
    else:
        print("Usage: umer-pkg <install|remove|list|search|info> [args]")
