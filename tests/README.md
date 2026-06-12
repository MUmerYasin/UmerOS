# Umer OS Skeleton

Prototype microkernel-like skeleton in user-space with:
- asyncio scheduler (quantum-inspired heuristic)
- IPC broker (message passing)
- HAL C stub + ctypes binding
- Simple quantum simulator backend

Build:
    make build

Run demo:
    python3 examples/run_demo.py

Run tests:
    pip install pytest pytest-asyncio
    pytest -q