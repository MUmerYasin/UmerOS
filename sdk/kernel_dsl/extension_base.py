"""Kernel Extension base class with type-safe capability checking."""
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