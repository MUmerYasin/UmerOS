"""IonQ-native gate definitions."""
from __future__ import annotations

from .gates import Gate
import numpy as np
import math

__all__ = [
    "IonQGate", "GPIGate", "GPI2Gate", "MSGate", "ZZGate", "get_ionq_gate",
]


class IonQGate(Gate):
    def __init__(self, name: str, num_qubits: int, matrix, params=None):
        super().__init__(name, num_qubits, matrix, params)

    def to_matrix(self) -> np.ndarray:
        return np.array(self.matrix, dtype=np.complex128)

    def to_dict(self) -> dict:
        return {"gate": self.name, "phases": list(self.params or [])}


class GPIGate(IonQGate):
    def __init__(self, phi: float = 0.0):
        m = np.array([
            [np.exp(-1j * phi) * 1j, 0],
            [0, np.exp(1j * phi) * (-1j)],
        ])
        super().__init__("gpi", 1, m, [phi])
        self.phi = phi


class GPI2Gate(IonQGate):
    def __init__(self, phi: float = 0.0):
        s = 1.0 / math.sqrt(2.0)
        m = s * np.array([
            [1, -1j * np.exp(-1j * phi)],
            [-1j * np.exp(1j * phi), 1],
        ])
        super().__init__("gpi2", 1, m, [phi])
        self.phi = phi


class MSGate(IonQGate):
    def __init__(self, phi0: float = 0.0, phi1: float = 0.0):
        s = 1.0 / math.sqrt(2.0)
        m = s * np.array([
            [1, 0, 0, -1j * np.exp(-1j * (phi0 + phi1))],
            [0, 1, -1j * np.exp(1j * (phi0 - phi1)), 0],
            [0, -1j * np.exp(-1j * (phi0 - phi1)), 1, 0],
            [-1j * np.exp(1j * (phi0 + phi1)), 0, 0, 1],
        ])
        super().__init__("ms", 2, m, [phi0, phi1])
        self.phi0 = phi0
        self.phi1 = phi1


class ZZGate(IonQGate):
    def __init__(self, phi0: float = 0.0, phi1: float = 0.0):
        m = np.array([
            [np.exp(-1j * phi0), 0, 0, 0],
            [0, np.exp(1j * phi0), 0, 0],
            [0, 0, np.exp(1j * phi1), 0],
            [0, 0, 0, np.exp(-1j * phi1)],
        ])
        super().__init__("zz", 2, m, [phi0, phi1])
        self.phi0 = phi0
        self.phi1 = phi1


def get_ionq_gate(name: str, params=None) -> IonQGate:
    p = params or []
    mapping = {
        "gpi": lambda: GPIGate(p[0] if p else 0.0),
        "gpi2": lambda: GPI2Gate(p[0] if p else 0.0),
        "ms": lambda: MSGate(p[0] if p else 0.0, p[1] if len(p) > 1 else 0.0),
        "zz": lambda: ZZGate(p[0] if p else 0.0, p[1] if len(p) > 1 else 0.0),
    }
    if name not in mapping:
        raise ValueError(f"Unknown IonQ gate: {name}")
    return mapping[name]()
