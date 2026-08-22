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

"""IonQ equivalence rules for gate decomposition."""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

__all__ = [
    "rz_to_gpi", "ry_to_gpi", "rx_to_gpi", "u1_to_gpi", "u3_to_gpi",
    "cr_to_ms", "cx_to_ms", "cy_to_ms", "cz_to_ms",
    "add_equivalences", "apply_equivalences", "build_default_library",
]

GateTuple = Tuple[str, tuple, tuple]


def rz_to_gpi(angle: float, qubit: int = 0) -> List[GateTuple]:
    """Rz(angle) decomposed into gpi/gpi2 on the given qubit."""
    half = angle / 2.0
    return [
        ("gpi2", (-half,), (qubit,)),
        ("gpi", (math.pi / 2,), (qubit,)),
        ("gpi2", (half,), (qubit,)),
    ]


def ry_to_gpi(angle: float, qubit: int = 0) -> List[GateTuple]:
    """Ry(angle) decomposed into gpi/gpi2."""
    half = angle / 2.0
    return [
        ("gpi2", (math.pi / 2,), (qubit,)),
        ("gpi", (-half,), (qubit,)),
        ("gpi2", (-math.pi / 2,), (qubit,)),
        ("gpi", (half,), (qubit,)),
    ]


def rx_to_gpi(angle: float, qubit: int = 0) -> List[GateTuple]:
    """Rx(angle) decomposed into gpi/gpi2."""
    half = angle / 2.0
    return [
        ("gpi", (math.pi / 2,), (qubit,)),
        ("gpi2", (-half,), (qubit,)),
        ("gpi", (-math.pi / 2,), (qubit,)),
        ("gpi2", (half,), (qubit,)),
    ]


def u1_to_gpi(angle: float, qubit: int = 0) -> List[GateTuple]:
    """U1(angle) decomposed into gpi/gpi2."""
    return [
        ("gpi2", (angle / 2.0,), (qubit,)),
    ]


def u3_to_gpi(theta: float, phi: float, lam: float, qubit: int = 0) -> List[GateTuple]:
    """U3(theta, phi, lam) decomposed into gpi/gpi2."""
    return [
        ("gpi", (-lam / 2.0,), (qubit,)),
        ("gpi2", (-theta / 2.0,), (qubit,)),
        ("gpi", ((phi + lam) / 2.0,), (qubit,)),
        ("gpi2", (theta / 2.0,), (qubit,)),
    ]


def cr_to_ms(angle: float, control: int = 0, target: int = 1) -> List[GateTuple]:
    """CR(angle) decomposed into MS + single-qubit gates."""
    half = angle / 2.0
    return [
        ("gpi2", (half,), (target,)),
        ("ms", (0.0, half), (control, target)),
        ("gpi2", (-half,), (target,)),
        ("gpi", (math.pi,), (control,)),
    ]


def cx_to_ms(control: int = 0, target: int = 1) -> List[GateTuple]:
    """CX decomposed into MS + single-qubit gates."""
    return [
        ("gpi2", (-math.pi / 2,), (target,)),
        ("ms", (0.0, 0.0), (control, target)),
        ("gpi2", (math.pi / 2,), (target,)),
        ("gpi", (math.pi,), (control,)),
    ]


def cy_to_ms(control: int = 0, target: int = 1) -> List[GateTuple]:
    """CY decomposed into MS + single-qubit gates."""
    return [
        ("gpi", (math.pi / 2,), (target,)),
        ("gpi2", (-math.pi / 2,), (target,)),
        ("ms", (0.0, 0.0), (control, target)),
        ("gpi2", (math.pi / 2,), (target,)),
        ("gpi", (math.pi,), (control,)),
        ("gpi", (-math.pi / 2,), (target,)),
    ]


def cz_to_ms(control: int = 0, target: int = 1) -> List[GateTuple]:
    """CZ decomposed into MS + single-qubit gates."""
    return [
        ("gpi2", (-math.pi / 2,), (target,)),
        ("gpi", (math.pi,), (target,)),
        ("ms", (0.0, 0.0), (control, target)),
        ("gpi", (math.pi,), (control,)),
        ("gpi2", (math.pi / 2,), (target,)),
    ]


def build_default_library() -> Dict[str, callable]:
    """Return a dict mapping gate names to decomposition functions."""
    return {
        "rz": rz_to_gpi,
        "ry": ry_to_gpi,
        "rx": rx_to_gpi,
        "u1": u1_to_gpi,
        "u3": u3_to_gpi,
        "cr": cr_to_ms,
        "cx": cx_to_ms,
        "cy": cy_to_ms,
        "cz": cz_to_ms,
    }


def add_equivalences(library: Dict[str, callable], gate_name: str, decomposition_fn: callable) -> Dict[str, callable]:
    """Add a new equivalence rule to a library, returning the updated library."""
    library[gate_name] = decomposition_fn
    return library


def apply_equivalences(stream: List[GateTuple], library: Dict[str, callable]) -> List[GateTuple]:
    """Apply equivalence rules to a gate stream, returning the rewritten stream."""
    native = {"gpi", "gpi2", "ms", "zz"}
    result = []
    for gate_tuple in stream:
        name = gate_tuple[0]
        if name in native:
            result.append(gate_tuple)
        elif name in library:
            params = gate_tuple[1]
            qubits = gate_tuple[2]
            rule_fn = library[name]
            if name in ("rz", "ry", "rx", "u1"):
                angle = params[0] if params else 0.0
                qubit = qubits[0] if qubits else 0
                result.extend(rule_fn(angle, qubit))
            elif name == "u3":
                theta = params[0] if len(params) > 0 else 0.0
                phi = params[1] if len(params) > 1 else 0.0
                lam = params[2] if len(params) > 2 else 0.0
                qubit = qubits[0] if qubits else 0
                result.extend(rule_fn(theta, phi, lam, qubit))
            elif name in ("cx", "cy", "cz"):
                control = qubits[0] if len(qubits) > 0 else 0
                target = qubits[1] if len(qubits) > 1 else 1
                result.extend(rule_fn(control, target))
            elif name == "cr":
                angle = params[0] if params else math.pi
                control = qubits[0] if len(qubits) > 0 else 0
                target = qubits[1] if len(qubits) > 1 else 1
                result.extend(rule_fn(angle, control, target))
            else:
                result.append(gate_tuple)
        else:
            result.append(gate_tuple)
    return result
