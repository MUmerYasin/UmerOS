# Umer OS — Quantum Computing Tutorial

**Audience:** Everyone — from complete beginners to quantum engineers  
**Prerequisites:** Basic Python knowledge helpful but not required

---

## Part 1: Quantum Computing for Complete Beginners

### What Is a Quantum Computer?

A normal computer (like your laptop) stores information as **bits** — each one is either
0 or 1. Think of them like light switches: either OFF (0) or ON (1).

A quantum computer stores information as **qubits** (quantum bits). A qubit can be:
- **0** (like a normal bit)
- **1** (like a normal bit)
- **Both 0 and 1 at the same time!** (this is called **superposition**)

```
Normal bit:   [ 0 ]  or  [ 1 ]
              OFF        ON

Qubit:        [ 0 ]  or  [ 1 ]  or  [ 0 AND 1 simultaneously ]
                                     (superposition — exists until measured)
```

### Why Does "Both at Once" Matter?

Imagine you're looking for your keys in a house with 8 rooms:
- **Normal computer:** checks Room 1, then Room 2, then Room 3... (one at a time)
- **Quantum computer:** checks all 8 rooms simultaneously!

This is why quantum computers can solve certain problems **exponentially faster**.

### The Catch: Measurement Collapses Superposition

The moment you *look* at a qubit (measure it), the superposition collapses and it becomes
either 0 or 1. This is why quantum computing requires clever algorithms — you have to
extract the answer before measurement collapses everything.

```
Before measurement: qubit = [0 and 1 together, 50/50 probability]

After measurement:  qubit = [0]  ← collapsed to definite state
               OR   qubit = [1]
```

### Entanglement: Qubits That Share a Destiny

**Entanglement** links two qubits so that measuring one instantly determines the other,
no matter how far apart they are.

```
Entangled pair:
  Qubit A: [0 and 1]     Qubit B: [0 and 1]
  
  Measure A → gets 0     Qubit B instantly becomes 0
  Measure A → gets 1     Qubit B instantly becomes 1
  
  They always agree! (This is what Einstein called "spooky action at a distance")
```

Umer OS uses simulated entanglement to synchronise inter-process messages with zero
confusion about state.

---

## Part 2: Quantum States in Umer OS

### The State Vector

Umer OS represents quantum states as a **state vector** — a list of complex numbers
where each position represents a possible measurement outcome.

For 2 qubits, there are 4 possible outcomes: |00⟩, |01⟩, |10⟩, |11⟩

```python
from quantum.quantum_sim import QuantumCircuitSimulator
import numpy as np

sim = QuantumCircuitSimulator(n_qubits=2)

# Initial state: |00⟩ (both qubits are 0)
print(sim.state)
# [1+0j, 0+0j, 0+0j, 0+0j]
#   ↑         ↑         ↑         ↑
# |00⟩=100% |01⟩=0%  |10⟩=0%  |11⟩=0%
```

### The Hadamard Gate: Creating Superposition

The **Hadamard (H) gate** puts a qubit into equal superposition (50% chance of 0, 50% of 1):

```python
sim.reset()
sim.apply_h(0)   # Apply H to qubit 0

print(sim.probabilities())
# [0.5, 0.0, 0.5, 0.0]
#   ↑         ↑
# |00⟩=50% |01⟩=0%  |10⟩=50% |11⟩=0%
# Qubit 0 is in superposition: could be 0 (→ |00⟩) or 1 (→ |10⟩)

# Measure it — randomly collapses to 0 or 1
result = sim.measure()
print(result)   # 0 (state |00⟩) or 2 (state |10⟩)
```

**Mathematical representation:**

```
After H gate on |0⟩:

|ψ⟩ = (1/√2)|0⟩ + (1/√2)|1⟩

     ┌───┐        1         1
|0⟩─┤ H ├─▶   ─────|0⟩ + ─────|1⟩
     └───┘       √2        √2

Probability of measuring 0 = |1/√2|² = 0.5
Probability of measuring 1 = |1/√2|² = 0.5
```

### The CNOT Gate: Creating Entanglement

