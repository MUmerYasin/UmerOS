# tests/test_grub_cli.py
" Unit tests for the GRUB configuration parser."

import sys
import pathlib

# Ensure the project root is on the import path
project_root = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from backup.grub_cli import parse_grub_cfg

def test_parse_grub_cfg():
    root = str(project_root)
    result = parse_grub_cfg(root)
    expected = {
        default_entry: None,
        timeout: 5,
        entries: [
            {
                name: Ubuntu,
                linux: /boot/vmlinuz-5.15.0-50-generic,
                initrd: /boot/initrd.img-5.15.0-50-generic,
                options: root=UUID=xxxx ro quiet splash,
            },
            {
                name: Advanced options for Ubuntu,
                linux: /boot/vmlinuz-5.15.0-50-generic,
                initrd: /boot/initrd.img-5.15.0-50-generic,
                options: root=UUID=xxxx ro quiet splash,
            },
        ],
    }
    assert result[timeout] == expected[timeout]
    assert result[entries] == expected[entries]
    assert default_entry in result
