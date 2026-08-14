def _read_file(path: str) -> str:
    """Read a file from the real /proc if it exists, otherwise return empty string."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
