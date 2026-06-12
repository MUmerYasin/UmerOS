---
short_context: |
  I want to write a Python‑based operating system like Linux that includes
  all features of quantum computing (simulated superposition, entanglement,
  quantum‑safe security), AI integration, backward compatibility with all
  platforms, and a modern UI. The system is called Umer OS.
---

# Umer OS – Full Architecture & Code Generation Prompt

You are a Senior Principal Systems Architect and Lead Quantum Software Engineer.
Your task is to design and generate the foundational Python code for **Umer OS**,
a revolutionary universal operating system intended to eventually replace
Windows, Linux, macOS, Android, iOS, and HarmonyOS.

## Language & Kernel
- **100% Python** (use `ctypes`, `numba`, or `cython` only when strictly necessary).
- Design a **hybrid micro‑kernel** named `Umer Hybrid Quantum Kernel`.
- It must include a **quantum‑classical simulation layer** that uses
  quantum‑inspired algorithms to optimise classical hardware.

## Quantum Computing Integration
- **Simulate** superposition (for parallel task scheduling) and entanglement
  (for instant data synchronisation) entirely in software.
- Include a **quantum‑safe cryptography** module (CRYSTALS‑Kyber, Dilithium).
- Design a **future quantum co‑processor interface** (PCI‑e) and API.

## AI / Super‑Intelligence
- Build a **local, permission‑based AI layer** that:
  - Predictively manages CPU/GPU/RAM before an application starts.
  - Runs a lightweight LLM for a natural‑language system assistant.
  - Implements **self‑healing code** – detects bugs and rewrites its own logic.
- All training must be opt‑in, and data stays on‑device by default.

## Backward Compatibility
- Create a **Universal Container Engine** (Wine/Proton/Docker hybrid) that runs:
  - `.exe` (Windows)
  - `.apk` (Android)
  - `.ipa` (iOS, simulated)
  - Legacy Linux binaries
- Existing user data, settings, and applications must migrate without reset.

## UI / UX
- “Fluidic” interface using **Kivy** (or custom hardware‑accelerated wrapper).
- Adaptive to any screen size, supports voice, gesture, and multiple languages.
- More intuitive than macOS, more customisable than Android, easier than Linux.

## Security
- Zero‑trust architecture, AI‑driven behavioural firewall, sandboxing.
- Quantum‑resistant encryption, secure boot, explicit user opt‑in with a
  legal liability waiver before installation.

## Performance
- Achieve speed‑ups through **algorithmic optimisation**, not magical hardware
  boosting: super‑compression (quantum‑inspired, lossless), intelligent caching,
  predictive prefetching, and GPU acceleration.

## Developer Ecosystem
- Native Python SDK, package manager (`umer‑pkg`), AI‑assisted IDE.
- Support Python, C/C++, Flutter, and all major AI frameworks.

## Reality & Engineering Constraints
Throughout your answer you **must** distinguish clearly between:
1. **Today** – what can be implemented now (simulation, AI, containers).
2. **Experimental** – near‑term quantum simulation with error models.
3. **Future theoretical** – true fault‑tolerant quantum computing, zero‑loss goal.

Be as technically detailed as Linus Torvalds, Dennis Ritchie, or a DARPA engineer.
Deliver a realistic, modular, production‑structured codebase.

## Output Structure
Generate a single Markdown document with the following sections **in order**.
Provide real, runnable Python code wherever possible; use pseudo‑code only when
hardware constraints truly demand it.

1. Executive Summary  
2. Reality Check & Technical Constraints  
3. High‑Level OS Architecture (ASCII diagrams)  
4. Kernel Architecture – `umer_kernel.py`  
5. Quantum Layer – `quantum_sim.py`  
6. AI System – `umer_ai.py`  
7. Security Architecture – `security.py`  
8. Filesystem – `qfs.py` (quantum‑inspired super‑compression)  
9. Driver Model  
10. Compatibility Layer – `container_engine.py`  
11. UI/UX Engine – `gui.py`  
12. Networking Stack  
13. Cloud Integration  
14. Mobile Device Strategy  
15. iPhone/Android Installation Constraints (legal waiver, rollback)  
16. Performance Optimisation Plan  
17. Developer Ecosystem  
18. Boot Process – `bootloader.py` (shows warning, opt‑in)  
19. Package Management – `umer-pkg`  
20. Backup & Recovery System  
21. AI Governance & Privacy Model  
22. Quantum Error Mitigation Roadmap  
23. Future Roadmap (5, 10, 20 years)  
24. Risks & Engineering Challenges  
25. Full Folder Structure  
26. Initial Source Code Overview  
27. Kernel Prototype (working Python code)  
28. Bootloader Prototype  
29. Quantum Simulation Module  
30. AI Assistant Module  
31. Compatibility Layer Prototype  
32. Installer Prototype – `installer.py` (TUI/GUI with legal warning)  
33. GUI Prototype  
34. Security Subsystem  
35. Update System  
36. Example Device Drivers  
37. Filesystem Prototype  
38. API Documentation  
39. SDK Documentation  
40. Build Instructions  
41. Deployment Instructions  
42. Future Quantum Hardware Integration Plan  

## Specific Code Deliverables
Include these fully‑functional Python files inside the relevant sections:
- `bootloader.py`
- `umer_kernel.py`
- `quantum_sim.py`
- `umer_ai.py`
- `installer.py`
- `gui.py`
- `container_engine.py`
- `security.py`
- `qfs.py`

Write all code with extensive comments, clean architecture, and error handling.
The final response must be a complete, self‑contained blueprint for Umer OS.