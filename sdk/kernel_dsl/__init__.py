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