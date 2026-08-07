# Umer OS — Quantum Computing Tutorial

**Audience:** Everyone — from complete beginners to quantum engineers

---

## Part 1: Quantum Computing for Complete Beginners

### What Is a Quantum Computer?

A normal computer stores information as **bits** — each is either 0 or 1 (like a light switch).

A quantum computer stores information as **qubits**. A qubit can be:
- **0** (like a normal bit)
- **1** (like a normal bit)
- **Both 0 and 1 at the same time!** (called **superposition**)

```
Normal bit:   [ 0 ]  or  [ 1 ]

Qubit:        [ 0 ]  or  [ 1 ]  or  [ 0 AND 1 simultaneously ]
                                     (superposition)
```

### Why "Both at Once" Matters

Looking for keys in a house with 8 rooms:
- **Normal computer:** checks Room 1, then 2, then 3... (one at a time)
- **Quantum computer:** checks all 8 rooms simultaneously!

### Measurement Collapses Superposition

The moment you *measure* a qubit, superposition collapses to either 0 or 1.

```
Before measurement: qubit = [0 and 1 together, 50/50 probability]
After measurement:  qubit = [0]  OR  qubit = [1]  ← collapsed
```

### Entanglement

**Entanglement** links two qubits so measuring one instantly determines the other:

```
Entangled pair:
  Measure A → gets 0     Qubit B instantly becomes 0
  Measure A → gets 1     Qubit B instantly becomes 1
  They always agree!
```

---

## Part 2: Quantum States in Umer OS

### The State Vector

```python
from quantum.quantum_sim import QuantumCircuitSimulator

sim = QuantumCircuitSimulator(n_qubits=2)
print(sim.state)
# [1+0j, 0+0j, 0+0j, 0+0j]   ← |00⟩ = 100% probability
```

### The Hadamard Gate: Creating Superposition

```python
sim.reset()
sim.apply_h(0)
print(sim.probabilities())
# [0.5, 0.0, 0.5, 0.0]  ← qubit 0 in superposition

result = sim.measure()   # randomly 0 (|00⟩) or 2 (|10⟩)
```

**Mathematics:**

```
|ψ⟩ = (1/√2)|0⟩ + (1/√2)|1⟩
Probability of 0 = |1/√2|² = 0.5
Probability of 1 = |1/√2|² = 0.5
```

### The CNOT Gate: Creating Entanglement

```python
sim.reset()
sim.apply_h(0)
sim.apply_cnot(0, 1)
print(sim.probabilities())
# [0.5, 0.0, 0.0, 0.5]   ← ONLY |00⟩ and |11⟩ possible — entangled!
```

---

## Part 3: Umer OS Quantum Features

### Feature 1: Quantum-Inspired Scheduling ✅ TODAY

```python
from quantum.quantum_sim import SuperpositionSchedulerAdapter, QuantumCircuitSimulator
from kernel.scheduler import Task

adapter = SuperpositionSchedulerAdapter(sim=QuantumCircuitSimulator(n_qubits=1))
tasks = [
    Task(pid=1, name="video_encode", priority=0.9),
    Task(pid=2, name="background_sync", priority=0.2),
]
scores = adapter.evaluate_task_paths(tasks)
# {1: 0.72, 2: 0.19}  ← quantum-refined probability scores
```

**Scoring algorithm:**
```
For each task:
  1. Reset simulator → |0⟩
  2. Apply Hadamard: |0⟩ → (|0⟩ + |1⟩)/√2
  3. Measure ⟨Z⟩ expectation → [-1, +1]
  4. Normalise: quantum_prob = (ev + 1) / 2
  5. Blend: score = 0.5×priority + 0.5×quantum_prob
```

### Feature 2: Entanglement-Inspired IPC ✅ TODAY

```python
from quantum.quantum_sim import EntanglementIPCAdapter

adapter = EntanglementIPCAdapter()
adapter.subscribe(pid=1, channel="events")
pub_bit, msg = adapter.publish("events", {"event": "cpu_high"})
# msg["_quantum"] = {"pub_bit": 0, "sub_bit": 0, ...}  ← always correlated
```

### Feature 3: Post-Quantum Cryptography ✅ TODAY

