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

"""Visualization — Circuit and quantum state visualization tools.

Provides ASCII circuit drawing, state visualization, and optional
matplotlib plotting for quantum circuits and states.
"""

from __future__ import annotations

import math
from typing import Optional, List, Dict, Any

from .circuit import QuantumCircuit, QuantumRegister, ClassicalRegister


# ---------------------------------------------------------------------------
# ASCII Circuit Drawing
# ---------------------------------------------------------------------------

def draw_circuit(circuit: QuantumCircuit) -> str:
    """Draw a quantum circuit as ASCII art.

    Args:
        circuit: Quantum circuit to draw

    Returns:
        ASCII representation of the circuit
    """
    n_qubits = circuit.num_qubits
    if n_qubits == 0:
        return "Empty circuit"

    lines: List[List[str]] = [[] for _ in range(n_qubits)]
    wire_len = 3  # Minimum line length

    for inst in circuit.instructions:
        # Add wire segments
        target_len = max(wire_len, inst.qubits[-1] + 3)
        while wire_len < target_len:
            for q in range(n_qubits):
                lines[q].append("─")
            wire_len += 1

        if inst.gate is None:
            continue

        gate_name = inst.gate.name
        params_str = ""
        if inst.params:
            params_str = f"({', '.join(f'{p:.2f}' for p in inst.params)})"

        if len(inst.qubits) == 1:
            q = inst.qubits[0]
            label = f"[{gate_name}{params_str}]"
            padding = max(0, len(label) - 1)
            lines[q].append(label)
            for i in range(n_qubits):
                if i != q:
                    if lines[i][-1] != " " * len(lines[i][-1]):
                        lines[i].append("─" * len(label))
                    else:
                        lines[i].append("─" * padding)

        elif len(inst.qubits) == 2:
            q1, q2 = sorted(inst.qubits)
            label = f"[{gate_name}]"
            lines[q1].append(label)
            lines[q2].append(label)
            for i in range(q1 + 1, q2):
                lines[i].append("│")

        elif len(inst.qubits) == 3:
            q1, q2, q3 = sorted(inst.qubits)
            label = f"[{gate_name}]"
            lines[q1].append(label)
            lines[q2].append(label)
            lines[q3].append(label)
            for i in range(q1 + 1, q3):
                if i != q2:
                    lines[i].append("│")

    # Build header and footer
    header = []
    footer = []
    for q in range(n_qubits):
        qreg_name = f"q{q}"
        header.append(f"q{q} ─")
        footer.append(f"     ")

    # Combine lines
    result = []
    for q in range(n_qubits):
        line_str = "".join(lines[q]) if lines[q] else ""
        result.append(f"q{q} ─{line_str}")

    return "\n".join(result)


def draw_circuit_compact(circuit: QuantumCircuit) -> str:
    """Draw a compact ASCII circuit representation.

    Args:
        circuit: Quantum circuit to draw

    Returns:
        Compact ASCII representation
    """
    n_qubits = circuit.num_qubits
    if n_qubits == 0:
        return "Empty circuit"

    # Simple text representation
    lines = []
    for inst in circuit.instructions:
        if inst.gate is None:
            continue
        parts = [inst.gate.name]
        if inst.params:
            parts.append(f"({', '.join(f'{p:.2f}' for p in inst.params)})")
        parts.append(f"q{inst.qubits}")
        lines.append(" ".join(parts))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State Visualization
# ---------------------------------------------------------------------------

def statevector_to_ascii(statevector, num_qubits: int, threshold: float = 0.01) -> str:
    """Convert a statevector to ASCII representation.

    Args:
        statevector: Statevector to visualize
        num_qubits: Number of qubits
        threshold: Amplitude threshold for display

    Returns:
        ASCII representation of the state
    """
    if hasattr(statevector, 'data'):
        data = statevector.data
    else:
        data = statevector

    lines = []
    for i, amp in enumerate(data):
        if abs(amp) > threshold:
            prob = abs(amp) ** 2
            phase = math.degrees(math.atan2(amp.imag, amp.real))
            binary = format(i, f'0{num_qubits}b')
            lines.append(
                f"|{binary}⟩: {amp.real:+.4f}{amp.imag:+.4f}i "
                f"(P={prob:.4f}, θ={phase:.1f}°)"
            )

    return "\n".join(lines)


