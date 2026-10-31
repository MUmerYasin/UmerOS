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

"""Algebraic Data Types for UmerOS Kernel Extension DSL.

Result/Option structures with exhaustiveness validation.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""
from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, Union
from dataclasses import dataclass

T = TypeVar("T")
E = TypeVar("E")


class Result(Generic[T, E]):
    """Result type: Success(value) or Failure(error)."""

    def is_success(self) -> bool:
        return isinstance(self, Success)

    def is_failure(self) -> bool:
        return isinstance(self, Failure)

    def unwrap(self) -> T:
        if isinstance(self, Success):
            return self.value
        raise RuntimeError(f"Cannot unwrap Failure: {self}")

    def unwrap_or(self, default: T) -> T:
        if isinstance(self, Success):
            return self.value
        return default

    def map(self, fn: Callable[[T], Any]) -> "Result":
        if isinstance(self, Success):
            return Success(fn(self.value))
        return self


@dataclass
class Success(Result[T, E]):
    value: T

    def __repr__(self) -> str:
        return f"Success({self.value!r})"


@dataclass
class Failure(Result[T, E]):
    error: E

    def __repr__(self) -> str:
        return f"Failure({self.error!r})"


class Option(Generic[T]):
    """Option type: Some(value) or None_."""

    def is_some(self) -> bool:
        return isinstance(self, Some)

    def is_none(self) -> bool:
        return isinstance(self, None_)

    def unwrap(self) -> T:
        if isinstance(self, Some):
            return self.value
        raise RuntimeError("Cannot unwrap None")

    def unwrap_or(self, default: T) -> T:
        if isinstance(self, Some):
            return self.value
        return default


@dataclass
class Some(Option[T]):
    value: T

    def __repr__(self) -> str:
        return f"Some({self.value!r})"


class None_(Option[T]):
    def __repr__(self) -> str:
        return "None"