```python
from quantum.crypto_pqc import PostQuantumCrypto

pqc = PostQuantumCrypto()
print(pqc.backend)   # "liboqs" (Kyber768) or "fallback" (Ed25519)

pk, sk = pqc.generate_keypair()
ct = pqc.encrypt(b"secret", pk)
assert pqc.decrypt(ct, sk) == b"secret"

sig = pqc.sign(b"message", sk)
assert pqc.verify(b"message", sig, pk) == True
assert pqc.verify(b"tampered", sig, pk) == False
```

### Feature 4: Quantum API Gateway ✅ TODAY

```python
from quantum.quantum_api import QuantumAPIGateway

gw = QuantumAPIGateway()
result = gw.run(
    [{"gate":"H","qubit":0}, {"gate":"CNOT","control":0,"target":1}],
    backend="simulator", shots=1024
)
print(result["counts"])   # {"0": ~512, "3": ~512}  ← Bell state
```

> **Engineering note:** The gateway dynamically sizes its internal simulator to
> match the circuit's actual qubit count (`_required_qubits()`). This prevents a
> critical bug where a fixed-size simulator lets entangled-state probability leak
> into unused qubits.

### Feature 5: Error Mitigation ✅ TODAY / 🔬 EXPERIMENTAL

```python
from quantum.error_mitigation import ZeroNoiseExtrapolator

zne = ZeroNoiseExtrapolator(scale_factors=[1.0, 2.0, 3.0])

def expectation_at_scale(noise_scale):
    return 1.0 - 0.05 * noise_scale   # simplified noise model

zero_noise_value = zne.extrapolate(expectation_at_scale)
print(f"Extrapolated: {zero_noise_value:.4f}")   # ≈ 1.0
```

---

## Part 4: The Mathematics

### State Vector Notation

```
n=1 (2 states):   [α₀, α₁]              |0⟩  |1⟩
n=2 (4 states):   [α₀₀, α₀₁, α₁₀, α₁₁]  |00⟩ |01⟩ |10⟩ |11⟩

Probability of |i⟩ = |αᵢ|²
Normalisation: Σ|αᵢ|² = 1.0
```

### Gate Matrices

```
Hadamard (H):        Pauli-X:        Pauli-Z:
┌            ┐        ┌     ┐         ┌      ┐
│ 1/√2  1/√2│        │ 0 1 │         │ 1  0 │
│ 1/√2 -1/√2│        │ 1 0 │         │ 0 -1 │
└            ┘        └     ┘         └      ┘
```

---

## Part 5: Running Experiments

### Experiment 1: Quantum Coin Flip

```python
from quantum.quantum_sim import QuantumCircuitSimulator

sim = QuantumCircuitSimulator(n_qubits=1)
results = []
for _ in range(100):
    sim.reset(); sim.apply_h(0)
    results.append(sim.measure_qubit(0))

heads = sum(results)
print(f"Heads: {heads}, Tails: {100-heads}")   # ≈ 50/50
```

### Experiment 2: Bell State Verification

```python
sim = QuantumCircuitSimulator(n_qubits=2)
correlated = 0
for _ in range(1000):
    sim.reset(); sim.apply_h(0); sim.apply_cnot(0, 1)
    a = sim.measure_qubit(0); b = sim.measure_qubit(1)
    if a == b: correlated += 1
print(f"Correlation: {correlated/10}%")   # Always 100.0%
```

---

## Part 6: FAQ

**Q: Is Umer OS's quantum computing real?**
A: The *mathematics* is exactly correct. What's simulated is the hardware — real
qubit behaviour computed via NumPy on a classical CPU, limited to ~20 qubits.

**Q: How many qubits does Umer OS support?**
A: 1–20 qubits. At 20 qubits the state vector is 2²⁰ ≈ 1 million complex numbers.

**Q: When will there be a real QPU?**
A: The API is already QPU-ready (`QuantumDevice` abstract interface,
`QuantumAPIGateway.register_backend()`). Once hardware exists, only a driver
plugin is needed — application code stays identical.

**Q: What's the difference between Kyber and RSA?**
A: RSA relies on factoring difficulty, breakable by Shor's algorithm on a real
quantum computer. Kyber relies on lattice problems, which have no known efficient
quantum attack — it's "post-quantum safe."

---

*Umer OS Quantum Tutorial — v0.1.0-alpha*