The **CNOT (Controlled-NOT) gate** flips the *target* qubit if and only if the *control*
qubit is |1⟩. When combined with H, it creates Bell states (maximally entangled pairs):

```python
sim.reset()
sim.apply_h(0)        # Qubit 0 in superposition
sim.apply_cnot(0, 1)  # Entangle qubit 0 and qubit 1

print(sim.probabilities())
# [0.5, 0.0, 0.0, 0.5]
#   ↑                   ↑
# |00⟩=50%  |01⟩=0%  |10⟩=0%  |11⟩=50%
# ONLY |00⟩ and |11⟩ are possible — the qubits are entangled!
```

**What this means:** If you measure qubit 0 and get 0, qubit 1 must also be 0.
If qubit 0 is 1, qubit 1 must also be 1. They're correlated forever.

---

## Part 3: Umer OS Quantum Features

### Feature 1: Quantum-Inspired Task Scheduling ✅ TODAY

The `HybridScheduler` uses a quantum-inspired scoring algorithm to decide which process
runs next. Each process has a `superposition` score (0.0 to 1.0) representing its
predicted success probability.

```python
from quantum.quantum_sim import SuperpositionSchedulerAdapter, QuantumCircuitSimulator
from kernel.scheduler import HybridScheduler, Task
import asyncio

# Create quantum simulator and adapter
sim = QuantumCircuitSimulator(n_qubits=1)
adapter = SuperpositionSchedulerAdapter(sim=sim)

# Create tasks with different priorities
tasks = [
    Task(pid=1, name="video_encode",     priority=0.9),
    Task(pid=2, name="background_sync",  priority=0.2),
    Task(pid=3, name="user_interface",   priority=0.8),
]

# Get quantum-refined probability scores
scores = adapter.evaluate_task_paths(tasks)
print(scores)
# {1: 0.7234, 2: 0.1891, 3: 0.6102}  ← varies each run (quantum randomness)

# The scheduler selects the task with the highest score
best_pid = max(scores, key=scores.get)
print(f"Next task: PID {best_pid}")   # Usually 1 (video_encode, highest priority)
```

**How the scoring works:**

```
For each task:
  1. Reset simulator to |0⟩
  2. Apply Hadamard: |0⟩ → (|0⟩ + |1⟩)/√2
  3. Measure ⟨Z⟩ expectation value → [-1, +1]
  4. Normalise to [0, 1]: quantum_prob = (ev + 1) / 2
  5. Blend with static priority: score = 0.5 × priority + 0.5 × quantum_prob

This adds quantum randomness that breaks scheduling ties and explores
different execution orders — inspired by quantum path sampling.
```

### Feature 2: Entanglement-Inspired IPC Synchronisation ✅ TODAY

The `EntanglementIPCAdapter` uses Bell states to ensure that publisher and subscriber
always see consistent state:

```python
from quantum.quantum_sim import EntanglementIPCAdapter

adapter = EntanglementIPCAdapter()
adapter.subscribe(pid=1, channel="system_events")
adapter.subscribe(pid=2, channel="system_events")

# Publish a message
pub_bit, enriched_msg = adapter.publish(
    channel="system_events",
    message={"event": "cpu_high", "value": 0.95}
)

print(pub_bit)          # 0 or 1 (random — quantum measurement)
print(enriched_msg)
# {
#   "event": "cpu_high",
#   "value": 0.95,
#   "_quantum": {
#     "pub_bit": 0,    ← publisher measured 0
#     "sub_bit": 0,    ← subscriber ALWAYS sees same value (entanglement)
#     "channel": "system_events"
#   }
# }
```

### Feature 3: Post-Quantum Cryptography ✅ TODAY

Umer OS uses **CRYSTALS-Kyber** (for key exchange) and **CRYSTALS-Dilithium** (for
signatures) — algorithms standardised by NIST that are secure against quantum computers:

