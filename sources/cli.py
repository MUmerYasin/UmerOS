"""
UmerOS /sources — Command Line Interface (sources_ctl)
======================================================

Provides command-line query, search, and citation tools for the Linux Filesystem
Hierarchy sources, System V signals, architecture glossary, and kernel documentation.

Usage:
    python -m sources.cli list
    python -m sources.cli show <key>
    python -m sources.cli search <query>
    python -m sources.cli signals [name|number]
    python -m sources.cli glossary [term]
    python -m sources.cli kernel-doc [name]
    python -m sources.cli export [--format bibtex|markdown|json]
    python -m sources.cli summary

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from manager import SourcesManager


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sources_ctl",
        description="UmerOS /sources Reference, Signals & Standards Controller",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list
    subparsers.add_parser("list", help="List all bibliography sources")

    # show
    show_p = subparsers.add_parser("show", help="Show full details for a citation key")
    show_p.add_argument("key", help="Citation key (e.g. kernighan1984unix, fhs_spec)")

    # search
    search_p = subparsers.add_parser("search", help="Unified search across sources, glossary, signals")
    search_p.add_argument("query", help="Search string")

    # signals
    sig_p = subparsers.add_parser("signals", help="List or inspect System V signals")
    sig_p.add_argument("signal", nargs="?", help="Optional signal name (e.g. SIGINT, SIGHUP, 9)")

    # glossary
    glo_p = subparsers.add_parser("glossary", help="Search or view architecture glossary terms")
    glo_p.add_argument("term", nargs="?", help="Optional term name (e.g. FHS, inode, tmpfs)")

    # kernel-doc
    doc_p = subparsers.add_parser("kernel-doc", help="View kernel documentation specifications")
    doc_p.add_argument("name", nargs="?", help="Doc name (proc.txt, initrd.txt, runlevels)")

    # export
    exp_p = subparsers.add_parser("export", help="Export bibliography references")
    exp_p.add_argument("--format", default="markdown", choices=["markdown", "bibtex", "json"], help="Output format")

    # summary
    subparsers.add_parser("summary", help="Show summary statistics")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    mgr = SourcesManager()

    if args.command == "list":
        sources = mgr.bibliography.list_all()
        print(f"\nLinux Filesystem Hierarchy Sources & Bibliography (Total: {len(sources)}):")
        print("=" * 75)
        for s in sources:
            year_str = f"({s.year})" if s.year else ""
            authors_str = ", ".join(s.authors[:2])
            if len(s.authors) > 2:
                authors_str += " et al."
            print(f"  * {s.key:<22} [{s.category.value:<10}] {s.title} {year_str} - {authors_str}")
        print("=" * 75 + "\n")
        return 0

    elif args.command == "show":
        s = mgr.bibliography.get(args.key)
        if not s:
            print(f"Error: Source '{args.key}' not found.", file=sys.stderr)
            return 1
        print(f"\nCitation: {s.title}")
        print("-" * 60)
        print(s.to_bibtex())
        print("-" * 60 + "\n")
        return 0

    elif args.command == "search":
        res = mgr.search_all(args.query)
        print(f"\nSearch Results for '{args.query}' (Total: {res['total_matches']}):")
        print("=" * 65)
        if res["bibliography"]:
            print("\n[Bibliography References]:")
            for b in res["bibliography"]:
                print(f"  * {b['key']}: {b['title']} ({', '.join(b['authors'])})")
        if res["glossary"]:
            print("\n[Glossary Terms]:")
            for g in res["glossary"]:
                print(f"  * {g['term']}: {g['definition']}")
        if res["signals"]:
            print("\n[System V Signals]:")
            for sig in res["signals"]:
                print(f"  * {sig['name']} ({sig['number']}): {sig['description']} [Action: {sig['action']}]")
        if res["kernel_docs"]:
            print("\n[Kernel Specifications]:")
            for d in res["kernel_docs"]:
                print(f"  * {d['title']}: {d['summary']}")
        print("=" * 65 + "\n")
        return 0

    elif args.command == "signals":
        if args.signal:
            sig = mgr.signals.get_signal(args.signal)
            if not sig:
                print(f"Error: Signal '{args.signal}' not found.", file=sys.stderr)
                return 1
            print(f"\nSignal Specification: {sig.name} ({sig.number})")
            print("-" * 50)
            print(f"Name:        {sig.name}")
            print(f"Number:      {sig.number}")
            print(f"Action:      {sig.action.value}")
            print(f"Can Catch:   {sig.can_catch}")
            print(f"Can Ignore:  {sig.can_ignore}")
            print(f"Description: {sig.description}")
            print("-" * 50 + "\n")
        else:
            sigs = mgr.signals.list_signals()
            print(f"\nUNIX System V & POSIX Signals (Total: {len(sigs)}):")
            print("=" * 70)
            for s in sigs:
                catch_str = "Catchable" if s.can_catch else "UNCATCHABLE"
                print(f"  {s.number:>2} | {s.name:<10} [{s.action.value:<4}] [{catch_str:<11}] {s.description}")
            print("=" * 70 + "\n")
        return 0

    elif args.command == "glossary":
        if args.term:
            entry = mgr.glossary.get(args.term)
            if not entry:
                # Try search
                matches = mgr.glossary.search(args.term)
                if not matches:
                    print(f"Error: Term '{args.term}' not found in glossary.", file=sys.stderr)
                    return 1
                entry = matches[0]
            print(f"\nGlossary Definition: {entry.term}")
            print("-" * 50)
            print(f"Category:  {entry.category}")
            print(f"Definition: {entry.definition}")
            if entry.see_also:
                print(f"See Also:  {', '.join(entry.see_also)}")
            print("-" * 50 + "\n")
        else:
            terms = mgr.glossary.list_all()
            print(f"\nLinux Filesystem Hierarchy Glossary (Total: {len(terms)}):")
            print("=" * 70)
            for t in terms:
                print(f"  * {t.term:<16} [{t.category:<12}] {t.definition[:70]}...")
            print("=" * 70 + "\n")
        return 0

    elif args.command == "kernel-doc":
        if args.name:
            doc = mgr.kernel_docs.get_doc(args.name)
            if not doc:
                print(f"Error: Kernel doc '{args.name}' not found.", file=sys.stderr)
                return 1
            print(f"\nKernel Specification: {doc['title']}")
            print("=" * 60)
            print(f"Authors: {', '.join(doc['authors'])}")
            print(f"Summary: {doc['summary']}\n")
            print("Sections:")
            for s_title, s_content in doc["sections"].items():
                print(f"  [{s_title}]: {s_content}")
            print("=" * 60 + "\n")
        else:
            docs = mgr.kernel_docs.list_docs()
            print("\nAvailable Kernel Specifications:")
            for d in docs:
                print(f"  - {d}")
            print()
        return 0

    elif args.command == "export":
        print(mgr.bibliography.export(format_type=args.format))
        return 0

    elif args.command == "summary":
        s = mgr.get_summary()
        print("\nUmerOS /sources Subsystem Summary:")
        print("=" * 50)
        print(f"Bibliography Citations: {s['total_bibliography_sources']}")
        print(f"Glossary Terms:         {s['total_glossary_terms']}")
        print(f"System V Signals:       {s['total_signals_defined']}")
        print(f"Kernel Specifications:  {s['total_kernel_specs']}")
        print(f"Source Packages:        {s['source_tree_packages']}")
        print("=" * 50 + "\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
