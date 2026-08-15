"""
UmerOS /legal — Command Line Interface (legal_ctl)
==================================================

Provides command-line management for disclaimers, user consent, open-source
licenses, contributors, donations, and safety checks.

Usage:
    python -m legal.cli disclaimer [key]
    python -m legal.cli consent [key]
    python -m legal.cli verify [key]
    python -m legal.cli contributors
    python -m legal.cli donations
    python -m legal.cli maintainers
    python -m legal.cli licenses [dir]
    python -m legal.cli safety-check <operation> [--target path]
    python -m legal.cli summary

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from disclaimer import RiskLevel
from manager import LegalManager


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legal_ctl",
        description="UmerOS Legal, Disclaimer, Consent & Compliance Controller",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # disclaimer
    disc_p = subparsers.add_parser("disclaimer", help="View legal disclaimers and waivers")
    disc_p.add_argument("key", nargs="?", default="general", help="Disclaimer key (general, tldp, installer, kernel_hal, quantum_ai)")

    # consent
    con_p = subparsers.add_parser("consent", help="Grant and record explicit legal consent")
    con_p.add_argument("key", nargs="?", default="general", help="Disclaimer key")
    con_p.add_argument("--user", help="Username granting consent")

    # verify
    ver_p = subparsers.add_parser("verify", help="Verify if valid consent exists")
    ver_p.add_argument("key", nargs="?", default="general", help="Disclaimer key")

    # contributors
    subparsers.add_parser("contributors", help="List recognized project contributors & DCO status")

    # donations
    subparsers.add_parser("donations", help="Show funding channels and sponsor wall")

    # maintainers
    subparsers.add_parser("maintainers", help="View verified maintainer profiles & PQC keys")

    # licenses
    lic_p = subparsers.add_parser("licenses", help="Scan directory for license header compliance")
    lic_p.add_argument("dir", nargs="?", default=".", help="Directory to scan")

    # safety-check
    safe_p = subparsers.add_parser("safety-check", help="Run pre-execution safety and backup check")
    safe_p.add_argument("operation", help="Name of operation (e.g. partition_disk, flash_kernel)")
    safe_p.add_argument("--target", help="Target path to inspect and backup")
    safe_p.add_argument("--risk", default="moderate", choices=["safe", "moderate", "high", "critical"])

    # summary
    subparsers.add_parser("summary", help="Show overview summary of legal and compliance records")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    mgr = LegalManager()

    if args.command == "disclaimer":
        notice = mgr.disclaimers.get_notice(args.key)
        print(f"\n{notice.title}")
        print("=" * 65)
        print(notice.full_text)
        print("=" * 65)
        print(f"Risk Level:            {notice.risk_level.value.upper()}")
        print(f"Requires User Consent: {'YES' if notice.requires_explicit_consent else 'NO'}")
        print(f"Backup Recommended:    {'YES' if notice.backup_recommended else 'NO'}\n")
        return 0

    elif args.command == "consent":
        rec = mgr.consent.grant_consent(
            disclaimer_key=args.key,
            user_response="I AGREE",
            user_name=args.user,
        )
        print(f"[OK] Consent granted for '{args.key}':")
        print(f"  - User:      {rec.user_name}")
        print(f"  - Host:      {rec.hostname}")
        print(f"  - Machine:   {rec.machine_id}")
        print(f"  - Token:     {rec.consent_token[:16]}...")
        return 0

    elif args.command == "verify":
        has = mgr.consent.has_consented(args.key)
        print(f"Consent status for '{args.key}': {'VALID / GRANTED' if has else 'NOT GRANTED'}")
        return 0 if has else 1

    elif args.command == "contributors":
        print(mgr.contributors.generate_acknowledgements_md())
        return 0

    elif args.command == "donations":
        print(mgr.donations.generate_sponsors_md())
        return 0

    elif args.command == "maintainers":
        maintainers = mgr.maintainers.list_all()
        print(f"\nUmerOS Core Subsystem Maintainers (Total: {len(maintainers)}):")
        print("=" * 70)
        for m in maintainers:
            print(f"  * {m.name} (@{m.handle}) — {m.role}")
            print(f"    Email:        {m.email}")
            print(f"    PQC Key:      {m.pqc_public_key_fingerprint}")
            print(f"    PGP Key:      {m.pgp_fingerprint}")
            print(f"    Subsystems:   {', '.join(m.subsystems_maintained)}")
        print("=" * 70 + "\n")
        return 0

    elif args.command == "licenses":
        res = mgr.licenses.scan_directory(args.dir)
        print(res.summary())
        return 0

    elif args.command == "safety-check":
        risk = RiskLevel(args.risk)
        res = mgr.safety.verify_safety(
            operation_name=args.operation,
            risk_level=risk,
            target_path=args.target,
        )
        print(res.summary())
        return 0 if res.is_safe else 1

    elif args.command == "summary":
        s = mgr.get_summary()
        print("\nUmerOS Legal & Compliance Summary:")
        print("=" * 50)
        print(f"Disclaimer Notices:    {s['disclaimer_notices']}")
        print(f"Recorded Consents:     {s['recorded_consents']}")
        print(f"Recognized Contributors:{s['contributors_count']}")
        print(f"Subsystem Maintainers: {s['maintainers_count']}")
        print(f"Funding Channels:      {s['funding_channels']}")
        print("=" * 50 + "\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