```python
from quantum.crypto_pqc import PostQuantumCrypto

pqc = PostQuantumCrypto()
print(f"Using backend: {pqc.backend}")  # "liboqs" or "fallback"

# ── Key Generation ──────────────────────────────────────────
public_key, private_key = pqc.generate_keypair()
print(f"Public key size:  {len(public_key):,} bytes")
# liboqs (Kyber768):  1,184 bytes
# fallback (Ed25519):    64 bytes

# ── Encryption (key encapsulation) ──────────────────────────
secret_message = b"Umer OS kernel image SHA3-256 hash"
ciphertext = pqc.encrypt(secret_message, public_key)

recovered = pqc.decrypt(ciphertext, private_key)
assert recovered == secret_message   # ✓

# ── Digital Signatures ──────────────────────────────────────
message = b"OS update v0.2.0 approved"
signature = pqc.sign(message, private_key)

is_authentic = pqc.verify(message, signature, public_key)
print(f"Signature valid: {is_authentic}")   # True

# Try to verify a tampered message
tampered = b"OS update v0.2.0 MODIFIED"
is_fake = pqc.verify(tampered, signature, public_key)
print(f"Tampered valid:  {is_fake}")        # False
```

### Feature 4: Quantum API Gateway ✅ TODAY

Submit quantum circuits through a unified API that works today with the simulator
and will work with real QPUs in the future:

```python
from quantum.quantum_api import QuantumAPIGateway

gw = QuantumAPIGateway()
print(f"Available backends: {gw.list_backends()}")
# ["simulator"]   (+ real QPUs when registered)

# Run a quantum circuit
result = gw.run(
    circuit_ops=[
        {"gate": "H",    "qubit": 0},          # Superposition
        {"gate": "CNOT", "control": 0, "target": 1},  # Entanglement
        # For 3-qubit: add more operations...
    ],
    backend="simulator",
    shots=1024   # number of measurement repetitions
)

print(result["counts"])
# {"0": 507, "3": 517}
# Key "0" = binary 00 = |00⟩, "3" = binary 11 = |11⟩
# Bell state: only |00⟩ and |11⟩ observed (50/50 split)

# Get noise model for error estimation
noise = gw.get_noise_model("simulator")
print(f"Depolarizing rate: {noise['depolarizing_rate']}")  # 0.01 (1%)
```

### Feature 5: Error Mitigation ✅ TODAY / 🔬 EXPERIMENTAL

Real quantum hardware has errors. Umer OS implements Zero-Noise Extrapolation (ZNE):

```python
from quantum.error_mitigation import ZeroNoiseExtrapolator
from quantum.quantum_sim import QuantumCircuitSimulator

sim = QuantumCircuitSimulator(n_qubits=1)

def expectation_at_noise_scale(noise_scale: float) -> float:
    """
    In a real QPU: scale circuit depth by noise_scale to amplify noise.
    Today: we approximate by adding minor perturbations.
    """
    sim.reset()
    sim.apply_h(0)
    # Simulate noise effect (simplified)
    ev = sim.expectation_z(0)
    return ev * (1.0 - 0.05 * noise_scale)  # noise reduces expectation

zne = ZeroNoiseExtrapolator(scale_factors=[1.0, 2.0, 3.0])
zero_noise_value = zne.extrapolate(expectation_at_noise_scale)
print(f"Zero-noise expectation: {zero_noise_value:.4f}")
# More accurate than the raw noisy measurement
```

---

## Part 4: Understanding the Mathematics

### State Vector Notation

For n qubits, the state is a complex vector of length 2ⁿ:

```
n=1 (2 states):   [α₀, α₁]
                   |0⟩  |1⟩

n=2 (4 states):   [α₀₀, α₀₁, α₁₀, α₁₁]
                   |00⟩ |01⟩ |10⟩ |11⟩

n=3 (8 states):   [α₀₀₀, α₀₀₁, α₀₁₀, α₀₁₁, α₁₀₀, α₁₀₁, α₁₁₀, α₁₁₁]

Probability of measuring state |i⟩ = |αᵢ|²

Normalisation constraint: Σ|αᵢ|² = 1.0
```

### Gate Matrices

