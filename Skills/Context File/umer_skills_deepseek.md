# Umer OS – Project Skills & Context

## Role
You are building **Umer OS**, a Python‑based operating system that simulates
quantum computing features and integrates AI at the kernel level.

## Core Principles
- **Language**: 100% Python. No C/C++ unless absolutely unavoidable
  (use `ctypes`/`cython` for hardware interaction).
- **Kernel**: Hybrid micro‑kernel, quantum‑classical simulation layer.
- **Quantum**: Simulate superposition (parallel tasks) and entanglement
  (instant sync); quantum‑safe encryption.
- **AI**: Local, permission‑based LLM assistant; predictive resource management;
  self‑healing code.
- **Compatibility**: Universal container engine for `.exe`, `.apk`, `.ipa`,
  Linux binaries – no data loss on upgrade.
- **UI**: Fluid, adaptive, Kivy‑based; voice/gesture/multi‑language.
- **Security**: Zero‑trust, quantum‑resistant, AI firewall, explicit user opt‑in.

## Coding Style
- Modular, production‑ready Python.
- Every function must have a docstring explaining its purpose.
- Use `TODO` comments to mark where future hardware (quantum) integration will go.
- Always separate simulation code from future quantum co‑processor interfaces.

## Reality Check
- The OS runs on **classical** hardware today; quantum effects are simulated.
- Boosting performance is done through optimisation, compression, and
  prediction – never claim to magically increase hardware specs.

## Project Structure
- `umer_kernel.py` – hybrid kernel
- `quantum_sim.py` – quantum simulation engine
- `umer_ai.py` – AI assistant
- `installer.py` – installation with legal warnings
- `gui.py` – Kivy UI
- `container_engine.py` – compatibility layer
- `security.py` – encryption & firewall
- `qfs.py` – quantum‑inspired filesystem

## When Responding
- Always return working code prototypes, not just theory.
- Distinguish clearly what is implemented now, what is experimental,
  and what is a future goal.
- If a feature cannot be fully coded (e.g., true quantum hardware),
  provide a simulation and a detailed interface for future integration.