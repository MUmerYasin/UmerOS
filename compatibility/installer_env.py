"""
Umer OS /compatibility/installer_env — software installation targets
====================================================================

When Windows Installer (or any modern installer) puts an application on
a machine it has to answer two questions, and both are answered with
environment variables and Known Folders:

**Which installation context?**
    *Per-machine* -- installed for every user, under ``Program Files``,
    and needs administrative rights to write.
    *Per-user* -- installed for one user, under
    ``%LocalAppData%\\Programs``, and needs no rights at all.

**Which architecture?**
    A 32-bit package on a 64-bit Windows goes to
    ``Program Files (x86)``; a 64-bit package goes to ``Program Files``.
    A 32-bit *process* sees ``%ProgramFiles%`` pointing at the x86
    directory and finds the real one in ``%ProgramW6432%``.

This module turns those rules into concrete paths, so UmerOS can place
an application exactly where Windows would have put it -- and so a
32-bit installer running on UmerOS sees the same environment a 32-bit
installer sees on Windows.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/msi/installation-context
* https://learn.microsoft.com/en-us/windows/win32/msi/allusers
* https://learn.microsoft.com/en-us/windows/win32/winprog64/wow64-implementation-details
* https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Compat.InstallerEnv")


class InstallationContext(Enum):
    """Which installation context a package targets."""

    #: Installed for every user.  Requires elevation.
    PER_MACHINE = "PerMachine"
    #: Installed for one user only.  No elevation needed.
    PER_USER = "PerUser"

    @property
    def requires_elevation(self) -> bool:
        """``True`` when writing to the target needs admin rights."""
        return self is InstallationContext.PER_MACHINE


@dataclass(frozen=True)
class InstallTarget:
    """The concrete directories an application is installed into."""

    context: InstallationContext
    #: The directory the application itself lives in.
    app_dir: str
    #: The shared-components directory for this architecture.
    common_files: str
    #: Where the Start Menu shortcut goes.
    start_menu: str
    #: The registry key holding the uninstall information.
    uninstall_key: str
    #: Where the application's own data goes.
    data_dir: str
    #: The directory holding per-user application data.
    local_app_data: str
    #: The directory holding roaming application data.
    roaming_app_data: str
    #: ``True`` when the package is 32-bit on a 64-bit Windows.
    wow64: bool = False

    @property
    def is_per_user(self) -> bool:
        return self.context is InstallationContext.PER_USER


def _join(*parts: str) -> str:
    """Join path components with a backslash, skipping empty ones."""
    out = ""
    for part in parts:
        if not part:
            continue
        if out:
            out = out.rstrip("\\") + "\\" + part.lstrip("\\")
        else:
            out = part
    return out


def program_files_folder(context: InstallationContext,
                         app_is_32bit: bool,
                         os_is_64bit: bool,
                         block=None) -> str:
    """The ``ProgramFilesFolder`` value Windows Installer would use.

    ================================ ==================================
    Context / architecture           Value
    ================================ ==================================
    Per-machine, 32-bit OS           ``%ProgramFiles%``
    Per-machine, 64-bit OS, 64-bit   ``%ProgramFiles%``
    Per-machine, 64-bit OS, 32-bit   ``%ProgramFiles(x86)%``
    Per-user                         ``%LocalAppData%\\Programs``
    ================================ ==================================
    """
    from .environment import get_default_block   # local: avoid cycle
    if block is None:
        block = get_default_block()

    if context is InstallationContext.PER_USER:
        local = block.get("LocalAppData") or r"C:\Users\Default\AppData\Local"
        return _join(local, "Programs")

    if app_is_32bit and os_is_64bit:
        return block.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    return block.get("ProgramFiles") or r"C:\Program Files"


def common_files_folder(context: InstallationContext,
                        app_is_32bit: bool,
                        os_is_64bit: bool,
                        block=None) -> str:
    """The ``CommonFilesFolder`` value Windows Installer would use."""
    from .environment import get_default_block   # local: avoid cycle
    if block is None:
        block = get_default_block()

    if context is InstallationContext.PER_USER:
        local = block.get("LocalAppData") or r"C:\Users\Default\AppData\Local"
        return _join(local, "Programs", "Common")

    if app_is_32bit and os_is_64bit:
        return (block.get("CommonProgramFiles(x86)")
                or r"C:\Program Files (x86)\Common Files")
    return block.get("CommonProgramFiles") or r"C:\Program Files\Common Files"


def resolve_install_target(app_name: str,
                           context: InstallationContext = InstallationContext.PER_MACHINE,
                           *,
                           app_is_32bit: bool = False,
                           os_is_64bit: bool = True,
                           product_code: Optional[str] = None,
                           block=None) -> InstallTarget:
    """Work out every directory an application needs.

    Parameters
    ----------
    app_name:
        The display name of the application.  It becomes the last
        component of the install directory.
    context:
        Per-machine or per-user.
    app_is_32bit:
        ``True`` for a 32-bit package.
    os_is_64bit:
        ``True`` on a 64-bit Windows.
    product_code:
        The MSI product GUID.  When given it is used for the uninstall
        key; otherwise a placeholder is used.
    block:
        The environment block used to resolve the root directories.
    """
    from .environment import get_default_block   # local: avoid cycle
    if block is None:
        block = get_default_block()

    program_files = program_files_folder(context, app_is_32bit, os_is_64bit,
                                         block)
    common_files = common_files_folder(context, app_is_32bit, os_is_64bit,
                                       block)
    local_app_data = (block.get("LocalAppData")
                      or r"C:\Users\Default\AppData\Local")
    roaming_app_data = (block.get("AppData")
                        or r"C:\Users\Default\AppData\Roaming")
    program_data = block.get("ProgramData") or r"C:\ProgramData"

    if context is InstallationContext.PER_USER:
        app_dir = _join(local_app_data, "Programs", app_name)
        start_menu = _join(roaming_app_data,
                           "Microsoft", "Windows", "Start Menu", "Programs",
                           app_name)
        uninstall_key = (r"HKCU\Software\Microsoft\Windows\CurrentVersion"
                         r"\Uninstall" + (f"\\{product_code}" if product_code
                                         else ""))
        data_dir = _join(local_app_data, app_name)
    else:
        app_dir = _join(program_files, app_name)
        start_menu = _join(program_data, "Microsoft", "Windows", "Start Menu",
                           "Programs", app_name)
        uninstall_key = (r"HKLM\Software\Microsoft\Windows\CurrentVersion"
                         r"\Uninstall" + (f"\\{product_code}" if product_code
                                         else ""))
        data_dir = _join(program_data, app_name)

    return InstallTarget(
        context=context,
        app_dir=app_dir,
        common_files=common_files,
        start_menu=start_menu,
        uninstall_key=uninstall_key,
        data_dir=data_dir,
        local_app_data=local_app_data,
        roaming_app_data=roaming_app_data,
        wow64=(app_is_32bit and os_is_64bit),
    )


def msi_properties(context: InstallationContext) -> Dict[str, str]:
    """The MSI properties that select an installation context.

    ========================== ==================================================
    Context                    Properties
    ========================== ==================================================
    Per-machine                ``ALLUSERS=1``
    Per-user                   ``ALLUSERS=`` (empty)
    Dynamic                    ``ALLUSERS=2`` -- Windows Installer resolves it
                                from the user's privileges, falling back to
                                per-user for a standard account.
    ========================== ==================================================

    ``MSIINSTALLPERUSER=1`` additionally forces the per-user context, but
    Windows Installer ignores it unless ``ALLUSERS`` is ``2``.
    """
    if context is InstallationContext.PER_MACHINE:
        return {"ALLUSERS": "1"}
    return {"ALLUSERS": ""}


def installer_environment(base_block=None,
                          *,
                          context: InstallationContext = InstallationContext.PER_MACHINE,
                          app_is_32bit: bool = False,
                          native_arch: str = "AMD64",
                          os_is_64bit: bool = True,
                          extra: Optional[Dict[str, str]] = None
                          ) -> "object":
    """The environment an installer process should see.

    This is the base block with the WOW64 redirection applied for the
    installer's bitness, plus the MSI context properties.

    Parameters
    ----------
    base_block:
        The environment to start from.  Defaults to the process block.
    context:
        The installation context the installer is running in.
    app_is_32bit:
        ``True`` when the installer itself is a 32-bit program.
    extra:
        Additional variables to add (installer-specific settings).
    """
    from .environment import (EnvironmentBlock, EnvScope,   # local: avoid cycle
                              apply_wow64_redirection, get_default_block)
    if base_block is None:
        base_block = get_default_block()

    block = apply_wow64_redirection(base_block,
                                    app_is_32bit=app_is_32bit,
                                    native_arch=native_arch,
                                    os_is_64bit=os_is_64bit)
    for name, value in msi_properties(context).items():
        block[name] = value
    if extra:
        for name, value in extra.items():
            block[name] = value
    return block


def installer_path_entries(target: InstallTarget,
                           extra_dirs: Optional[List[str]] = None
                           ) -> List[str]:
    """The directories an installer should add to ``PATH``.

    A per-machine install puts its ``bin`` directory in the *system*
    ``PATH``; a per-user install puts it in the *user* ``PATH``.  The
    system ``PATH`` is what every user of the machine sees.
    """
    entries = [_join(target.app_dir, "bin")]
    if extra_dirs:
        entries.extend(extra_dirs)
    return [e for e in entries if e]


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    from .environment import EnvironmentBlock   # local: avoid cycle

    blk = EnvironmentBlock(host_fallback=False)
    blk["ProgramFiles"] = r"C:\Program Files"
    blk["ProgramFiles(x86)"] = r"C:\Program Files (x86)"
    blk["CommonProgramFiles"] = r"C:\Program Files\Common Files"
    blk["CommonProgramFiles(x86)"] = r"C:\Program Files (x86)\Common Files"
    blk["LocalAppData"] = r"C:\Users\me\AppData\Local"
    blk["AppData"] = r"C:\Users\me\AppData\Roaming"
    blk["ProgramData"] = r"C:\ProgramData"

    # 1. Per-machine on 64-bit Windows: a 64-bit package goes to
    #    Program Files, a 32-bit package to Program Files (x86).
    t64 = resolve_install_target("MyApp", InstallationContext.PER_MACHINE,
                                 app_is_32bit=False, os_is_64bit=True,
                                 block=blk)
    if t64.app_dir != r"C:\Program Files\MyApp":
        log.debug("64-bit app dir = %r", t64.app_dir)
        return False
    t32 = resolve_install_target("MyApp", InstallationContext.PER_MACHINE,
                                 app_is_32bit=True, os_is_64bit=True,
                                 block=blk)
    if t32.app_dir != r"C:\Program Files (x86)\MyApp":
        log.debug("32-bit app dir = %r", t32.app_dir)
        return False
    if not t32.wow64:
        return False

    # 2. Per-machine on a 32-bit OS: no x86 split.
    t32os = resolve_install_target("MyApp", InstallationContext.PER_MACHINE,
                                   app_is_32bit=False, os_is_64bit=False,
                                   block=blk)
    if t32os.app_dir != r"C:\Program Files\MyApp":
        return False

    # 3. Per-user goes under %LocalAppData%\Programs.
    tu = resolve_install_target("MyApp", InstallationContext.PER_USER,
                                block=blk)
    if tu.app_dir != r"C:\Users\me\AppData\Local\Programs\MyApp":
        log.debug("per-user app dir = %r", tu.app_dir)
        return False
    if tu.common_files != r"C:\Users\me\AppData\Local\Programs\Common":
        return False
    if not tu.uninstall_key.startswith("HKCU"):
        return False
    if tu.start_menu.startswith(r"C:\Users\me\AppData\Roaming\Microsoft"):
        pass
    else:
        log.debug("per-user start menu = %r", tu.start_menu)
        return False

    # 4. Per-machine uninstall entry lives under HKLM.
    if not t64.uninstall_key.startswith("HKLM"):
        return False

    # 5. MSI context properties.
    if msi_properties(InstallationContext.PER_MACHINE)["ALLUSERS"] != "1":
        return False
    if msi_properties(InstallationContext.PER_USER)["ALLUSERS"] != "":
        return False

    # 6. The installer environment carries the WOW64 rewrite.
    env = installer_environment(blk, app_is_32bit=True)
    if env.get("ProgramFiles") != r"C:\Program Files (x86)":
        return False
    if env.get("ProgramW6432") != r"C:\Program Files":
        return False
    if env.get("ALLUSERS") != "1":
        return False

    # 7. The PATH entries an installer would add.
    entries = installer_path_entries(t64)
    if entries != [r"C:\Program Files\MyApp\bin"]:
        return False

    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