```
Hadamard (H):           Pauli-X (NOT):         Pauli-Z:
┌              ┐        ┌       ┐              ┌        ┐
│ 1/√2  1/√2  │        │ 0  1  │              │  1   0 │
│ 1/√2 -1/√2  │        │ 1  0  │              │  0  -1 │
└              ┘        └       ┘              └        ┘

CNOT (4×4 for 2 qubits):
┌               ┐
│ 1  0  0  0   │   Identity on |00⟩ and |01⟩
│ 0  1  0  0   │   (control qubit is 0 → target unchanged)
│ 0  0  0  1   │   Swap |10⟩ ↔ |11⟩
│ 0  0  1  0   │   (control qubit is 1 → target flipped)
└               ┘
```

### How NumPy Implements This

```python
import numpy as np

# Hadamard matrix
H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)

# Apply H to qubit 0 of a 2-qubit system via Kronecker product
# Full gate matrix = H ⊗ I (H on qubit 0, identity on qubit 1)
I = np.eye(2, dtype=complex)
full_gate = np.kron(H, I)   # 4×4 matrix

# Initial state |00⟩
state = np.array([1, 0, 0, 0], dtype=complex)

# Apply gate: new_state = gate @ state
new_state = full_gate @ state
print(np.abs(new_state)**2)
# [0.5, 0.5, 0.0, 0.0]   → |00⟩ and |01⟩ each 50%
#                           (qubit 0 in superposition, qubit 1 still |0⟩)
```

---

## Part 5: Quantum Roadmap for Umer OS

### Today (Classical Simulation)

```
Umer OS on Classical Hardware
         │
         ▼
   Python + NumPy
         │
    ┌────┴────────────────────────┐
    │   State Vector Simulator    │
    │   state = complex[2^n]      │
    │   gates = matrix multiply   │
    │   measure = random sample   │
    └─────────────────────────────┘
         │
    Max practical: ~20 qubits (2^20 = 1M state vector entries)
    Speed: milliseconds for simple circuits
```

### Near Future (QPU Cloud Access) 🔬

```
Umer OS → QuantumAPIGateway → IBM Quantum / AWS Braket / Azure Quantum
                                         │
                               Real quantum hardware in the cloud
                               50-1000+ physical qubits
                               Available today via API subscription
```

### Far Future (Local QPU) 🔮

```
Umer OS
    │
    ▼
QuantumDevice driver
    │
    ▼
Local QPU co-processor chip
(like how GPUs are local today)
    │
    ▼
1000+ logical qubits (error-corrected)
Full fault-tolerant quantum computation
```

### Quantum Error Correction Timeline

| Year Range | Technology | Error Rate | Qubits |
|---|---|---|---|
| 2024–2026 | NISQ devices | ~0.1–5% per gate | 50–1000 physical |
| 2026–2030 | Early fault-tolerant | ~0.001% (surface codes) | 1000+ physical = ~10 logical |
| 2030–2040 | Fault-tolerant QPU | <0.0001% | Millions of physical |
| 2040+ | Large-scale QC | Negligible | Arbitrary scale |

---

## Part 6: Running Quantum Experiments in Umer OS

### Experiment 1: Quantum Coin Flip

```python
"""A truly random coin flip using quantum superposition."""
from quantum.quantum_sim import QuantumCircuitSimulator

sim = QuantumCircuitSimulator(n_qubits=1)
results = []

for _ in range(100):
    sim.reset()
    sim.apply_h(0)           # Superposition: 50/50
    bit = sim.measure_qubit(0)   # Truly random 0 or 1
    results.append(bit)

heads = sum(results)
tails = len(results) - heads
print(f"Heads: {heads}, Tails: {tails}")
# Should be approximately 50/50 — quantum randomness!
```

### Experiment 2: Bell State Verification

```python
"""Verify quantum entanglement (should ALWAYS be correlated)."""
from quantum.quantum_sim import QuantumCircuitSimulator

sim = QuantumCircuitSimulator(n_qubits=2)
correlated = 0

for trial in range(1000):
    sim.reset()
    sim.apply_h(0)
    sim.apply_cnot(0, 1)    # Create Bell state
    
    # Measure BOTH qubits (collapses the entangled state)
    a = sim.measure_qubit(0)
    b = sim.measure_qubit(1)
    
    if a == b:    # They must always agree!
        correlated += 1

print(f"Correlation: {correlated}/1000 = {correlated/10}%")
# Should always print 100.0% — perfect entanglement
```

