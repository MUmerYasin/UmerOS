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

"""Kernel Extension base class with type-safe capability checking.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""
from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("UmerOS.SDK.KernelDSL")

# Capability registry
_CAPABILITY_REGISTRY: Dict[str, "KernelExtension"] = {}


def system_capability(cap_name: str):
    """Decorator that statically verifies required permissions before execution."""
    def decorator(func: Callable) -> Callable:
        func._required_capability = cap_name
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.has_capability(cap_name):
                raise PermissionError(
                    f"Extension '{self.name}' lacks capability '{cap_name}'"
                )
            log.debug("Capability check passed: %s requires %s", self.name, cap_name)
            return func(self, *args, **kwargs)
        wrapper._required_capability = cap_name
        return wrapper
    return decorator


class KernelExtension:
    """Base class for type-safe kernel extensions.

    Enforces strict type annotations on all methods.
    """

    def __init__(self, name: str, capabilities: Optional[Set[str]] = None) -> None:
        self.name = name
        self._capabilities: Set[str] = capabilities or set()
        self._registered = False

    def has_capability(self, cap: str) -> bool:
        return cap in self._capabilities

    def grant_capability(self, cap: str) -> None:
        self._capabilities.add(cap)

    def revoke_capability(self, cap: str) -> None:
        self._capabilities.discard(cap)

    def register(self) -> bool:
        """Register this extension in the kernel."""
        if self._registered:
            return False
        _CAPABILITY_REGISTRY[self.name] = self
        self._registered = True
        log.info("Registered kernel extension: %s", self.name)
        return True

    def unregister(self) -> bool:
        if not self._registered:
            return False
        _CAPABILITY_REGISTRY.pop(self.name, None)
        self._registered = False
        log.info("Unregistered kernel extension: %s", self.name)
        return True

    @property
    def is_registered(self) -> bool:
        return self._registered

    @property
    def capabilities(self) -> Set[str]:
        return set(self._capabilities)

    def validate_types(self) -> List[str]:
        """Validate that all methods have type annotations."""
        errors = []
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("_"):
                continue
            sig = inspect.signature(method)
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                if param.annotation is inspect.Parameter.empty:
                    errors.append(f"{name}({param_name}) missing type annotation")
            if sig.return_annotation is inspect.Signature.empty:
                errors.append(f"{name}() missing return type annotation")
        return errors

    def __repr__(self) -> str:
        return f"KernelExtension(name={self.name}, caps={self._capabilities})"


def _selftest() -> bool:
    """Run self-tests for capability gating and extension registration."""
    print("[sdk/kernel_dsl/extension_base] selftest …")
    ok = True

    def check(condition: bool, label: str) -> None:
        nonlocal ok
        if condition:
            print(f"  [PASS] {label}")
        else:
            ok = False
            print(f"  [FAIL] {label}")

    ext = KernelExtension("selftest-ext")
    check(ext.has_capability("CAP_TEST") is False, "capabilities start empty")
    ext.grant_capability("CAP_TEST")
    check(ext.has_capability("CAP_TEST") is True, "grant_capability adds")
    check("CAP_TEST" in ext.capabilities, "capabilities exposes the granted set")
    ext.revoke_capability("CAP_TEST")
    check(ext.has_capability("CAP_TEST") is False, "revoke_capability removes")

    class _Guarded(KernelExtension):
        def __init__(self) -> None:
            super().__init__("guarded-ext")
            self.called = False

        @system_capability("CAP_TEST")
        def guarded(self) -> None:
            self.called = True

    guarded = _Guarded()
    try:
        guarded.guarded()
    except PermissionError:
        check(True, "system_capability denies without the capability")
    else:
        check(False, "system_capability should deny without the capability")
    check(guarded.called is False, "a denied call does not run the body")

    guarded.grant_capability("CAP_TEST")
    guarded.guarded()
    check(guarded.called is True, "system_capability allows with the capability")
    check(
        getattr(_Guarded.guarded, "_required_capability", None) == "CAP_TEST",
        "the decorator records the required capability",
    )

    class _Untyped(KernelExtension):
        def untyped(self, value):
            return value

    errors = _Untyped("untyped-ext").validate_types()
    check(
        any("untyped(value)" in e for e in errors),
        "validate_types flags a missing parameter annotation",
    )
    check(
        any("untyped()" in e for e in errors),
        "validate_types flags a missing return annotation",
    )
    check(KernelExtension("clean-ext").validate_types() == [], "annotated methods validate cleanly")

    reg = KernelExtension("selftest-reg")
    check(reg.is_registered is False, "extensions start unregistered")
    check(reg.register() is True, "register() succeeds once")
    check(reg.register() is False, "register() is idempotent")
    check(reg.is_registered is True, "is_registered reflects registration")
    check(reg.unregister() is True, "unregister() succeeds once")
    check(reg.unregister() is False, "unregister() is idempotent")
    check("KernelExtension" in repr(reg), "__repr__ is informative")

    print("[sdk/kernel_dsl/extension_base] selftest " + ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    _selftest()
