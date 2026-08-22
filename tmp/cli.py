"""
UmerOS /tmp — Command Line Interface (tmp_ctl)
==============================================

Provides command-line management and utilities for the /tmp filesystem hierarchy.

Usage:
    python -m tmp.cli list
    python -m tmp.cli mktemp [template] [-d]
    python -m tmp.cli clean [--max-age SEC] [--dry-run]
    python -m tmp.cli boot-clean [--dry-run]
    python -m tmp.cli locks
    python -m tmp.cli audit
    python -m tmp.cli summary
    python -m tmp.cli bootstrap

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .manager import TmpManager


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tmp_ctl",
        description="UmerOS /tmp Filesystem Hierarchy & Temporary Space Controller",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list
    subparsers.add_parser("list", help="List all entries currently in /tmp")

    # mktemp
    mk_p = subparsers.add_parser("mktemp", help="Create a secure temporary file or directory")
    mk_p.add_argument("template", nargs="?", default="tmp.XXXXXXXXXX", help="Template string (e.g. tmp.XXXXXXXXXX)")
    mk_p.add_argument("-d", "--directory", action="store_true", help="Create a directory instead of a file")
    mk_p.add_argument("-u", "--dry-run", action="store_true", help="Print path without creating it")

    # clean
    cl_p = subparsers.add_parser("clean", help="Clean /tmp files by age (tmpwatch)")
    cl_p.add_argument("--max-age", type=float, default=None, help="Maximum age in seconds before removal")
    cl_p.add_argument("--dry-run", action="store_true", help="Show files that would be deleted without deleting")

    # boot-clean
    bc_p = subparsers.add_parser("boot-clean", help="Simulate boot-time cleanup of /tmp")
    bc_p.add_argument("--dry-run", action="store_true", help="Dry run simulation")

    # locks
    subparsers.add_parser("locks", help="List active process lockfiles in /tmp")

    # audit
    subparsers.add_parser("audit", help="Run FHS compliance and permission security audit")

    # summary
    subparsers.add_parser("summary", help="Show /tmp disk and memory usage summary")

    # bootstrap
    subparsers.add_parser("bootstrap", help="Bootstrap standard socket subdirectories")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    mgr = TmpManager()

    if args.command == "list":
        entries = mgr.hierarchy.list_entries()
        print(f"\nUmerOS /tmp Entries (Total: {len(entries)}):")
        print("=" * 65)
        for e in entries:
            type_str = "DIR " if e["is_dir"] else "FILE"
            prot_str = "[PROTECTED]" if e["is_protected"] else "           "
            print(f"  {type_str} {prot_str} {e['size_bytes']:>8} bytes | {e['name']}")
        print("=" * 65 + "\n")
        return 0

    elif args.command == "mktemp":
        path = mgr.mktemp(
            template=args.template,
            directory=args.directory,
            dry_run=args.dry_run,
        )
        print(str(path))
        return 0

    elif args.command == "clean":
        rep = mgr.clean(max_age_seconds=args.max_age, dry_run=args.dry_run)
        print(rep.summary())
        return 0

    elif args.command == "boot-clean":
        rep = mgr.wipe_on_boot(dry_run=args.dry_run)
        print(rep.summary())
        return 0

    elif args.command == "locks":
        locks = mgr.list_locks()
        print(f"\nActive /tmp Process Locks (Total: {len(locks)}):")
        print("=" * 65)
        for l in locks:
            st = "ALIVE" if l.get("is_pid_alive") else "DEAD/STALE"
            print(f"  * {l.get('name', 'unknown'):<20} PID: {l.get('pid', 'N/A')} [{st}] | Host: {l.get('hostname', 'N/A')}")
        print("=" * 65 + "\n")
        return 0

    elif args.command == "audit":
        audit = mgr.audit_all()
        print(f"\n/tmp FHS & Security Audit (Root: {audit['root']}):")
        print("=" * 60)
        print(f"FHS Compliant:  {'YES' if audit['fhs_compliant'] else 'NO'}")
        print(f"Security Level: {'SECURE' if audit['security_secure'] else 'WARNINGS DETECTED'}")
        print(f"Sticky Bit Set: {'YES' if audit['sticky_bit_set'] else 'NO'}")
        print("-" * 60)
        for v in audit["fhs_violations"]:
            print(f"  - [FHS Error] {v}")
        for i in audit["security_issues"]:
            print(f"  - [Security]  {i}")
        for r in audit["recommendations"]:
            print(f"  - [Recommendation] {r}")
        print("=" * 60 + "\n")
        return 0

    elif args.command == "summary":
        s = mgr.get_summary()
        print("\nUmerOS /tmp Storage Summary:")
        print("=" * 50)
        print(f"Root Directory:    {s['root']}")
        print(f"Total Size:        {s['total_size_bytes']} bytes")
        print(f"Total Files:       {s['total_files']}")
        print(f"Total Dirs:        {s['total_dirs']}")
        print(f"Active Locks:      {s['active_locks']}")
        print(f"TmpFS RAM Free:    {s['tmpfs_free_bytes']} bytes")
        print("=" * 50 + "\n")
        return 0

    elif args.command == "bootstrap":
        created = mgr.hierarchy.bootstrap()
        print("[OK] Bootstrapped /tmp socket skeletons:")
        for k, v in created.items():
            print(f"  - {k}: {v}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