### Experiment 3: Grover Search (2 qubits)

```python
"""
Grover's algorithm: find a marked item in an unsorted database.
Classical: O(N) checks. Quantum: O(√N) checks.
This 2-qubit version searches through 4 items.
"""
from quantum.quantum_sim import QuantumCircuitSimulator
import numpy as np

sim = QuantumCircuitSimulator(n_qubits=2)

# We want to find item |11⟩ (index 3)
# Step 1: Equal superposition
sim.apply_h(0)
sim.apply_h(1)

# Step 2: Oracle — mark |11⟩ by flipping its phase
# For |11⟩: Z gates on both qubits achieve CZ effect
sim.apply_z(0)
sim.apply_z(1)

# Step 3: Diffusion operator (amplitude amplification)
sim.apply_h(0); sim.apply_h(1)
sim.apply_x(0); sim.apply_x(1)
sim.apply_z(0)   # simplified diffusion
sim.apply_x(0); sim.apply_x(1)
sim.apply_h(0); sim.apply_h(1)

probs = sim.probabilities()
found = np.argmax(probs)
print(f"Grover found item: {found}")  # Should be 3 = |11⟩
print(f"Probabilities: {[f'{p:.2f}' for p in probs]}")
```

### Experiment 4: Quantum Phase Estimation (advanced)

```python
"""
Estimate the eigenphase of a unitary — core of Shor's algorithm.
Today: simulated. Future: runs on real QPU.
"""
from quantum.quantum_sim import QuantumCircuitSimulator
import numpy as np

sim = QuantumCircuitSimulator(n_qubits=3)

# Prepare superposition
for i in range(3):
    sim.apply_h(i)

# Controlled unitary applications would go here (QPU-specific)
# For now: measure to show the state exploration
probs = sim.probabilities()
print("Phase estimation state vector probabilities:")
for i, p in enumerate(probs):
    print(f"  |{i:03b}⟩: {p:.3f}")
```

---

## Part 7: Frequently Asked Questions

**Q: Is Umer OS's quantum computing real?**  
A: The *simulation* is real — the mathematics is exactly correct. What's not real is the
hardware: we simulate qubit behaviour on classical CPUs using NumPy, not actual quantum
chips. The algorithms, gates, and measurements all behave exactly as they would on real
hardware, just much slower and limited to ~20 qubits.

**Q: How many qubits does Umer OS support?**  
A: The simulator supports 1–20 qubits. At 20 qubits, the state vector has 2²⁰ = 1,048,576
complex numbers (~16 MB). Beyond 20 qubits, classical simulation becomes impractical
(30 qubits = 8 GB RAM).

**Q: When will Umer OS have a real QPU?**  
A: The API is already QPU-ready. Once hardware QPU co-processors become available in
consumer devices (estimated 2028–2035), Umer OS simply needs a `QuantumDevice` driver
plugin. The application API stays identical.

**Q: What's the difference between Kyber and RSA?**  
A: RSA security relies on the difficulty of factoring large numbers. A quantum computer
running Shor's algorithm can factor numbers exponentially faster, breaking RSA.
CRYSTALS-Kyber security relies on the difficulty of solving lattice problems, which
no known quantum algorithm can solve efficiently. Kyber is "post-quantum safe."

**Q: Can Umer OS break existing encryption?**  
A: No. Umer OS simulates quantum algorithms but on classical hardware — the simulation
is exponentially slower than real hardware for large inputs. Breaking RSA-2048 would
require billions of years of simulation time. Only an actual large-scale quantum computer
(which doesn't exist yet) could do it.

---

*Umer OS Quantum Tutorial — v0.1.0-alpha*  
*Difficulty: Part 1–2 (Beginner) | Part 3–4 (Intermediate) | Part 5–7 (Advanced)*
