# tests/test_grub_cli.py
" Unit tests for the GRUB configuration parser."

import shutil
import sys
import pathlib

# Ensure the project root is on the import path
project_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from backup.grub_cli import parse_grub_cfg

# The fixture lives beside this test file; ``parse_grub_cfg`` resolves
# ``<root>/boot/grub.cfg``, so the fixture is staged into a temporary
# project root instead of relying on a ``boot/grub.cfg`` in the repo
# (there is none, and creating one would look like a real GRUB config).
FIXTURE = pathlib.Path(__file__).resolve().parent / "grub.cfg"


def test_parse_grub_cfg(tmp_path):
    (tmp_path / "boot").mkdir()
    shutil.copyfile(FIXTURE, tmp_path / "boot" / "grub.cfg")
    root = str(tmp_path)
    result = parse_grub_cfg(root)
    expected = {
        "default_entry": None,
        "timeout": 5,
        "entries": [
            {
                "name": "Ubuntu",
                "linux": "/boot/vmlinuz-5.15.0-50-generic",
                "initrd": "/boot/initrd.img-5.15.0-50-generic",
                "options": "root=UUID=xxxx ro quiet splash",
            },
            {
                "name": "Advanced options for Ubuntu",
                "linux": "/boot/vmlinuz-5.15.0-50-generic",
                "initrd": "/boot/initrd.img-5.15.0-50-generic",
                "options": "root=UUID=xxxx ro quiet splash",
            },
        ],
    }
    assert result["timeout"] == expected["timeout"]
    assert result["entries"] == expected["entries"]
    assert "default_entry" in result
