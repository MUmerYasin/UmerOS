"""UmerOS Type-Safe Kernel Extension DSL.

Cangjie-inspired type-safe scripting layer for kernel extensions.
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