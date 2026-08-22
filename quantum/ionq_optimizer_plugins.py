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

"""Trapped-ion optimizer plugins for gate-stream optimization."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Tuple

__all__ = [
    "TrappedIonOptimizerPluginBase",
    "TrappedIonOptimizerPluginSimpleRules",
    "TrappedIonOptimizerPluginCompactGates",
    "TrappedIonOptimizerPluginCommuteGpi2ThroughMs",
    "run_trapped_ion_pipeline",
]

GateTuple = Tuple[str, tuple, tuple]
GateStream = List[GateTuple]

_NATIVE = {"gpi", "gpi2", "ms", "zz"}


class TrappedIonOptimizerPluginBase(ABC):
    @abstractmethod
    def run(self, stream: GateStream, **kwargs) -> GateStream:
        ...


class TrappedIonOptimizerPluginSimpleRules(TrappedIonOptimizerPluginBase):
    """Replace non-native gates with MS-based equivalents where possible."""

    def run(self, stream: GateStream, **kwargs) -> GateStream:
        result: GateStream = []
        i = 0
        while i < len(stream):
            name, params, qubits = stream[i]
            if name == "cx" and i + 1 < len(stream):
                next_name = stream[i + 1][0]
                if next_name == "h":
                    result.append(("ms", (0.0, 0.0), (qubits[0], qubits[1])))
                    result.append(stream[i + 1])
                    i += 2
                    continue
            if name not in _NATIVE:
                result.append(("ms", (0.0, 0.0), qubits) if len(qubits) == 2
                              else ("gpi2", (0.0,), qubits))
            else:
                result.append((name, params, qubits))
            i += 1
        return result


class TrappedIonOptimizerPluginCompactGates(TrappedIonOptimizerPluginBase):
    """Fuse consecutive GPI gates and cancel cancelling GPI2 pairs."""

    def run(self, stream: GateStream, **kwargs) -> GateStream:
        result: GateStream = []
        for gate_tuple in stream:
            name, params, qubits = gate_tuple
            if result and name == "gpi" and result[-1][0] == "gpi":
                if qubits == result[-1][2]:
                    prev_phi = result[-1][1][0] if result[-1][1] else 0.0
                    cur_phi = params[0] if params else 0.0
                    if abs(prev_phi - cur_phi) < 1e-9:
                        result.pop()
                    else:
                        result.pop()
                        result.append(("gpi2", (0.0,), qubits))
                    continue
            if result and name == "gpi2" and result[-1][0] == "gpi2":
                if qubits == result[-1][2]:
                    prev_phi = result[-1][1][0] if result[-1][1] else 0.0
                    cur_phi = params[0] if params else 0.0
                    if abs(prev_phi - cur_phi) < 1e-9:
                        result.pop()
                        continue
            result.append(gate_tuple)
        return result


class TrappedIonOptimizerPluginCommuteGpi2ThroughMs(TrappedIonOptimizerPluginBase):
    """Commute GPI2(φ) through MS(φ0,φ1) → MS(φ0+φ,φ1-φ) · GPI2(φ)."""

    def run(self, stream: GateStream, **kwargs) -> GateStream:
        result: GateStream = []
        i = 0
        while i < len(stream):
            name, params, qubits = stream[i]
            if (name == "gpi2" and i + 1 < len(stream)
                    and stream[i + 1][0] == "ms"):
                gpi2_phi = params[0] if params else 0.0
                ms_params = stream[i + 1][1]
                ms_qubits = stream[i + 1][2]
                ms_phi0 = ms_params[0] if len(ms_params) > 0 else 0.0
                ms_phi1 = ms_params[1] if len(ms_params) > 1 else 0.0
                # Move gpi2 to the other qubit of the MS gate
                other_qubit = ms_qubits[1] if qubits[0] == ms_qubits[0] else ms_qubits[0]
                if qubits[0] == ms_qubits[0]:
                    new_phi0 = ms_phi0 + gpi2_phi
                    new_phi1 = ms_phi1 - gpi2_phi
                else:
                    new_phi0 = ms_phi0 - gpi2_phi
                    new_phi1 = ms_phi1 + gpi2_phi
                result.append(("ms", (new_phi0, new_phi1), ms_qubits))
                result.append(("gpi2", (gpi2_phi,), (other_qubit,)))
                i += 2
                continue
            result.append((name, params, qubits))
            i += 1
        return result


def run_trapped_ion_pipeline(
    stream: GateStream,
    plugins=None,
) -> GateStream:
    """Run all optimizer plugins in sequence on the gate stream."""
    if plugins is None:
        plugins = [
            TrappedIonOptimizerPluginSimpleRules(),
            TrappedIonOptimizerPluginCompactGates(),
            TrappedIonOptimizerPluginCommuteGpi2ThroughMs(),
        ]
    result = list(stream)
    for plugin in plugins:
        result = plugin.run(result)
    return result
