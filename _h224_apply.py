"""H224 applier -- quantum/backend.py: redact secrets, replace print with logging."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("quantum/backend.py")
src = TARGET.read_text(encoding="utf-8")
orig = src


def sub(old: str, new: str, label: str) -> None:
    global src
    n = src.count(old)
    if n != 1:
        print(f"ABORT [{label}]: expected 1 occurrence, found {n}")
        sys.exit(1)
    src = src.replace(old, new)
    print(f"OK [{label}]")


# --- 1. import logging -------------------------------------------------------
sub(
    "from __future__ import annotations\n\nimport math\nimport time\n",
    "from __future__ import annotations\n\nimport logging\nimport math\nimport time\n",
    "import logging",
)

# --- 2. module logger --------------------------------------------------------
sub(
    "from .noise import NoiseModel\n\n\n# ---------------------------------------------------------------------------\n"
    "# Backend status and options\n",
    "from .noise import NoiseModel\n\n\n"
    'log = logging.getLogger("UmerOS.Quantum.Backend")\n\n\n'
    "# ---------------------------------------------------------------------------\n"
    "# Backend status and options\n",
    "module logger",
)

# --- 3. docstring trailer (section 1 baseline) -------------------------------
sub(
    "Backend objects are compatible with noise models and can be composed.\n\"\"\"\n",
    "Backend objects are compatible with noise models and can be composed.\n\n"
    "Author:  Umer OS Project\n"
    "License: GPL-3.0 (GNU General Public License v3)\n"
    "\"\"\"\n",
    "docstring trailer",
)

# --- 4. redaction helper + IBMBackend init/repr ------------------------------
OLD_IBM = '''class IBMBackend(Backend):
    """IBM Quantum backend via qiskit-ibm-runtime.

    Requires: pip install qiskit-ibm-runtime
    """

    def __init__(self, token: Optional[str] = None, instance: Optional[str] = None,
                 backend_name: str = "ibm_brisbane", **kwargs):
        self._token = token
        self._instance = instance
        self._backend_name = backend_name
        self._service = None
        self._backend = None

        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            self._service = QiskitRuntimeService(
                token=token, instance=instance
            )
            self._backend = self._service.backend(backend_name)
        except ImportError:
            pass
        except Exception as e:
            print(f"IBM Backend init warning: {e}")
'''

NEW_IBM = '''_SECRET_PLACEHOLDER = "***"

# Secrets shorter than this are not scrubbed: replacing a one- or two-character
# token would shred the surrounding diagnostic text for no confidentiality gain.
_MIN_SECRET_LEN = 4


def _redact_secrets(text: Any, *secrets: Optional[str]) -> str:
    """Return ``text`` with every supplied secret replaced by ``***``.

    Provider SDK exceptions cannot be trusted about what they echo: an
    ``HTTPError`` raised deep inside ``requests`` carries the full request URL
    (query string included), and some SDKs format the auth token straight into
    the message.  Every diagnostic string that reaches a log record therefore
    passes through this scrubber first.

    Args:
        text: The diagnostic text to sanitize.  ``None`` becomes ``""`` and
            non-strings are coerced with ``str()`` -- this function never
            raises.
        *secrets: Secret values to remove.  ``None`` and empty strings are
            ignored, and values shorter than ``_MIN_SECRET_LEN`` are skipped.

    Returns:
        The scrubbed text.
    """
    redacted = "" if text is None else str(text)
    for secret in secrets:
        if not isinstance(secret, str) or len(secret) < _MIN_SECRET_LEN:
            continue
        redacted = redacted.replace(secret, _SECRET_PLACEHOLDER)
    return redacted


class IBMBackend(Backend):
    """IBM Quantum backend via qiskit-ibm-runtime.

    Requires: pip install qiskit-ibm-runtime

    Initialization is best-effort.  When the optional dependency is missing the
    backend stays in offline mode (``status()`` -> ``OFFLINE``); when the
    service rejects the credentials the failure is logged at WARNING through
    ``logging`` -- never printed to stdout -- with the token scrubbed out of the
    exception text by ``_redact_secrets``.  ``__repr__`` follows the
    ``providers/base.py`` redaction pattern (``token='***'``).
    """

    def __init__(self, token: Optional[str] = None, instance: Optional[str] = None,
                 backend_name: str = "ibm_brisbane", **kwargs):
        self._token = token
        self._instance = instance
        self._backend_name = backend_name
        self._service = None
        self._backend = None

        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            self._service = QiskitRuntimeService(
                token=token, instance=instance
            )
            self._backend = self._service.backend(backend_name)
        except ImportError:
            log.debug(
                "qiskit-ibm-runtime not installed; IBMBackend(%s) runs offline.",
                backend_name,
            )
        except Exception as exc:
            log.warning(
                "IBM backend %r initialization failed (%s): %s",
                backend_name,
                type(exc).__name__,
                _redact_secrets(exc, token),
            )

    def __repr__(self) -> str:
        return (
            f"IBMBackend(name={self._backend_name!r}, "
            f"token={'***' if self._token else None}, "
            f"online={self._backend is not None})"
        )
'''

sub(OLD_IBM, NEW_IBM, "IBMBackend redaction")

if src == orig:
    print("ABORT: nothing changed")
    sys.exit(1)

TARGET.write_text(src, encoding="utf-8")

import py_compile

py_compile.compile(str(TARGET), doraise=True)
print("compiles clean")

# post-conditions
assert "print(" not in src, "a print( survived"
assert "logging.getLogger" in src
assert src.count("_redact_secrets") >= 2
print("post-conditions OK")
