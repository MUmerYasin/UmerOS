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

"""UmerOS Quantum Computing CLI.

Command-line interface for quantum computing operations:

    uumeros quantum info                    — show system status
    uumeros quantum providers               — list available providers
    uumeros quantum backends --provider ibm — list backends
    uumeros quantum transpile --file circuit.qasm --target ibm_brisbane
    uumeros quantum execute --file circuit.json --provider ibm --shots 1024
    uumeros quantum jobs --provider ibm --status running
    uumeros quantum qrng --bits 256
    uumeros quantum qkd --protocol bb84 --bits 1024

Usage:
    python -m quantum.cli <command> [options]
    python quantum/cli.py <command> [options]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

from .circuit import QuantumCircuit, QuantumRegister, ClassicalRegister
from .gates import H_GATE, X_GATE, CNOT_GATE


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def cmd_info(args: argparse.Namespace) -> int:
    """Show quantum computing system information."""
    print("=" * 60)
    print("  UmerOS Quantum Computing Stack")
    print("=" * 60)
    print()
    print("  Layers:")
    print("    L0 — Provider Abstraction & Cloud Execution")
    print("    L1 — Core (Gates, Circuits, Operators)")
    print("    L2 — Simulation (Statevector, Density Matrix)")
    print("    L3 — Transpilation (Hardware-aware, Native Gates)")
    print("    L4 — Execution (Primitives, Dynamic Circuits)")
    print("    L5 — Algorithms & Circuit Library")
    print("    L6 — QRNG, QKD, Error Correction")
    print()
    print("  Supported Providers:")
    print("    - IBM Quantum (superconducting)")
    print("    - IonQ (trapped ion)")
    print("    - AWS Braket (multi-vendor)")
    print("    - Rigetti QCS (superconducting)")
    print()

    # Show native gate sets
    try:
        from .native_gates import list_native_gates
        gates = list_native_gates()
        print("  Native Gate Sets:")
        for platform, gate_list in gates.items():
            print(f"    {platform}: {', '.join(gate_list[:5])}...")
    except Exception:
        print("  Native Gate Sets: (loading...)")

    print()
    return 0


def cmd_providers(args: argparse.Namespace) -> int:
    """List available quantum providers."""
    providers = []

    try:
        from .providers.ibm_provider import IBMQuantumProvider
        providers.append(("IBM Quantum", "Superconducting", "ibm, ibm_quantum"))
    except Exception:
        pass

    try:
        from .providers.ionq_provider import IonQProvider
        providers.append(("IonQ", "Trapped Ion", "ionq"))
    except Exception:
        pass

    try:
        from .providers.braket_provider import BraketProvider
        providers.append(("AWS Braket", "Multi-vendor", "braket, aws_braket"))
    except Exception:
        pass

    try:
        from .providers.rigetti_provider import RigettiProvider
        providers.append(("Rigetti QCS", "Superconducting", "rigetti, qcs"))
    except Exception:
        pass

    if not providers:
        print("No providers available. Install dependencies first.")
        return 1

    print(f"{'Provider':<20} {'Architecture':<20} {'Aliases'}")
    print("-" * 60)
    for name, arch, aliases in providers:
        print(f"{name:<20} {arch:<20} {aliases}")
    print()
    return 0


def cmd_backends(args: argparse.Namespace) -> int:
    """List backends for a provider."""
    provider_name = args.provider.lower()

    if provider_name in ("ibm", "ibm_quantum"):
        try:
            from .providers.ibm_provider import IBMQuantumProvider
            p = IBMQuantumProvider(api_token=args.token)
            backends = p.list_backends()
            print(f"IBM Quantum Backends:")
            for b in backends:
                status = "online" if b.status == "online" else "offline"
                print(f"  {b.name}: {b.num_qubits} qubits, {status}")
        except Exception as e:
            print(f"Error: {e}")
            return 1

    elif provider_name == "ionq":
        try:
            from .providers.ionq_provider import IonQProvider
            p = IonQProvider(api_key=args.token)
            backends = p.list_backends()
            print(f"IonQ Backends:")
            for b in backends:
                print(f"  {b.name}: {b.num_qubits} qubits")
        except Exception as e:
            print(f"Error: {e}")
            return 1

    elif provider_name in ("braket", "aws_braket"):
        try:
            from .providers.braket_provider import BraketProvider
            p = BraketProvider(region=args.region or "us-east-1")
            backends = p.list_backends()
            print(f"AWS Braket Backends:")
            for b in backends:
                print(f"  {b.name}: {b.num_qubits} qubits ({b.provider})")
        except Exception as e:
            print(f"Error: {e}")
            return 1

    elif provider_name in ("rigetti", "qcs"):
        try:
            from .providers.rigetti_provider import RigettiProvider
            p = RigettiProvider()
            backends = p.list_backends()
            print(f"Rigetti QCS Backends:")
            for b in backends:
                print(f"  {b.name}: {b.num_qubits} qubits")
        except Exception as e:
            print(f"Error: {e}")
            return 1

    else:
        print(f"Unknown provider: {provider_name}")
        return 1

    return 0


def cmd_transpile(args: argparse.Namespace) -> int:
    """Transpile a circuit for a target backend."""
    try:
        if args.file:
            circuit = _load_circuit(args.file)
        else:
            print("Creating example Bell state circuit...")
            q = QuantumRegister(2, "q")
            c = ClassicalRegister(2, "c")
            circuit = QuantumCircuit(q, c)
            circuit.h(0)
            circuit.cx(0, 1)
            circuit.measure(q[0], c[0])
            circuit.measure(q[1], c[1])

        target = args.target or "ibm_brisbane"
        print(f"Transpiling for target: {target}")
        print(f"  Original depth: {circuit.depth()}")
        print(f"  Original gates: {len(circuit.instructions)}")

        # Apply basic transpilation
        from .transpiler import transpile
        transpiled = transpile(circuit, target=target)

        print(f"  Transpiled depth: {transpiled.depth()}")
        print(f"  Transpiled gates: {len(transpiled.instructions)}")
        print()

        if args.output:
            with open(args.output, "w") as f:
                json.dump({
                    "instructions": [
                        {"gate": inst.gate.name, "qubits": list(inst.qubits)}
                        for inst in transpiled.instructions
                    ]
                }, f, indent=2)
            print(f"Saved to: {args.output}")

    except Exception as e:
        print(f"Transpilation error: {e}")
        return 1

    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    """Execute a circuit on a quantum backend."""
    try:
        if args.file:
            circuit = _load_circuit(args.file)
        else:
            print("Creating example GHZ state circuit...")
            q = QuantumRegister(3, "q")
            c = ClassicalRegister(3, "c")
            circuit = QuantumCircuit(q, c)
            circuit.h(0)
            circuit.cx(0, 1)
            circuit.cx(1, 2)
            circuit.measure(q[0], c[0])
            circuit.measure(q[1], c[1])
            circuit.measure(q[2], c[2])

        provider_name = args.provider.lower()
        shots = args.shots or 1024

        print(f"Executing on {provider_name} backend...")
        print(f"  Shots: {shots}")

        if provider_name in ("ibm", "ibm_quantum"):
            from .providers.ibm_provider import IBMQuantumProvider
            p = IBMQuantumProvider(api_token=args.token)
            backend = p.get_backend(args.backend or "ibm_brisbane")
            job = backend.run(circuit, shots=shots)
            result = job.result()
            print(f"  Job ID: {job.job_id}")
            print(f"  Counts: {result.counts}")

        elif provider_name == "ionq":
            from .providers.ionq_provider import IonQProvider
            p = IonQProvider(api_key=args.token)
            backend = p.get_backend(args.backend or "ionq_harmony")
            job = backend.run(circuit, shots=shots)
            result = job.result()
            print(f"  Job ID: {job.job_id}")
            print(f"  Counts: {result.counts}")

        elif provider_name in ("braket", "aws_braket"):
            from .providers.braket_provider import BraketProvider
            p = BraketProvider(region=args.region or "us-east-1")
            backend = p.get_backend(args.backend or "SV1")
            job = backend.run(circuit, shots=shots)
            result = job.result()
            print(f"  Job ID: {job.job_id}")
            print(f"  Counts: {result.counts}")

        elif provider_name in ("rigetti", "qcs"):
            from .providers.rigetti_provider import RigettiProvider
            p = RigettiProvider()
            backend = p.get_backend(args.backend or "Aspen-M-3")
            job = backend.run(circuit, shots=shots)
            result = job.result()
            print(f"  Job ID: {job.job_id}")
            print(f"  Counts: {result.counts}")

        else:
            print(f"Unknown provider: {provider_name}")
            return 1

    except Exception as e:
        print(f"Execution error: {e}")
        return 1

    return 0


def cmd_jobs(args: argparse.Namespace) -> int:
    """List jobs for a provider."""
    provider_name = args.provider.lower()

    try:
        if provider_name in ("ibm", "ibm_quantum"):
            from .providers.ibm_provider import IBMQuantumProvider
            p = IBMQuantumProvider(api_token=args.token)
            session = p.open_session()
            jobs = session.list_jobs(status=args.status)
            print(f"IBM Quantum Jobs:")
            for job in jobs:
                print(f"  {job.job_id}: {job.status.value}")

        elif provider_name == "ionq":
            from .providers.ionq_provider import IonQProvider
            p = IonQProvider(api_key=args.token)
            session = p.open_session()
            jobs = session.list_jobs(status=args.status)
            print(f"IonQ Jobs:")
            for job in jobs:
                print(f"  {job.job_id}: {job.status.value}")

        else:
            print(f"Provider {provider_name} not yet supported for job listing.")
            return 1

    except Exception as e:
        print(f"Error listing jobs: {e}")
        return 1

    return 0


def cmd_qrng(args: argparse.Namespace) -> int:
    """Generate quantum random numbers."""
    try:
        from .qrng import QRNG

        qrng = QRNG()
        bits = args.bits or 256

        print(f"Generating {bits} random bits...")
        random_bits = qrng.generate_random_bits(bits)
        print(f"  Result: {random_bits[:80]}{'...' if len(random_bits) > 80 else ''}")
        print(f"  Length: {len(random_bits)} bits")

        if args.output:
            with open(args.output, "w") as f:
                f.write(random_bits)
            print(f"  Saved to: {args.output}")

    except Exception as e:
        print(f"QRNG error: {e}")
        return 1

    return 0


def cmd_qkd(args: argparse.Namespace) -> int:
    """Run Quantum Key Distribution."""
    try:
        from .qkd import BB84, E91

        protocol = args.protocol or "bb84"
        bits = args.bits or 1024

        print(f"Running {protocol.upper()} QKD with {bits} bits...")

        if protocol == "bb84":
            session = BB84(num_bits=bits)
            result = session.run()
        elif protocol == "e91":
            session = E91(num_bits=bits)
            result = session.run()
        else:
            print(f"Unknown protocol: {protocol}")
            return 1

        print(f"  Key length: {len(result.key)} bits")
        print(f"  QBER: {result.qber:.4f}")
        print(f"  Secure: {result.secure}")

    except Exception as e:
        print(f"QKD error: {e}")
        return 1

    return 0


def cmd_error_correction(args: argparse.Namespace) -> int:
    """Demonstrate quantum error correction."""
    try:
        from .error_correction import BitFlipCode, PhaseFlipCode, ShorCode, SteaneCode

        code_name = args.code or "bit_flip"
        codes = {
            "bit_flip": BitFlipCode,
            "phase_flip": PhaseFlipCode,
            "shor": ShorCode,
            "steane": SteaneCode,
        }

        if code_name not in codes:
            print(f"Unknown code: {code_name}")
            print(f"Available: {', '.join(codes.keys())}")
            return 1

        code = codes[code_name]()
        print(f"{code_name.replace('_', ' ').title()} Quantum Error Correction")
        print(f"  Physical qubits: {code.num_physical_qubits}")
        print(f"  Logical qubits: {code.num_logical_qubits}")
        print(f"  Distance: {code.distance}")

        # Show encoding
        from .circuit import QuantumCircuit
        q = QuantumRegister(code.num_physical_qubits)
        c = ClassicalRegister(code.num_logical_qubits)
        circuit = QuantumCircuit(q, c)

        print(f"  Encoding circuit depth: {circuit.depth()}")

    except Exception as e:
        print(f"Error correction error: {e}")
        return 1

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_circuit(filepath: str) -> QuantumCircuit:
    """Load a circuit from a file (JSON or QASM)."""
    if filepath.endswith(".json"):
        with open(filepath) as f:
            data = json.load(f)
        q = QuantumRegister(data.get("num_qubits", 2))
        c = ClassicalRegister(data.get("num_clbits", 2))
        circuit = QuantumCircuit(q, c)
        for inst in data.get("instructions", []):
            gate_name = inst["gate"]
            qubits = inst["qubits"]
            if gate_name == "h":
                circuit.h(qubits[0])
            elif gate_name == "x":
                circuit.x(qubits[0])
            elif gate_name == "cx":
                circuit.cx(qubits[0], qubits[1])
            elif gate_name == "measure":
                circuit.measure(qubits[0], qubits[0] if len(qubits) > 1 else 0)
        return circuit
    elif filepath.endswith(".qasm"):
        # Simple QASM parser
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        circuit = QuantumCircuit(q, c)
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line.startswith("h "):
                    circuit.h(int(line.split()[1]))
                elif line.startswith("x "):
                    circuit.x(int(line.split()[1]))
                elif line.startswith("cx "):
                    parts = line.split()[1].split(",")
                    circuit.cx(int(parts[0]), int(parts[1]))
        return circuit
    else:
        raise ValueError(f"Unsupported file format: {filepath}")


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="quantum",
        description="UmerOS Quantum Computing CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # info
    subparsers.add_parser("info", help="Show quantum system info")

    # providers
    subparsers.add_parser("providers", help="List available providers")

    # backends
    p_backends = subparsers.add_parser("backends", help="List backends")
    p_backends.add_argument("--provider", "-p", required=True, help="Provider name")
    p_backends.add_argument("--token", "-t", help="API token")
    p_backends.add_argument("--region", "-r", help="AWS region")

    # transpile
    p_transpile = subparsers.add_parser("transpile", help="Transpile circuit")
    p_transpile.add_argument("--file", "-f", help="Circuit file (JSON/QASM)")
    p_transpile.add_argument("--target", "-t", help="Target backend")
    p_transpile.add_argument("--output", "-o", help="Output file")

    # execute
    p_exec = subparsers.add_parser("execute", help="Execute circuit")
    p_exec.add_argument("--file", "-f", help="Circuit file (JSON/QASM)")
    p_exec.add_argument("--provider", "-p", required=True, help="Provider name")
    p_exec.add_argument("--backend", "-b", help="Backend name")
    p_exec.add_argument("--shots", "-s", type=int, help="Number of shots")
    p_exec.add_argument("--token", "-t", help="API token")
    p_exec.add_argument("--region", "-r", help="AWS region")

    # jobs
    p_jobs = subparsers.add_parser("jobs", help="List jobs")
    p_jobs.add_argument("--provider", "-p", required=True, help="Provider name")
    p_jobs.add_argument("--status", help="Filter by status")
    p_jobs.add_argument("--token", "-t", help="API token")

    # qrng
    p_qrng = subparsers.add_parser("qrng", help="Generate random numbers")
    p_qrng.add_argument("--bits", "-b", type=int, help="Number of bits")
    p_qrng.add_argument("--output", "-o", help="Output file")

    # qkd
    p_qkd = subparsers.add_parser("qkd", help="Quantum Key Distribution")
    p_qkd.add_argument("--protocol", help="Protocol (bb84/e91)")
    p_qkd.add_argument("--bits", "-b", type=int, help="Number of bits")

    # error-correction
    p_ec = subparsers.add_parser("error-correction", help="Error correction demo")
    p_ec.add_argument("--code", "-c", help="Code name (bit_flip/phase_flip/shor/steane)")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "info": cmd_info,
        "providers": cmd_providers,
        "backends": cmd_backends,
        "transpile": cmd_transpile,
        "execute": cmd_execute,
        "jobs": cmd_jobs,
        "qrng": cmd_qrng,
        "qkd": cmd_qkd,
        "error-correction": cmd_error_correction,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
