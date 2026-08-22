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

"""
Hardware-Native Gate Sets for Trapped-Ion and Superconducting Platforms.

Provides hardware-native gate classes, predefined gate sets, and utility
functions for optimizing circuits to specific hardware backends.

Usage:
    from quantum.native_gates import (
        HardwarePlatform, NativeGateSet, NativeGateSetInfo,
        get_native_gate_set, list_native_gates,
        decompose_to_native, get_native_decomposition,
    )

    # Get a gate set
    trap_ion = get_native_gate_set(HardwarePlatform.TRAPPED_ION)

    # Convert a standard gate to native form
    native_gates = decompose_to_native(x_gate, HardwarePlatform.TRAPPED_ION)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple, Union

import numpy as np

from .gates import Gate, I_GATE, X_GATE, Z_GATE, CNOT_GATE, CZ_GATE


# ---------------------------------------------------------------------------
# 1. Hardware Platform Enum
# ---------------------------------------------------------------------------

class HardwarePlatform(Enum):
    """Supported hardware platforms."""
    TRAPPED_ION = auto()
    SUPERCONDUCTING = auto()
    PHOTONIC = auto()
    NEUTRAL_ATOM = auto()
    QUANTUM_DOT = auto()


# ---------------------------------------------------------------------------
# 2. Native Gate Set Enum
# ---------------------------------------------------------------------------

class NativeGateSet(Enum):
    """Named native gate sets for each platform."""
    TRAPPED_ION_UNIVERSAL = auto()
    TRAPPED_ION_MINIMAL = auto()
    SUPERCONDUCTING_UNIVERSAL = auto()
    SUPERCONDUCTING_MINIMAL = auto()
    PHOTONIC_UNIVERSAL = auto()


# ---------------------------------------------------------------------------
# 3. Native Gate Set Info (dataclass)
# ---------------------------------------------------------------------------

@dataclass
class NativeGateSetInfo:
    """Metadata for a native gate set."""
    platform: HardwarePlatform
    gate_set: NativeGateSet
    gate_names: List[str]
    description: str


# ---------------------------------------------------------------------------
# 4. Gate Base Class (inherited by all native gates)
# ---------------------------------------------------------------------------

class NativeGate(Gate):
    """Base class for all hardware-native gates.

    Extends Gate with a hardware_platform attribute.
    """

    def __init__(
        self,
        name: str,
        num_qubits: int,
        matrix: np.ndarray,
        params: Optional[list] = None,
        hardware_platform: HardwarePlatform = HardwarePlatform.TRAPPED_ION,
    ):
        super().__init__(name=name, num_qubits=num_qubits, matrix=matrix, params=params)
        self.hardware_platform = hardware_platform

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NativeGate):
            return False
        return (
            self.name == other.name
            and self.num_qubits == other.num_qubits
            and self.hardware_platform == other.hardware_platform
            and np.allclose(self.matrix, other.matrix)
        )

    def __hash__(self) -> int:
        return hash((self.name, self.num_qubits, self.hardware_platform))


# ---------------------------------------------------------------------------
# 5. Hardware-Native Gate Classes — Trapped Ion
# ---------------------------------------------------------------------------

class GPI(NativeGate):
    """GPI gate: single-qubit rotation about axis in XY-plane.

    GPI(φ) = [[0, e^{-iφ}], [e^{iφ}, 0]]

    Parameters:
        phi: Rotation angle in radians.
    """

    def __init__(self, phi: float = 0.0):
        self._phi = phi
        matrix = np.array([
            [0, np.exp(-1j * phi)],
            [np.exp(1j * phi), 0],
        ], dtype=complex)
        super().__init__(
            name="GPI",
            num_qubits=1,
            matrix=matrix,
            params=[phi],
            hardware_platform=HardwarePlatform.TRAPPED_ION,
        )

    @property
    def phi(self) -> float:
        return self._phi

    def inverse(self) -> "GPI":
        return GPI(-self._phi)

    def power(self, exponent: float) -> "GPI":
        return GPI(self._phi * exponent)


class GPI2(NativeGate):
    """GPI2 gate: π/2 rotation about axis in XY-plane.

    GPI2(φ) = (1/√2) * [[1, -ie^{-iφ}], [-ie^{iφ}, 1]]

    Parameters:
        phi: Rotation angle in radians.
    """

    def __init__(self, phi: float = 0.0):
        self._phi = phi
        c = 1.0 / np.sqrt(2)
        matrix = c * np.array([
            [1, -1j * np.exp(-1j * phi)],
            [-1j * np.exp(1j * phi), 1],
        ], dtype=complex)
        super().__init__(
            name="GPI2",
            num_qubits=1,
            matrix=matrix,
            params=[phi],
            hardware_platform=HardwarePlatform.TRAPPED_ION,
        )

    @property
    def phi(self) -> float:
        return self._phi

    def inverse(self) -> "GPI2":
        return GPI2(self._phi + math.pi)

    def power(self, exponent: float) -> "GPI2":
        return GPI2(self._phi * exponent)


class MS(NativeGate):
    """Molmer-Sorensen gate: native two-qubit entangling gate.

    MS(θ, φ) = exp(-iθ(cos(φ)⊗XX + sin(φ)⊗YY))

    The matrix has two 2×2 blocks:
    - Block (|00⟩,|11⟩): exp(-iθ·a·σx) with a = cos(φ) - sin(φ)
    - Block (|01⟩,|10⟩): exp(-iθ·b·σx) with b = cos(φ) + sin(φ)

    Parameters:
        theta: Entangling strength.
        phi: Rotation angle in XY-plane.
    """

    def __init__(self, theta: float = math.pi / 2, phi: float = 0.0):
        self._theta = theta
        self._phi = phi
        a = np.cos(phi) - np.sin(phi)
        b = np.cos(phi) + np.sin(phi)
        ca = np.cos(a * theta)
        sa = np.sin(a * theta)
        cb = np.cos(b * theta)
        sb = np.sin(b * theta)
        matrix = np.array([
            [ca, 0, 0, -1j * sa],
            [0, cb, -1j * sb, 0],
            [0, -1j * sb, cb, 0],
            [-1j * sa, 0, 0, ca],
        ], dtype=complex)
        super().__init__(
            name="MS",
            num_qubits=2,
            matrix=matrix,
            params=[theta, phi],
            hardware_platform=HardwarePlatform.TRAPPED_ION,
        )

    @property
    def theta(self) -> float:
        return self._theta

    @property
    def phi(self) -> float:
        return self._phi

    def inverse(self) -> "MS":
        return MS(-self._theta, self._phi)


# ---------------------------------------------------------------------------
# 6. Hardware-Native Gate Classes — Superconducting
# ---------------------------------------------------------------------------

class RZ(NativeGate):
    """RZ gate: rotation about Z-axis.

    RZ(θ) = diag(e^{-iθ/2}, e^{iθ/2})

    Parameters:
        theta: Rotation angle in radians.
    """

    def __init__(self, theta: float = 0.0):
        self._theta = theta
        matrix = np.array([
            [np.exp(-1j * theta / 2), 0],
            [0, np.exp(1j * theta / 2)],
        ], dtype=complex)
        super().__init__(
            name="RZ",
            num_qubits=1,
            matrix=matrix,
            params=[theta],
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    @property
    def theta(self) -> float:
        return self._theta

    def inverse(self) -> "RZ":
        return RZ(-self._theta)

    def power(self, exponent: float) -> "RZ":
        return RZ(self._theta * exponent)


class U1(NativeGate):
    """U1 gate: phase gate.

    U1(λ) = diag(1, e^{iλ})

    Parameters:
        lam: Phase angle in radians.
    """

    def __init__(self, lam: float = 0.0):
        self._lam = lam
        matrix = np.array([
            [1, 0],
            [0, np.exp(1j * lam)],
        ], dtype=complex)
        super().__init__(
            name="U1",
            num_qubits=1,
            matrix=matrix,
            params=[lam],
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    @property
    def lam(self) -> float:
        return self._lam

    def inverse(self) -> "U1":
        return U1(-self._lam)

    def power(self, exponent: float) -> "U1":
        return U1(self._lam * exponent)


class U2(NativeGate):
    """U2 gate: π/2 rotation with phase.

    U2(φ, λ) = (1/√2) * [[1, -e^{iλ}], [e^{iφ}, e^{i(φ+λ)}]]

    Parameters:
        phi: Azimuthal angle.
        lam: Phase angle.
    """

    def __init__(self, phi: float = 0.0, lam: float = 0.0):
        self._phi = phi
        self._lam = lam
        c = 1.0 / np.sqrt(2)
        matrix = c * np.array([
            [1, -np.exp(1j * lam)],
            [np.exp(1j * phi), np.exp(1j * (phi + lam))],
        ], dtype=complex)
        super().__init__(
            name="U2",
            num_qubits=1,
            matrix=matrix,
            params=[phi, lam],
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    @property
    def phi(self) -> float:
        return self._phi

    @property
    def lam(self) -> float:
        return self._lam


class U3(NativeGate):
    """U3 gate: universal single-qubit rotation.

    U3(θ, φ, λ) = [[cos(θ/2), -e^{iλ}sin(θ/2)],
                     [e^{iφ}sin(θ/2), e^{i(φ+λ)}cos(θ/2)]]

    Parameters:
        theta: Polar angle.
        phi: Azimuthal angle.
        lam: Phase angle.
    """

    def __init__(self, theta: float = 0.0, phi: float = 0.0, lam: float = 0.0):
        self._theta = theta
        self._phi = phi
        self._lam = lam
        c = np.cos(theta / 2)
        s = np.sin(theta / 2)
        matrix = np.array([
            [c, -np.exp(1j * lam) * s],
            [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c],
        ], dtype=complex)
        super().__init__(
            name="U3",
            num_qubits=1,
            matrix=matrix,
            params=[theta, phi, lam],
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    @property
    def theta(self) -> float:
        return self._theta

    @property
    def phi(self) -> float:
        return self._phi

    @property
    def lam(self) -> float:
        return self._lam

    def inverse(self) -> "U3":
        return U3(-self._theta, -self._lam, -self._phi)


class ISwap(NativeGate):
    """iSWAP gate: native two-qubit gate for superconducting hardware.

    iSWAP = [[1,0,0,0],[0,0,i,0],[0,i,0,0],[0,0,0,1]]
    """

    def __init__(self):
        matrix = np.array([
            [1, 0, 0, 0],
            [0, 0, 1j, 0],
            [0, 1j, 0, 0],
            [0, 0, 0, 1],
        ], dtype=complex)
        super().__init__(
            name="iSwap",
            num_qubits=2,
            matrix=matrix,
            params=None,
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    def inverse(self) -> "ISwap":
        return ISwapDag()


class ISwapDag(NativeGate):
    """Dagger of iSWAP gate."""

    def __init__(self):
        matrix = np.array([
            [1, 0, 0, 0],
            [0, 0, -1j, 0],
            [0, -1j, 0, 0],
            [0, 0, 0, 1],
        ], dtype=complex)
        super().__init__(
            name="iSwap†",
            num_qubits=2,
            matrix=matrix,
            params=None,
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    def inverse(self) -> "ISwap":
        return ISwap()


class SQISwap(NativeGate):
    """√iSWAP gate: half-power of iSWAP, native on some hardware.

    SQISwap = [[1,0,0,0],[0,(1+i)/2,(1-i)/2,0],
                [0,(1-i)/2,(1+i)/2,0],[0,0,0,1]]
    """

    def __init__(self):
        a = (1 + 1j) / 2
        b = (1 - 1j) / 2
        matrix = np.array([
            [1, 0, 0, 0],
            [0, a, b, 0],
            [0, b, a, 0],
            [0, 0, 0, 1],
        ], dtype=complex)
        super().__init__(
            name="√iSwap",
            num_qubits=2,
            matrix=matrix,
            params=None,
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )


class ECR(NativeGate):
    """Echoed Cross-Resonance gate: native 2-qubit gate for transmons.

    ECR = (1/√2) * [[0,0,1,i],[0,0,i,1],[1,-i,0,0],[-i,1,0,0]]
    """

    def __init__(self):
        c = 1.0 / np.sqrt(2)
        matrix = c * np.array([
            [0, 0, 1, 1j],
            [0, 0, 1j, 1],
            [1, -1j, 0, 0],
            [-1j, 1, 0, 0],
        ], dtype=complex)
        super().__init__(
            name="ECR",
            num_qubits=2,
            matrix=matrix,
            params=None,
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    def inverse(self) -> "ECR":
        return ECRDag()


class ECRDag(NativeGate):
    """Dagger of ECR gate. ECR is Hermitian, so ECR† = ECR."""

    def __init__(self):
        c = 1.0 / np.sqrt(2)
        matrix = c * np.array([
            [0, 0, 1, 1j],
            [0, 0, 1j, 1],
            [1, -1j, 0, 0],
            [-1j, 1, 0, 0],
        ], dtype=complex)
        super().__init__(
            name="ECR†",
            num_qubits=2,
            matrix=matrix,
            params=None,
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    def inverse(self) -> "ECR":
        return ECR()


class SX(NativeGate):
    """√X gate: square root of Pauli-X.

    SX = [[1+i, 1-i], [1-i, 1+i]] / 2
    SX @ SX = X
    """

    def __init__(self):
        c = (1 + 1j) / 2
        d = (1 - 1j) / 2
        matrix = np.array([
            [c, d],
            [d, c],
        ], dtype=complex)
        super().__init__(
            name="SX",
            num_qubits=1,
            matrix=matrix,
            params=None,
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    def inverse(self) -> "SXdg":
        return SXdg()


class SXdg(NativeGate):
    """Dagger of √X gate."""

    def __init__(self):
        c = (1 - 1j) / 2
        d = (1 + 1j) / 2
        matrix = np.array([
            [c, d],
            [d, c],
        ], dtype=complex)
        super().__init__(
            name="SX†",
            num_qubits=1,
            matrix=matrix,
            params=None,
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    def inverse(self) -> "SX":
        return SX()


class ZZ(NativeGate):
    """ZZ interaction gate: native two-qubit entangling gate.

    ZZ(θ) = diag(e^{-iθ}, e^{iθ}, e^{iθ}, e^{-iθ})

    Parameters:
        theta: Rotation angle.
    """

    def __init__(self, theta: float = 0.0):
        self._theta = theta
        matrix = np.diag([
            np.exp(-1j * theta),
            np.exp(1j * theta),
            np.exp(1j * theta),
            np.exp(-1j * theta),
        ]).astype(complex)
        super().__init__(
            name="ZZ",
            num_qubits=2,
            matrix=matrix,
            params=[theta],
            hardware_platform=HardwarePlatform.SUPERCONDUCTING,
        )

    @property
    def theta(self) -> float:
        return self._theta

    def inverse(self) -> "ZZ":
        return ZZ(-self._theta)

    def power(self, exponent: float) -> "ZZ":
        return ZZ(self._theta * exponent)


# ---------------------------------------------------------------------------
# 7. Gate Set Registry
# ---------------------------------------------------------------------------

_TRAPPED_ION_UNIVERSAL_INFO = NativeGateSetInfo(
    platform=HardwarePlatform.TRAPPED_ION,
    gate_set=NativeGateSet.TRAPPED_ION_UNIVERSAL,
    gate_names=["GPI", "GPI2", "MS"],
    description=(
        "Universal trapped-ion gate set. GPI and GPI2 provide arbitrary "
        "single-qubit rotations; MS is the native two-qubit entangling gate."
    ),
)

_TRAPPED_ION_MINIMAL_INFO = NativeGateSetInfo(
    platform=HardwarePlatform.TRAPPED_ION,
    gate_set=NativeGateSet.TRAPPED_ION_MINIMAL,
    gate_names=["GPI", "GPI2", "MS"],
    description=(
        "Minimal trapped-ion gate set using GPI for all single-qubit rotations "
        "and MS for entanglement."
    ),
)

_SUPERCONDUCTING_UNIVERSAL_INFO = NativeGateSetInfo(
    platform=HardwarePlatform.SUPERCONDUCTING,
    gate_set=NativeGateSet.SUPERCONDUCTING_UNIVERSAL,
    gate_names=["U3", "U1", "ECR", "RZ"],
    description=(
        "Universal superconducting gate set. U3 and U1 provide arbitrary "
        "single-qubit rotations; ECR is the native two-qubit gate; RZ "
        "is used for virtual Z rotations."
    ),
)

_SUPERCONDUCTING_MINIMAL_INFO = NativeGateSetInfo(
    platform=HardwarePlatform.SUPERCONDUCTING,
    gate_set=NativeGateSet.SUPERCONDUCTING_MINIMAL,
    gate_names=["SX", "RZ", "ECR"],
    description=(
        "Minimal superconducting gate set using SX and RZ for single-qubit "
        "rotations and ECR for entanglement. Common in IBM backends."
    ),
)

_PHOTONIC_UNIVERSAL_INFO = NativeGateSetInfo(
    platform=HardwarePlatform.PHOTONIC,
    gate_set=NativeGateSet.PHOTONIC_UNIVERSAL,
    gate_names=["U3", "U1", "ZZ", "ISwap"],
    description=(
        "Photonic platform gate set. Uses standard single-qubit gates with "
        "ZZ and iSwap as native two-qubit interactions."
    ),
)

_GATE_SET_REGISTRY: dict[NativeGateSet, NativeGateSetInfo] = {
    NativeGateSet.TRAPPED_ION_UNIVERSAL: _TRAPPED_ION_UNIVERSAL_INFO,
    NativeGateSet.TRAPPED_ION_MINIMAL: _TRAPPED_ION_MINIMAL_INFO,
    NativeGateSet.SUPERCONDUCTING_UNIVERSAL: _SUPERCONDUCTING_UNIVERSAL_INFO,
    NativeGateSet.SUPERCONDUCTING_MINIMAL: _SUPERCONDUCTING_MINIMAL_INFO,
    NativeGateSet.PHOTONIC_UNIVERSAL: _PHOTONIC_UNIVERSAL_INFO,
}


# ---------------------------------------------------------------------------
# 8. Utility Functions
# ---------------------------------------------------------------------------

def get_native_gate_set(platform: HardwarePlatform) -> NativeGateSetInfo:
    """Return the default native gate set info for a given platform.

    Args:
        platform: Hardware platform.

    Returns:
        NativeGateSetInfo for the default set of that platform.

    Raises:
        ValueError: If no default set is defined for the platform.
    """
    platform_defaults = {
        HardwarePlatform.TRAPPED_ION: NativeGateSet.TRAPPED_ION_UNIVERSAL,
        HardwarePlatform.SUPERCONDUCTING: NativeGateSet.SUPERCONDUCTING_UNIVERSAL,
        HardwarePlatform.PHOTONIC: NativeGateSet.PHOTONIC_UNIVERSAL,
    }
    if platform not in platform_defaults:
        raise ValueError(f"No default native gate set defined for {platform.name}")
    gate_set = platform_defaults[platform]
    return _GATE_SET_REGISTRY[gate_set]


def list_native_gates(gate_set: NativeGateSet) -> list[str]:
    """List the gate names in a native gate set.

    Args:
        gate_set: Which gate set to list.

    Returns:
        List of gate name strings.

    Raises:
        ValueError: If the gate set is not in the registry.
    """
    if gate_set not in _GATE_SET_REGISTRY:
        raise ValueError(f"Unknown gate set: {gate_set.name}")
    return list(_GATE_SET_REGISTRY[gate_set].gate_names)


def decompose_to_native(gate: Gate, platform: HardwarePlatform) -> list[NativeGate]:
    """Decompose a standard gate into a list of native gates.

    Currently supports decomposition of common standard gates to their
    native equivalents. Returns a single-element list for gates that
    have a direct native equivalent.

    Args:
        gate: Standard gate from quantum.gates to decompose.
        platform: Target hardware platform.

    Returns:
        List of native gates equivalent to the input gate.

    Raises:
        NotImplementedError: If the gate cannot be decomposed to native form.
    """
    name = gate.name.upper()

    if platform == HardwarePlatform.TRAPPED_ION:
        return _decompose_trapped_ion(gate, name)
    elif platform == HardwarePlatform.SUPERCONDUCTING:
        return _decompose_superconducting(gate, name)
    else:
        raise NotImplementedError(
            f"Decomposition not implemented for {platform.name}"
        )


def _decompose_trapped_ion(gate: Gate, name: str) -> list[NativeGate]:
    """Decompose a gate to trapped-ion native gates."""
    if name == "X":
        return [GPI(0.0), GPI2(0.0), GPI(0.0)]
    elif name == "H":
        return [GPI2(0.0), GPI(math.pi / 2)]
    elif name == "Z":
        return [GPI(math.pi / 2), GPI2(0.0), GPI(math.pi / 2)]
    elif name == "GPI":
        phi = gate.params[0] if gate.params else 0.0
        return [GPI(phi)]
    elif name == "GPI2":
        phi = gate.params[0] if gate.params else 0.0
        return [GPI2(phi)]
    elif name == "MS":
        theta = gate.params[0] if gate.params else math.pi / 2
        phi = gate.params[1] if len(gate.params) > 1 else 0.0
        return [MS(theta, phi)]
    elif name == "CNOT":
        return [MS(math.pi / 2, 0.0), GPI(0.0), GPI2(0.0)]
    else:
        raise NotImplementedError(
            f"Trapped-ion decomposition not implemented for gate: {gate.name}"
        )


def _decompose_superconducting(gate: Gate, name: str) -> list[NativeGate]:
    """Decompose a gate to superconducting native gates."""
    if name == "U3":
        theta = gate.params[0] if gate.params else 0.0
        phi = gate.params[1] if len(gate.params) > 1 else 0.0
        lam = gate.params[2] if len(gate.params) > 2 else 0.0
        return [U3(theta, phi, lam)]
    elif name == "U1":
        lam = gate.params[0] if gate.params else 0.0
        return [U1(lam)]
    elif name == "U2":
        phi = gate.params[0] if gate.params else 0.0
        lam = gate.params[1] if len(gate.params) > 1 else 0.0
        return [U2(phi, lam)]
    elif name == "RZ":
        theta = gate.params[0] if gate.params else 0.0
        return [RZ(theta)]
    elif name == "X":
        return [U3(math.pi, 0.0, math.pi)]
    elif name == "H":
        return [U3(math.pi / 2, 0.0, math.pi)]
    elif name == "Z":
        return [U1(math.pi)]
    elif name == "ECR":
        return [ECR()]
    elif name == "ISWAP":
        return [ISwap()]
    elif name == "SX":
        return [SX()]
    elif name == "ZZ":
        theta = gate.params[0] if gate.params else 0.0
        return [ZZ(theta)]
    elif name == "CNOT":
        return [ECR(), RZ(math.pi / 2), U3(math.pi, 0.0, math.pi)]
    else:
        raise NotImplementedError(
            f"Superconducting decomposition not implemented for gate: {gate.name}"
        )


def get_native_decomposition(
    gate: Gate, gate_set: NativeGateSet
) -> list[NativeGate]:
    """Decompose a gate using a specific named gate set.

    Convenience wrapper that maps gate set enum to platform and
    delegates to decompose_to_native.

    Args:
        gate: Standard gate to decompose.
        gate_set: Target native gate set.

    Returns:
        List of native gates.

    Raises:
        ValueError: If the gate set is not in the registry.
    """
    if gate_set not in _GATE_SET_REGISTRY:
        raise ValueError(f"Unknown gate set: {gate_set.name}")
    info = _GATE_SET_REGISTRY[gate_set]
    return decompose_to_native(gate, info.platform)
