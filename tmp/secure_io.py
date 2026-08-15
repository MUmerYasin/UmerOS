"""
UmerOS /tmp — Cryptographically Secure Temporary File & Directory Engine
========================================================================

Implements race-free, cryptographically unguessable temporary file and directory
creation matching POSIX mktemp, mkstemp, and mkdtemp standards.

Security Principles:
--------------------
1. Exclusive Creation (O_CREAT | O_EXCL):
   Prevents symlink injection, TOCTOU (Time-of-Check to Time-of-Use) attacks,
   and file clobbering in shared world-writable /tmp.

2. Strict Least-Privilege Permissions:
   - Temporary files: Mode 0600 (owner read/write only).
   - Temporary directories: Mode 0700 (owner read/write/traverse only).

3. Cryptographically Secure Entropy:
   Generates unguessable pseudorandom tokens using `secrets` / `os.urandom`.

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import stat
import string
from pathlib import Path
from typing import Any, Callable, Generator, Optional, Tuple

from fhs import DEFAULT_TMP_ROOT

log = logging.getLogger("UmerOS.Tmp.SecureIO")

ALPHANUMERIC = string.ascii_letters + string.digits


class SecureIO:
    """
    Secure file and directory creation engine for /tmp.
    """

    @classmethod
    def create_temp_file(
        cls,
        prefix: str = "tmp.",
        suffix: str = "",
        dir_path: Optional[Path | str] = None,
        mode: int = 0o600,
        content: Optional[bytes | str] = None,
    ) -> Path:
        """
        Atomically and securely creates a temporary file with mode 0600.
        """
        target_dir = Path(dir_path or DEFAULT_TMP_ROOT).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        max_attempts = 100
        for _ in range(max_attempts):
            random_token = "".join(secrets.choice(ALPHANUMERIC) for _ in range(10))
            filename = f"{prefix}{random_token}{suffix}"
            candidate_path = target_dir / filename

            flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY

            try:
                fd = os.open(str(candidate_path), flags, mode)
                try:
                    if os.name != "nt":
                        os.chmod(str(candidate_path), mode)
                    if content is not None:
                        data_bytes = content.encode("utf-8") if isinstance(content, str) else content
                        os.write(fd, data_bytes)
                finally:
                    os.close(fd)
                return candidate_path
            except FileExistsError:
                continue

        raise IOError("Failed to create secure temporary file after 100 attempts.")

    @classmethod
    def create_temp_dir(
        cls,
        prefix: str = "tmp.",
        suffix: str = "",
        dir_path: Optional[Path | str] = None,
        mode: int = 0o700,
    ) -> Path:
        """
        Atomically and securely creates a temporary directory with mode 0700.
        """
        target_dir = Path(dir_path or DEFAULT_TMP_ROOT).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        max_attempts = 100
        for _ in range(max_attempts):
            random_token = "".join(secrets.choice(ALPHANUMERIC) for _ in range(10))
            dirname = f"{prefix}{random_token}{suffix}"
            candidate_path = target_dir / dirname

            try:
                candidate_path.mkdir(mode=mode, parents=False, exist_ok=False)
                if os.name != "nt":
                    os.chmod(candidate_path, mode)
                return candidate_path
            except FileExistsError:
                continue

        raise IOError("Failed to create secure temporary directory after 100 attempts.")

    @classmethod
    def mktemp(
        cls,
        template: str = "tmp.XXXXXXXXXX",
        directory: bool = False,
        tmp_dir: Optional[Path | str] = None,
        dry_run: bool = False,
    ) -> Path:
        """
        Emulates POSIX mktemp utility.
        Replaces trailing 'X' characters in the template with random characters.
        """
        target_dir = Path(tmp_dir or DEFAULT_TMP_ROOT).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        if "X" not in template:
            template += ".XXXXXXXXXX"

        # Count trailing X's
        prefix = template.rstrip("X")
        x_count = len(template) - len(prefix)
        if x_count < 3:
            x_count = 6

        random_token = "".join(secrets.choice(ALPHANUMERIC) for _ in range(x_count))
        final_name = f"{prefix}{random_token}"
        final_path = target_dir / final_name

        if dry_run:
            return final_path

        if directory:
            return cls.create_temp_dir(prefix=prefix, suffix="", dir_path=target_dir)
        else:
            return cls.create_temp_file(prefix=prefix, suffix="", dir_path=target_dir)


class SecureTempFile:
    """Context manager for automatic deletion of temporary files."""

    def __init__(
        self,
        prefix: str = "tmp.",
        suffix: str = "",
        dir_path: Optional[Path | str] = None,
        content: Optional[bytes | str] = None,
    ) -> None:
        self.prefix = prefix
        self.suffix = suffix
        self.dir_path = dir_path
        self.content = content
        self.path: Optional[Path] = None

    def __enter__(self) -> Path:
        self.path = SecureIO.create_temp_file(
            prefix=self.prefix,
            suffix=self.suffix,
            dir_path=self.dir_path,
            content=self.content,
        )
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.path and self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass


class SecureTempDir:
    """Context manager for automatic deletion of temporary directory trees."""

    def __init__(
        self,
        prefix: str = "tmp.",
        suffix: str = "",
        dir_path: Optional[Path | str] = None,
    ) -> None:
        self.prefix = prefix
        self.suffix = suffix
        self.dir_path = dir_path
        self.path: Optional[Path] = None

    def __enter__(self) -> Path:
        self.path = SecureIO.create_temp_dir(
            prefix=self.prefix,
            suffix=self.suffix,
            dir_path=self.dir_path,
        )
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.path and self.path.exists():
            try:
                shutil.rmtree(self.path, ignore_errors=True)
            except OSError:
                pass
