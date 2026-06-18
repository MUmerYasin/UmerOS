import platform
import shutil
from pathlib import Path


def boot():
    root = Path.cwd()
    env = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "root": str(root),
        "has_numpy": False,
        "has_kivy": False,
        "has_qiskit": False,
    }

    try:
        import numpy  # noqa: F401
        env["has_numpy"] = True
    except Exception:
        pass

    try:
        import kivy  # noqa: F401
        env["has_kivy"] = True
    except Exception:
        pass

    try:
        import qiskit  # noqa: F401
        env["has_qiskit"] = True
    except Exception:
        pass

    if shutil.which("python") is None and shutil.which("python3") is None:
        raise RuntimeError("No Python interpreter found.")

    print("Umer OS bootloader: system checks passed.")
    print(f"Platform: {env['platform']}")
    print(f"Python: {env['python']}")
    return env