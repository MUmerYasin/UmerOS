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

"""UmerOS Type-Safe Kernel Extension DSL.

Cangjie-inspired type-safe scripting layer for kernel extensions.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""
from __future__ import annotations

from .extension_base import KernelExtension, system_capability
from .types import Result, Success, Failure, Option, Some, None_

__all__ = [
    "KernelExtension",
    "system_capability",
    "Result",
    "Success",
    "Failure",
    "Option",
    "Some",
    "None_",
]


_SELFTEST_MODULES = ("types", "extension_base")


def _selftest() -> bool:
    """Verify the DSL surface imports and every child passes its own selftest."""
    import importlib

    print("[sdk/kernel_dsl] selftest …")
    ok = True
    package = importlib.import_module(__name__)
    missing = [name for name in __all__ if not hasattr(package, name)]
    if missing:
        ok = False
        print(f"  [FAIL] missing public names: {missing}")
    else:
        print("  [PASS] every public name is importable")

    for mod_name in _SELFTEST_MODULES:
        module = importlib.import_module(f"{__name__}.{mod_name}")
        child = getattr(module, "_selftest", None)
        if child is None:
            ok = False
            print(f"  [FAIL] {mod_name} has no _selftest()")
        elif child() is not True:
            ok = False
            print(f"  [FAIL] {mod_name}._selftest() failed")
        else:
            print(f"  [PASS] {mod_name} selftest")

    print("[sdk/kernel_dsl] selftest " + ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    _selftest()
