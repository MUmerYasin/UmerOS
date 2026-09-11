# backup/grub_cli.py
"""GRUB configuration parser for UmerOS.

Provides a function :func:`parse_grub_cfg` that reads the ``grub.cfg`` file
located under ``<PROJECT_ROOT>/boot`` and returns a JSON‑serialisable
dictionary describing global settings and menu entries.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any


def _extract_default_and_timeout(lines: List[str]) -> Dict[str, Any]:
    """Extract ``set default=`` and ``set timeout=`` directives.

    Returns a dict with keys ``default_entry`` (str or ``None``) and ``timeout``
    (int or ``None``). Handles optional quotes around the value.
    """
    default_entry = None
    timeout = None
    default_pat = re.compile(r"set\s+default\s*=\s*\"?([^\"\s]+)\"?")
    timeout_pat = re.compile(r"set\s+timeout\s*=\s*([0-9]+)")
    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            continue
        m = default_pat.search(line)
        if m:
            default_entry = m.group(1)
        m = timeout_pat.search(line)
        if m:
            timeout = int(m.group(1))
    return {"default_entry": default_entry, "timeout": timeout}


def _parse_menuentries(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse ``menuentry`` blocks from the grub.cfg content.

    Each block yields a dict with ``name``, ``linux``, ``initrd`` and ``options``
    (the remainder of the ``linux`` line after the kernel path). The parser
    tolerates comments and multiline continuation using backslashes.
    """
    entries = []
    menu_start_pat = re.compile(r"menuentry\s+['\"]([^'\"]+)['\"]\s*{", re.IGNORECASE)
    linux_pat = re.compile(r"\s*linux\s+([^\s]+)\s*(.*)")
    initrd_pat = re.compile(r"\s*initrd\s+([^\s]+)")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith('#'):
            i += 1
            continue
        m = menu_start_pat.search(line)
        if m:
            entry = {"name": m.group(1), "linux": None, "initrd": None, "options": ""}
            brace_depth = 1
            i += 1
            while i < len(lines) and brace_depth > 0:
                cur = lines[i].strip()
                if cur.startswith('#'):
                    i += 1
                    continue
                brace_depth += cur.count('{') - cur.count('}')
                lm = linux_pat.match(cur)
                if lm:
                    entry["linux"] = lm.group(1)
                    entry["options"] = lm.group(2).strip()
                im = initrd_pat.match(cur)
                if im:
                    entry["initrd"] = im.group(1)
                i += 1
            entries.append(entry)
        else:
            i += 1
    return entries


def parse_grub_cfg(root_path: str) -> Dict[str, Any]:
    """Parse the GRUB configuration file for the given project root.

    Parameters
    ----------
    root_path: str
        Absolute path to the UmerOS project directory.

    Returns
    -------
    dict
        ``{"default_entry": ..., "timeout": ..., "entries": [...]}``
    """
    grub_path = Path(root_path) / "boot" / "grub.cfg"
    if not grub_path.is_file():
        raise FileNotFoundError(f"GRUB config not found at {grub_path}")
    with grub_path.open('r', encoding='utf-8') as f:
        raw_lines = f.readlines()
    lines = [ln.rstrip('\n') for ln in raw_lines]
    globals_ = _extract_default_and_timeout(lines)
    entries = _parse_menuentries(lines)
    return {
        "default_entry": globals_["default_entry"],
        "timeout": globals_["timeout"],
        "entries": entries,
    }


if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="Parse grub.cfg and output JSON")
    parser.add_argument("--root", required=True, help="Project root directory")
    args = parser.parse_args()
    try:
        result = parse_grub_cfg(args.root)
        json.dump(result, sys.stdout, indent=2)
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
