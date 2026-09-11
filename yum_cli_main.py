"""YumManager CLI — full argparse interface for UmerOS package management.

All subcommands map to YumManager public methods. Output is JSON by default;
use ``--human`` for human-readable tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from srv.yum_manager import YumManager


def _manager(args: argparse.Namespace) -> YumManager:
    """Construct a YumManager from CLI-level directory options."""
    return YumManager(
        base_dir=args.base_dir,
        cache_dir=args.cache_dir,
        repos_dir=args.repos_dir,
        history_dir=args.history_dir,
        groups_dir=args.groups_dir,
    )


def _json(data: Any) -> None:
    """Pretty-print JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Package operations
# ---------------------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    result = mgr.install(
        packages=args.packages,
        assume_yes=args.assume_yes,
        skip_broken=args.skip_broken,
        no_deps=args.no_deps,
    )
    _json({"success": result.success, "installed": result.installed, "errors": result.errors})
    return 0 if result.success else 1


def cmd_update(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    result = mgr.update(
        packages=args.packages or None,
        security_only=args.security_only,
        minimal=args.minimal,
        assume_yes=args.assume_yes,
    )
    _json({"success": result.success, "updated": result.updated, "errors": result.errors})
    return 0 if result.success else 1


def cmd_remove(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    result = mgr.remove(
        packages=args.packages,
        nodeps=args.nodeps,
        assume_yes=args.assume_yes,
    )
    _json({"success": result.success, "removed": result.removed, "errors": result.errors})
    return 0 if result.success else 1


def cmd_downgrade(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    result = mgr.downgrade(packages=args.packages)
    _json({"success": result.success, "downgraded": result.downgraded, "errors": result.errors})
    return 0 if result.success else 1


def cmd_reinstall(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    result = mgr.reinstall(packages=args.packages)
    _json({"success": result.success, "reinstalled": result.reinstalled, "errors": result.errors})
    return 0 if result.success else 1


def cmd_local(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    result = mgr.local_install(path=args.path)
    _json({"success": result.success, "installed": result.installed, "errors": result.errors})
    return 0 if result.success else 1


# ---------------------------------------------------------------------------
# Query operations
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    if args.installed:
        packages = mgr.list_installed()
    elif args.updates:
        packages = mgr.list_updates()
    else:
        packages = mgr.list_available()
    _json(packages)
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    info = mgr.info(packages=args.packages)
    _json(info)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    results = mgr.search(query=args.query)
    _json(results)
    return 0


def cmd_provides(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    results = mgr.provides(query=args.query)
    _json(results)
    return 0


def cmd_whatrequires(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    results = mgr.whatrequires(query=args.query)
    _json(results)
    return 0


def cmd_check_update(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    updates = mgr.check_update()
    _json(updates)
    return 0


def cmd_distro_sync(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    result = mgr.distro_sync()
    _json({"success": result.success, "synced": result.synced, "errors": result.errors})
    return 0 if result.success else 1


# ---------------------------------------------------------------------------
# Repository management
# ---------------------------------------------------------------------------

def cmd_repo(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    sub = args.repo_action

    if sub == "list":
        repos = mgr.repo_list()
        _json(repos)
        return 0
    if sub == "add":
        ok = mgr.repo_add(name=args.name, url=args.url, gpgcheck=not args.no_gpgcheck)
        _json({"success": ok, "repo": args.name})
        return 0 if ok else 1
    if sub == "remove":
        ok = mgr.repo_remove(name=args.name)
        _json({"success": ok, "repo": args.name})
        return 0 if ok else 1
    if sub == "enable":
        ok = mgr.repo_enable(name=args.name)
        _json({"success": ok, "repo": args.name})
        return 0 if ok else 1
    if sub == "disable":
        ok = mgr.repo_disable(name=args.name)
        _json({"success": ok, "repo": args.name})
        return 0 if ok else 1

    return 0


# ---------------------------------------------------------------------------
# Group management
# ---------------------------------------------------------------------------

def cmd_group(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    sub = args.group_action

    if sub == "list":
        groups = mgr.group_list()
        _json(groups)
        return 0
    if sub == "info":
        info = mgr.group_info(group_name=args.name)
        _json(info)
        return 0
    if sub == "install":
        ok = mgr.group_install(group_name=args.name)
        _json({"success": ok, "group": args.name})
        return 0 if ok else 1
    if sub == "remove":
        ok = mgr.group_remove(group_name=args.name)
        _json({"success": ok, "group": args.name})
        return 0 if ok else 1
    if sub == "mark":
        ok = mgr.group_mark(group_name=args.name, mark_action=args.mark_action)
        _json({"success": ok, "group": args.name, "mark": args.mark_action})
        return 0 if ok else 1

    return 0


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------

def cmd_history(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    sub = args.history_action

    if sub == "list":
        history = mgr.history_list()
        _json(history)
        return 0
    if sub == "info":
        info = mgr.history_info(txn_id=args.txn_id)
        _json(info)
        return 0
    if sub == "undo":
        result = mgr.history_undo(txn_id=args.txn_id)
        _json({"success": result.success, "undone": result.undone, "errors": result.errors})
        return 0 if result.success else 1
    if sub == "rollback":
        result = mgr.history_rollback(txn_id=args.txn_id)
        _json({"success": result.success, "rolled_back": result.rolled_back, "errors": result.errors})
        return 0 if result.success else 1

    return 0


# ---------------------------------------------------------------------------
# Security updates
# ---------------------------------------------------------------------------

def cmd_security(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    updates = mgr.security_updates()
    _json(updates)
    return 0


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def cmd_clean(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    cleaned = mgr.clean(cache_type=args.cache_type)
    _json({"cleaned": cleaned})
    return 0


def cmd_autoremove(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    removed = mgr.autoremove()
    _json({"removed": removed})
    return 0


# ---------------------------------------------------------------------------
# Shell mode
# ---------------------------------------------------------------------------

def cmd_shell(args: argparse.Namespace) -> int:
    """Interactive shell for YumManager commands."""
    mgr = _manager(args)
    print("yum> type 'help' for commands, 'quit' to exit.")
    while True:
        try:
            line = input("yum> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("quit", "exit", "q"):
            break
        if line == "help":
            print(
                "Commands: install, update, remove, list, info, search, "
                "repo, group, history, clean, stats, quit"
            )
            continue
        if line == "stats":
            _json(mgr.stats())
            continue
        # Delegate to a fresh argparse parse for each line
        parts = line.split()
        subcmd = parts[0]
        try:
            rest_args = _shell_parser.parse_args(parts)
            rest_args.base_dir = args.base_dir
            rest_args.cache_dir = args.cache_dir
            rest_args.repos_dir = args.repos_dir
            rest_args.history_dir = args.history_dir
            rest_args.groups_dir = args.groups_dir
            HANDLERS.get(subcmd, _shell_unknown)(rest_args)
        except SystemExit:
            pass
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
    return 0


def _shell_unknown(args: argparse.Namespace) -> int:
    print(f"Unknown command: {getattr(args, 'command', '?')}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def cmd_stats(args: argparse.Namespace) -> int:
    mgr = _manager(args)
    stats = mgr.stats()
    _json(stats)
    return 0


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yum",
        description="UmerOS Yum-like package manager",
    )
    parser.add_argument("--base-dir", default="/", help="Root directory for package DB")
    parser.add_argument("--cache-dir", default=None, help="Cache directory (default: /var/cache/yum)")
    parser.add_argument("--repos-dir", default=None, help="Repos directory (default: /etc/yum.repos.d)")
    parser.add_argument("--history-dir", default=None, help="History directory (default: /var/lib/yum/history)")
    parser.add_argument("--groups-dir", default=None, help="Groups directory (default: /etc/yum/groups)")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- install ---
    p = sub.add_parser("install", help="Install packages")
    p.add_argument("packages", nargs="+", help="Package names to install")
    p.add_argument("-y", "--assume-yes", action="store_true", help="Automatic yes")
    p.add_argument("--skip-broken", action="store_true", help="Skip broken packages")
    p.add_argument("--no-deps", action="store_true", help="Skip dependency resolution")

    # --- update ---
    p = sub.add_parser("update", help="Update packages")
    p.add_argument("packages", nargs="*", help="Package names (empty = full update)")
    p.add_argument("--security-only", action="store_true", help="Security updates only")
    p.add_argument("--minimal", action="store_true", help="Minimal update")
    p.add_argument("-y", "--assume-yes", action="store_true", help="Automatic yes")

    # --- remove ---
    p = sub.add_parser("remove", help="Remove packages")
    p.add_argument("packages", nargs="+", help="Package names to remove")
    p.add_argument("--nodeps", action="store_true", help="Skip dependency check")
    p.add_argument("-y", "--assume-yes", action="store_true", help="Automatic yes")

    # --- downgrade ---
    p = sub.add_parser("downgrade", help="Downgrade packages")
    p.add_argument("packages", nargs="+", help="Package names to downgrade")

    # --- reinstall ---
    p = sub.add_parser("reinstall", help="Reinstall packages")
    p.add_argument("packages", nargs="+", help="Package names to reinstall")

    # --- local ---
    p = sub.add_parser("local", help="Install from local RPM file")
    p.add_argument("path", help="Path to RPM file")

    # --- list ---
    p = sub.add_parser("list", help="List packages")
    p.add_argument("--installed", action="store_true", help="List installed packages")
    p.add_argument("--updates", action="store_true", help="List available updates")

    # --- info ---
    p = sub.add_parser("info", help="Show package info")
    p.add_argument("packages", nargs="+", help="Package names")

    # --- search ---
    p = sub.add_parser("search", help="Search packages")
    p.add_argument("query", help="Search query")

    # --- provides ---
    p = sub.add_parser("provides", help="Search for packages providing a capability")
    p.add_argument("query", help="Capability or file to search for")

    # --- whatrequires ---
    p = sub.add_parser("whatrequires", help="Search for packages requiring a capability")
    p.add_argument("query", help="Capability to search for")

    # --- check-update ---
    sub.add_parser("check-update", help="Check for available updates")

    # --- distro-sync ---
    sub.add_parser("distro-sync", help="Synchronize installed packages with repo")

    # --- repo ---
    p = sub.add_parser("repo", help="Repository management")
    rp = p.add_subparsers(dest="repo_action", help="Repo actions")
    rp.add_parser("list", help="List repositories")
    a = rp.add_parser("add", help="Add a repository")
    a.add_argument("name", help="Repository name")
    a.add_argument("url", help="Repository URL")
    a.add_argument("--no-gpgcheck", action="store_true", help="Disable GPG check")
    rm = rp.add_parser("remove", help="Remove a repository")
    rm.add_argument("name", help="Repository name")
    en = rp.add_parser("enable", help="Enable a repository")
    en.add_argument("name", help="Repository name")
    dis = rp.add_parser("disable", help="Disable a repository")
    dis.add_argument("name", help="Repository name")

    # --- group ---
    p = sub.add_parser("group", help="Package group management")
    gp = p.add_subparsers(dest="group_action", help="Group actions")
    gp.add_parser("list", help="List groups")
    gi = gp.add_parser("info", help="Group info")
    gi.add_argument("name", help="Group name")
    ginst = gp.add_parser("install", help="Install a group")
    ginst.add_argument("name", help="Group name")
    grem = gp.add_parser("remove", help="Remove a group")
    grem.add_argument("name", help="Group name")
    gmk = gp.add_parser("mark", help="Mark a group")
    gmk.add_argument("name", help="Group name")
    gmk.add_argument("mark_action", choices=["install", "remove"], help="Mark action")

    # --- history ---
    p = sub.add_parser("history", help="Transaction history")
    hp = p.add_subparsers(dest="history_action", help="History actions")
    hp.add_parser("list", help="List history")
    hi = hp.add_parser("info", help="Transaction info")
    hi.add_argument("txn_id", help="Transaction ID")
    hu = hp.add_parser("undo", help="Undo a transaction")
    hu.add_argument("txn_id", help="Transaction ID")
    hr = hp.add_parser("rollback", help="Rollback to a transaction")
    hr.add_argument("txn_id", help="Transaction ID")

    # --- security ---
    sub.add_parser("security", help="List security updates")

    # --- clean ---
    p = sub.add_parser("clean", help="Clean package cache")
    p.add_argument("cache_type", nargs="?", default="all",
                    choices=["all", "packages", "metadata", "expire-cache"],
                    help="Cache type to clean")

    # --- autoremove ---
    sub.add_parser("autoremove", help="Remove unused dependencies")

    # --- stats ---
    sub.add_parser("stats", help="Show manager statistics")

    # --- shell ---
    sub.add_parser("shell", help="Interactive yum shell")

    return parser


# Shell-mode parser (lightweight, reuses subcommand parsers)
_shell_parser = build_parser()

HANDLERS = {
    "install": cmd_install,
    "update": cmd_update,
    "remove": cmd_remove,
    "downgrade": cmd_downgrade,
    "reinstall": cmd_reinstall,
    "local": cmd_local,
    "list": cmd_list,
    "info": cmd_info,
    "search": cmd_search,
    "provides": cmd_provides,
    "whatrequires": cmd_whatrequires,
    "check-update": cmd_check_update,
    "distro-sync": cmd_distro_sync,
    "repo": cmd_repo,
    "group": cmd_group,
    "history": cmd_history,
    "security": cmd_security,
    "clean": cmd_clean,
    "autoremove": cmd_autoremove,
    "stats": cmd_stats,
    "shell": cmd_shell,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    handler = HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
