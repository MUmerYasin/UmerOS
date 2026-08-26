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
License: GPL-3.0 (GNU General Public License Version 3)
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
    con_p.add_argument(
        "--i-agree",
        action="store_true",
        help="Explicitly assert you have read and accept the liability waiver "
             "(required for non-interactive use; consent is never auto-granted)",
    )

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
    lic_p = subparsers.add_parser("licenses", help="Manage GPL-3.0 license and scan repository compliance")
    lic_p.add_argument("dir", nargs="?", default=".", help="Directory to scan")
    lic_p.add_argument("--apply", action="store_true", help="Apply GPL-3.0 header to all missing Python files")
    lic_p.add_argument("--show", action="store_true", help="Print the full GPL-3.0 License text")

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
        # [FIX H135] Never auto-grant consent. Require an explicit --i-agree flag
        # (out-of-band assertion) or real interactive 'I AGREE' input on a TTY.
        if not getattr(args, "i_agree", False):
            if sys.stdin.isatty():
                notice = mgr.disclaimers.get_notice(args.key)
                print("\n" + "=" * 65)
                print(f"       {notice.title.upper()}")
                print("=" * 65)
                print(notice.full_text)
                print("=" * 65)
                resp = input("Type 'I AGREE' to accept and proceed: ").strip()
                if resp.upper() != "I AGREE":
                    print("✗ Consent declined. Operation aborted.\n")
                    return 1
            else:
                print("[CONSENT] Refusing to grant consent non-interactively without --i-agree.",
                      file=sys.stderr)
                print("          Re-run on a terminal and type 'I AGREE', or pass --i-agree to "
                      "assert acceptance.", file=sys.stderr)
                return 1
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
        if getattr(args, "show", False):
            print(mgr.licenses.get_full_license_text())
            return 0
        if getattr(args, "apply", False):
            count = mgr.licenses.apply_headers_to_missing(args.dir)
            print(f"[OK] Applied GPL-3.0 header to {count} files.")
            return 0
        
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
