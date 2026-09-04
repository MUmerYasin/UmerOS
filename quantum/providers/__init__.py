# UmerOS /quantum/providers — Quantum hardware provider abstraction
# =================================================================
# GPL-3.0 — see LICENSE and README for details.
"""
UmerOS /quantum/providers — Quantum hardware provider abstraction.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__: list[str] = []


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import optional helpers and add the names to ``__all__``."""
    global __all__
    try:
        mod = __import__(f"{__name__}.{module_name}", fromlist=names)
    except ImportError:
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


for _mod, _names in (
    ("base", (
        "BackendStatus", "BackendTarget", "BackendProperties",
        "JobResult", "BackendJob", "BackendSession",
        "BackendProvider", "BackendTargetCoupling",
        "GateSet", "JobQueueMode",
    )),
    ("ibm_provider", (
        "IBMQuantumProvider", "IBMQuantumJob", "IBMQuantumBackend",
        "IBMQuantumError", "IBMAuthenticationError",
        "IBMRatelimitError", "IBMBackendNotFoundError", "IBMJobError",
    )),
    ("ionq_provider", (
        "IonQProvider", "IonQJob", "IonQError",
        "IonQAuthenticationError", "IonQAPIError", "IonQJobError",
    )),
    ("braket_provider", (
        "BraketProvider", "BraketJob", "BraketBackend",
        "BraketError", "BraketAPIError", "BraketAuthError",
        "BraketDeviceError", "BraketJobError", "BraketResultError",
    )),
    ("rigetti_provider", (
        "RigettiProvider", "RigettiJob",
    )),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify every name in ``__all__`` is importable from this package."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [name for name in __all__ if not hasattr(pkg, name)]
    if missing:
        print(
            f"quantum.providers selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