def density_matrix_ascii(density_matrix, num_qubits: int,
                         threshold: float = 0.01) -> str:
    """Convert a density matrix to ASCII representation.

    Args:
        density_matrix: Density matrix to visualize
        num_qubits: Number of qubits
        threshold: Element threshold for display

    Returns:
        ASCII representation of the density matrix
    """
    if hasattr(density_matrix, 'data'):
        data = density_matrix.data
    else:
        data = density_matrix

    dim = data.shape[0]
    lines = ["  " + "  ".join(
        f"|{format(j, f'0{num_qubits}b')}⟩" for j in range(dim)
    )]

    for i in range(dim):
        row = [f"|{format(i, f'0{num_qubits}b')}⟩"]
        for j in range(dim):
            val = data[i, j]
            if abs(val) > threshold:
                row.append(f"{val.real:+.3f}{val.imag:+.3f}i")
            else:
                row.append("  .  ")
        lines.append("  ".join(row))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bloch Sphere (Text)
# ---------------------------------------------------------------------------

def bloch_sphere_ascii(theta: float, phi: float, label: str = "") -> str:
    """Create a text representation of a Bloch sphere with a point.

    Args:
        theta: Polar angle (0 to π)
        phi: Azimuthal angle (0 to 2π)
        label: Optional label

    Returns:
        ASCII Bloch sphere
    """
    # Convert spherical to Cartesian
    x = math.sin(theta) * math.cos(phi)
    y = math.sin(theta) * math.sin(phi)
    z = math.cos(theta)

    # Simple 2D projection
    cx, cy = 5, 3
    px = int(cx + x * 3)
    py = int(cy - z * 3)

    lines = [
        "  Bloch Sphere  ",
        "    ┌─────┐    ",
        f"  │ {label} │    " if label else "    │     │    ",
        "  │  |  |  │    ",
        f" ─┼──┼──┼─┼──  ",
        f"  │ {px},{py} │    ",
        "  │  |  |  │    ",
        "  └─────┘    ",
        f"  θ={math.degrees(theta):.1f}° φ={math.degrees(phi):.1f}°",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Circuit Statistics
# ---------------------------------------------------------------------------

def circuit_stats(circuit: QuantumCircuit) -> Dict[str, Any]:
    """Get statistics about a quantum circuit.

    Args:
        circuit: Quantum circuit to analyze

    Returns:
        Dictionary of circuit statistics
    """
    gate_counts = {}
    total_params = 0

    for inst in circuit.instructions:
        if inst.gate is not None:
            name = inst.gate.name
            gate_counts[name] = gate_counts.get(name, 0) + 1
            if inst.params:
                total_params += len(inst.params)

    return {
        "num_qubits": circuit.num_qubits,
        "num_clbits": circuit.num_clbits,
        "num_instructions": len(circuit.instructions),
        "gate_counts": gate_counts,
        "total_params": total_params,
        "depth": len(circuit.instructions),  # Approximation
    }


# ---------------------------------------------------------------------------
# Matrix Visualization
# ---------------------------------------------------------------------------

def matrix_ascii(matrix, label: str = "Matrix") -> str:
    """Convert a matrix to ASCII art.

    Args:
        matrix: Matrix to visualize
        label: Matrix label

    Returns:
        ASCII matrix
    """
    if hasattr(matrix, 'data'):
        data = matrix.data
    else:
        data = matrix

    rows, cols = data.shape
    lines = [f"  {label} ({rows}x{cols})"]

    # Column header
    header = "  " + "".join(f"{j:6}" for j in range(cols))
    lines.append(header)

    for i in range(rows):
        row_str = f"{i:2}" + "".join(
            f"{data[i, j]:6.3f}" if abs(data[i, j]) > 0.001 else "  .  "
            for j in range(cols)
        )
        lines.append(row_str)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------

def histogram_ascii(data: Dict[str, int], title: str = "Results",
                    max_width: int = 40) -> str:
    """Create an ASCII histogram.

    Args:
        data: Dictionary of label → count
        title: Histogram title
        max_width: Maximum bar width

    Returns:
        ASCII histogram
    """
    if not data:
        return "No data"

    max_count = max(data.values())
    lines = [f"  {title}", ""]

    for label, count in sorted(data.items(), key=lambda x: -x[1]):
        bar_len = int((count / max_count) * max_width) if max_count > 0 else 0
        bar = "█" * bar_len
        lines.append(f"  {label:10} | {bar} {count}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def draw(circuit: QuantumCircuit) -> str:
    """Draw a circuit (alias for draw_circuit)."""
    return draw_circuit(circuit)


def print_state(statevector, num_qubits: int) -> None:
    """Print a statevector in readable format."""
    print(statevector_to_ascii(statevector, num_qubits))


def print_density(density_matrix, num_qubits: int) -> None:
    """Print a density matrix in readable format."""
    print(density_matrix_ascii(density_matrix, num_qubits))


def plot_histogram(counts: Dict[str, int], title: str = "Results") -> None:
    """Print a histogram of measurement results."""
    print(histogram_ascii(counts, title))


# ---------------------------------------------------------------------------
# Matplotlib Integration (Optional)
# ---------------------------------------------------------------------------

def plot_circuit(circuit: QuantumCircuit, filename: Optional[str] = None,
                 show: bool = False) -> None:
    """Plot a circuit using matplotlib.

    Args:
        circuit: Quantum circuit to plot
        filename: Optional filename to save
        show: Whether to display the plot
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError:
        print("matplotlib not installed. Using ASCII fallback.")
        print(draw_circuit(circuit))
        return

    n_qubits = circuit.num_qubits
    fig, ax = plt.subplots(1, 1, figsize=(12, n_qubits * 0.8 + 1))
    ax.set_xlim(0, len(circuit.instructions) * 2 + 2)
    ax.set_ylim(-1, n_qubits)
    ax.set_aspect('equal')
    ax.axis('off')

    # Draw wires
    for q in range(n_qubits):
        ax.plot([0, len(circuit.instructions) * 2], [q, q], 'k-', linewidth=1)

    # Draw gates
    x_pos = 1
    for inst in circuit.instructions:
        if inst.gate is None:
            continue

        for q in inst.qubits:
            rect = patches.Rectangle((x_pos - 0.3, q - 0.3), 0.6, 0.6,
                                     linewidth=1, edgecolor='blue',
                                     facecolor='lightblue')
            ax.add_patch(rect)
            ax.text(x_pos, q, inst.gate.name, ha='center', va='center',
                    fontsize=8, fontweight='bold')

        x_pos += 2

    plt.tight_layout()

    if filename:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()


def plot_state(statevector, num_qubits: int, filename: Optional[str] = None,
               show: bool = False) -> None:
    """Plot a statevector using matplotlib.

    Args:
        statevector: Statevector to plot
        num_qubits: Number of qubits
        filename: Optional filename to save
        show: Whether to display the plot
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Using ASCII fallback.")
        print(statevector_to_ascii(statevector, num_qubits))
        return

    if hasattr(statevector, 'data'):
        data = statevector.data
    else:
        data = statevector

    probs = [abs(a) ** 2 for a in data]
    labels = [format(i, f'0{num_qubits}b') for i in range(len(data))]

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.5), 5))
    bars = ax.bar(labels, probs, color='steelblue', edgecolor='navy')
    ax.set_xlabel('Basis State')
    ax.set_ylabel('Probability')
    ax.set_title('Quantum State Probabilities')
    plt.xticks(rotation=45 if len(labels) > 8 else 0, fontsize=8)

    plt.tight_layout()
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

__all__ = [
    "draw_circuit",
    "draw_circuit_compact",
    "statevector_to_ascii",
    "density_matrix_ascii",
    "bloch_sphere_ascii",
    "circuit_stats",
    "matrix_ascii",
    "histogram_ascii",
    "draw",
    "print_state",
    "print_density",
    "plot_histogram",
    "plot_circuit",
    "plot_state",
]
