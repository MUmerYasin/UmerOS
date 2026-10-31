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


def _selftest() -> bool:
    """Run self-tests for the Result and Option types."""
    print("[sdk/kernel_dsl/types] selftest …")
    ok = True

    def check(condition: bool, label: str) -> None:
        nonlocal ok
        if condition:
            print(f"  [PASS] {label}")
        else:
            ok = False
            print(f"  [FAIL] {label}")

    good = Success(41)
    check(good.is_success() is True, "Success reports success")
    check(good.is_failure() is False, "Success is not a failure")
    check(good.unwrap() == 41, "Success unwraps its value")
    check(good.map(lambda v: v + 1).unwrap() == 42, "Result.map transforms a Success")

    bad = Failure("boom")
    check(bad.is_failure() is True, "Failure reports failure")
    check(bad.map(lambda v: v).is_failure() is True, "Result.map passes a Failure through")
    try:
        bad.unwrap()
    except RuntimeError:
        check(True, "Failure.unwrap raises RuntimeError")
    else:
        check(False, "Failure.unwrap should raise")

    check(bad.unwrap_or(7) == 7, "Failure.unwrap_or returns the default")
    check(good.unwrap_or(7) == 41, "Success.unwrap_or returns the value")

    some = Some(3)
    check(some.is_some() is True, "Some reports some")
    check(some.unwrap() == 3, "Some unwraps its value")

    none = None_()
    check(none.is_none() is True, "None_ reports none")
    check(none.unwrap_or(9) == 9, "None_.unwrap_or returns the default")
    try:
        none.unwrap()
    except RuntimeError:
        check(True, "None_.unwrap raises RuntimeError")
    else:
        check(False, "None_.unwrap should raise")

    print("[sdk/kernel_dsl/types] selftest " + ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    _selftest()
