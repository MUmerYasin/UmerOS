def _read_file(path: str) -> str:
    """Read a file from the real /proc if it exists, otherwise return empty string."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def parse_key_value(raw: str) -> dict:
    """Parse simple ``Key: Value`` lines into a dictionary.
    Empty lines are ignored. Whitespace around keys and values is stripped.
    """
    result = {}
    for line in raw.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        result[key.strip()] = value.strip()
    return result

def parse_key_value_multi(raw: str) -> list[dict]:
    """Parse files that contain multiple sections separated by blank lines
    (e.g., /proc/cpuinfo). Returns a list of dictionaries, one per section.
    """
    sections = []
    current = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current:
                sections.append(current)
                current = {}
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            current[key.strip()] = value.strip()
    if current:
        sections.append(current)
    return sections
