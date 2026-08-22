# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS /srv — Command Line Interface (srv_ctl)
==============================================

Provides full command-line management for the /srv filesystem hierarchy.

Usage:
    python -m srv.cli list
    python -m srv.cli show <name>
    python -m srv.cli create <name> --protocol <proto> [--domain <domain>]
    python -m srv.cli bootstrap
    python -m srv.cli audit
    python -m srv.cli summary
    python -m srv.cli backup <name> [--format tar.gz|zip]
    python -m srv.cli restore <archive> [--overwrite]

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .fhs import OrganizationScheme, StandardProtocol
from .manager import SrvManager


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srv_ctl",
        description="UmerOS /srv Filesystem Hierarchy & Service Controller (TLDP FHS)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list
    subparsers.add_parser("list", help="List all services registered under /srv")

    # show
    show_p = subparsers.add_parser("show", help="Show detailed info for a service")
    show_p.add_argument("name", help="Name of the service")

    # create
    create_p = subparsers.add_parser("create", help="Create and provision a new service tree")
    create_p.add_argument("name", help="Name of the service (e.g. www, git, mysite)")
    create_p.add_argument("--protocol", "-p", default="www", choices=[p.value for p in StandardProtocol], help="Protocol")
    create_p.add_argument("--scheme", "-s", default="by_protocol", choices=[s.value for s in OrganizationScheme], help="Scheme")
    create_p.add_argument("--domain", "-d", help="Domain or Virtual Host name")
    create_p.add_argument("--dept", help="Department name")

    # register
    reg_p = subparsers.add_parser("register", help="Register an existing directory")
    reg_p.add_argument("name", help="Service name")
    reg_p.add_argument("path", help="Path to register")
    reg_p.add_argument("--protocol", "-p", default="www", choices=[p.value for p in StandardProtocol], help="Protocol")

    # remove
    rem_p = subparsers.add_parser("remove", help="Remove a service registration")
    rem_p.add_argument("name", help="Service name")
    rem_p.add_argument("--delete-files", action="store_true", help="Delete physical files")
    rem_p.add_argument("--force", action="store_true", help="Force deletion without prompt")

    # bootstrap
    subparsers.add_parser("bootstrap", help="Bootstrap standard TLDP /srv skeletons")

    # audit
    subparsers.add_parser("audit", help="Run FHS compliance & security audit on /srv")

    # summary
    subparsers.add_parser("summary", help="Show /srv storage summary and stats")

    # backup
    bak_p = subparsers.add_parser("backup", help="Create backup archive of a service")
    bak_p.add_argument("name", help="Service name")
    bak_p.add_argument("--format", default="tar.gz", choices=["tar.gz", "zip"], help="Archive format")

    # restore
    res_p = subparsers.add_parser("restore", help="Restore service from backup archive")
    res_p.add_argument("archive", help="Path to backup archive")
    res_p.add_argument("--overwrite", action="store_true", help="Overwrite existing directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    mgr = SrvManager()

    if args.command == "list":
        services = mgr.list_services()
        print(f"\nUmerOS /srv Registered Services (Total: {len(services)}):")
        print("=" * 70)
        for name, rec in sorted(services.items()):
            proto = rec.config.protocol.value if hasattr(rec.config.protocol, "value") else str(rec.config.protocol)
            print(f"  * {name:<18} [{proto:<6}] {rec.size_bytes:>8} bytes | Path: {rec.base_path}")
        print("=" * 70 + "\n")
        return 0

    elif args.command == "show":
        rec = mgr.get_service(args.name)
        if not rec:
            print(f"Error: Service '{args.name}' not found.", file=sys.stderr)
            return 1
        print(f"\nService Details: {rec.name}")
        print("-" * 50)
        print(json.dumps(rec.to_dict(), indent=2))
        print("-" * 50 + "\n")
        return 0

    elif args.command == "create":
        proto = StandardProtocol(args.protocol)
        scheme = OrganizationScheme(args.scheme)
        domain_or_dept = args.domain or args.dept
        rec = mgr.create_service(
            name=args.name,
            protocol=proto,
            scheme=scheme,
            domain_or_dept=domain_or_dept,
        )
        print(f"[OK] Service '{args.name}' successfully created at {rec.base_path}")
        return 0

    elif args.command == "register":
        proto = StandardProtocol(args.protocol)
        rec = mgr.register_service(name=args.name, path=args.path, protocol=proto)
        print(f"[OK] Registered service '{args.name}' -> {rec.base_path}")
        return 0

    elif args.command == "remove":
        ok = mgr.remove_service(args.name, delete_files=args.delete_files, force=args.force)
        if ok:
            print(f"[OK] Removed service '{args.name}'")
            return 0
        else:
            print(f"Error: Could not remove '{args.name}'", file=sys.stderr)
            return 1

    elif args.command == "bootstrap":
        created = mgr.hierarchy.bootstrap()
        print("[OK] Bootstrapped /srv standard skeletons:")
        for k, v in created.items():
            print(f"  - {k}: {v}")
        mgr.auto_discover()
        return 0

    elif args.command == "audit":
        report = mgr.audit_all()
        print(f"\n/srv FHS & Security Audit (Root: {report['srv_root']}):")
        print("=" * 60)
        print(f"Total Services: {report['total_services']}")
        print(f"Total Violations: {report['total_violations']}")
        print(f"Total Warnings: {report['total_warnings']}")
        print(f"Health Status: {'HEALTHY' if report['is_healthy'] else 'ISSUES FOUND'}")
        print("-" * 60)
        for name, details in report["services"].items():
            fhs_st = "COMPLIANT" if details["fhs_compliant"] else "VIOLATION"
            sec_st = "SECURE" if details["permission_secure"] else "UNSECURE"
            print(f"  [{fhs_st}] [{sec_st}] {name}")
            for viol in details["fhs_violations"]:
                print(f"      - [FHS Error] {viol}")
            for iss in details["permission_issues"]:
                print(f"      - [Security] {iss}")
        print("=" * 60 + "\n")
        return 0

    elif args.command == "summary":
        summary = mgr.get_summary()
        print("\nUmerOS /srv Summary:")
        print("=" * 50)
        print(f"Root Directory:     {summary['root']}")
        print(f"Total Services:     {summary['total_services']}")
        print(f"Total Size:         {summary['total_size_bytes']} bytes")
        print(f"Total Files:        {summary['total_files']}")
        print(f"Protocol Breakdown: {summary['protocol_breakdown']}")
        print("=" * 50 + "\n")
        return 0

    elif args.command == "backup":
        rec = mgr.get_service(args.name)
        if not rec:
            print(f"Error: Service '{args.name}' not found.", file=sys.stderr)
            return 1
        archive = mgr.backup_manager.create_backup(
            service_path=rec.base_path,
            service_name=rec.name,
            archive_format=args.format,
            service_record=rec,
        )
        print(f"[OK] Backup created: {archive}")
        return 0

    elif args.command == "restore":
        res = mgr.backup_manager.restore_backup(
            archive_path=args.archive,
            overwrite=args.overwrite,
        )
        print(f"[OK] Service restored to: {res['restored_path']}")
        mgr.auto_discover()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
