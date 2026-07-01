#!/usr/bin/env python3
"""
Umer OS Fluidic Shell

An interactive command-line interface for the Umer OS kernel.
Routes user commands to the VFS, Scheduler, AI Assistant, and
other kernel subsystems.

Commands:
    ls [path]        - List directory contents
    cat <path>       - Read a file
    write <path> <d> - Write data to a file
    mkdir <path>     - Create a directory
    rm <path>        - Delete a file
    stat <path>      - Show file/dir metadata
    ps               - List scheduled tasks
    ai <query>       - Ask the AI Assistant
    qseed            - Generate a quantum random seed
    ota              - Run OTA update check
    sysinfo          - Show system information
    help             - Show available commands
    exit / quit      - Shutdown the OS
"""

import sys
from ui.theme import Theme


class FluidicShell:
    """Interactive terminal shell for Umer OS."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.cwd = "/"
        self.running = True

    def _prompt(self) -> str:
        return f"{Theme.PROMPT_COLOR}umer-os{Theme.RESET}:{Theme.PATH_COLOR}{self.cwd}{Theme.RESET}$ "

    def start(self, interactive: bool = True):
        """Launch the shell. If not interactive, print banner and exit."""
        print(Theme.banner())
        print(Theme.styled("  Type 'help' for available commands.\n", Theme.DIM))

        if not interactive:
            print(Theme.styled("[SHELL] Non-interactive mode. Shell ready.", Theme.SYSTEM_COLOR))
            return

        while self.running:
            try:
                line = input(self._prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n" + Theme.styled("[SHELL] Shutting down...", Theme.SYSTEM_COLOR))
                break

            if not line:
                continue
            self._dispatch(line)

    def _dispatch(self, line: str):
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        commands = {
            "ls": self._cmd_ls,
            "cat": self._cmd_cat,
            "write": self._cmd_write,
            "mkdir": self._cmd_mkdir,
            "rm": self._cmd_rm,
            "stat": self._cmd_stat,
            "ps": self._cmd_ps,
            "ai": self._cmd_ai,
            "qseed": self._cmd_qseed,
            "ota": self._cmd_ota,
            "pkg": self._cmd_pkg,
            "drivers": self._cmd_drivers,
            "sysinfo": self._cmd_sysinfo,
            "startx": self._cmd_startx,
            "gui": self._cmd_startx,
            "help": self._cmd_help,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
        }

        handler = commands.get(cmd)
        if handler:
            try:
                handler(args)
            except Exception as e:
                print(Theme.styled(f"  Error: {e}", Theme.ERROR_COLOR))
        else:
            print(Theme.styled(f"  Unknown command: '{cmd}'. Type 'help' for usage.", Theme.ERROR_COLOR))

    # ── File System Commands ──────────────────────────────────────────

    def _cmd_ls(self, args: str):
        path = args.strip() or self.cwd
        entries = self.kernel.vfs.ls(path)
        if not entries:
            print(Theme.styled("  (empty)", Theme.DIM))
        for entry in entries:
            print(f"  {Theme.BRIGHT_CYAN}{entry}{Theme.RESET}")

    def _cmd_cat(self, args: str):
        if not args.strip():
            print(Theme.styled("  Usage: cat <path>", Theme.YELLOW))
            return
        data = self.kernel.vfs.read_file(args.strip())
        print(f"  {data.decode(errors='replace')}")

    def _cmd_write(self, args: str):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print(Theme.styled("  Usage: write <path> <data>", Theme.YELLOW))
            return
        path, data = parts
        self.kernel.vfs.write_file(path, data.encode())
        print(Theme.styled(f"  Written to {path}", Theme.SUCCESS_COLOR))

    def _cmd_mkdir(self, args: str):
        if not args.strip():
            print(Theme.styled("  Usage: mkdir <path>", Theme.YELLOW))
            return
        self.kernel.vfs.mkdir(args.strip())
        print(Theme.styled(f"  Created {args.strip()}", Theme.SUCCESS_COLOR))

    def _cmd_rm(self, args: str):
        if not args.strip():
            print(Theme.styled("  Usage: rm <path>", Theme.YELLOW))
            return
        if self.kernel.vfs.delete(args.strip()):
            print(Theme.styled(f"  Deleted {args.strip()}", Theme.SUCCESS_COLOR))
        else:
            print(Theme.styled(f"  Not found: {args.strip()}", Theme.ERROR_COLOR))

    def _cmd_stat(self, args: str):
        if not args.strip():
            print(Theme.styled("  Usage: stat <path>", Theme.YELLOW))
            return
        info = self.kernel.vfs.stat(args.strip())
        for k, v in info.items():
            print(f"  {Theme.BRIGHT_YELLOW}{k}{Theme.RESET}: {v}")

    # ── System Commands ───────────────────────────────────────────────

    def _cmd_ps(self, _args: str):
        if not self.kernel.scheduler.task_queue:
            print(Theme.styled("  No tasks in queue.", Theme.DIM))
            return
        print(f"  {'PID':<8}{'NAME':<25}{'PRIORITY':<10}")
        print(f"  {'---':<8}{'----':<25}{'--------':<10}")
        for task in self.kernel.scheduler.task_queue:
            print(f"  {task.pid:<8}{task.name:<25}{task.priority:<10}")

    def _cmd_ai(self, args: str):
        if not args.strip():
            print(Theme.styled("  Usage: ai <question>", Theme.YELLOW))
            return
        response = self.kernel.ai_assistant.query(args.strip())
        print(f"  {Theme.BRIGHT_MAGENTA}AI: {response}{Theme.RESET}")

    def _cmd_qseed(self, _args: str):
        seed = self.kernel.quantum.generate_random_seed()
        print(f"  {Theme.BRIGHT_GREEN}Quantum Seed: {seed}{Theme.RESET}")

    def _cmd_ota(self, _args: str):
        self.kernel.ota.run_update_pipeline()

    def _cmd_sysinfo(self, _args: str):
        import platform
        print(f"  {Theme.BOLD}Umer OS v2.0.0-Quantum{Theme.RESET}")
        print(f"  Architecture : {platform.machine()}")
        print(f"  Host Platform: {platform.system()} {platform.release()}")
        print(f"  Python       : {platform.python_version()}")
        stats = self.kernel.qfs.stats()
        print(f"  QFS Writes   : {stats['writes']}")
        print(f"  QFS Dedup    : {stats['dedup_hits']} hits, {stats['bytes_saved']}B saved")
        print(f"  Memory Used  : {sum(self.kernel.memory.allocated.values())} MB")

    # ── Package Manager Commands ──────────────────────────────────────

    def _cmd_pkg(self, args: str):
        parts = args.strip().split(maxsplit=1)
        if not parts:
            print(Theme.styled("  Usage: pkg <install|remove|list|search|info> [name]", Theme.YELLOW))
            return
        subcmd = parts[0].lower()
        name = parts[1] if len(parts) > 1 else ""

        if subcmd == "install" and name:
            self.kernel.pkg.install(name)
        elif subcmd == "remove" and name:
            self.kernel.pkg.remove(name)
        elif subcmd == "list":
            installed = self.kernel.pkg.list_installed()
            if not installed:
                print(Theme.styled("  No packages installed.", Theme.DIM))
            else:
                print(f"  {'PACKAGE':<25}{'VERSION':<15}")
                print(f"  {'-------':<25}{'-------':<15}")
                for pkg_name, ver in installed.items():
                    print(f"  {Theme.BRIGHT_CYAN}{pkg_name:<25}{Theme.RESET}{ver}")
        elif subcmd == "search" and name:
            results = self.kernel.pkg.search(name)
            if not results:
                print(Theme.styled(f"  No packages matching '{name}'.", Theme.DIM))
            else:
                for p in results:
                    print(f"  {Theme.BRIGHT_CYAN}{p.name:<20}{Theme.RESET}{p.version:<10}{p.description}")
        elif subcmd == "info" and name:
            info = self.kernel.pkg.info(name)
            if not info:
                print(Theme.styled(f"  Package '{name}' not found.", Theme.ERROR_COLOR))
            else:
                for k, v in info.items():
                    print(f"  {Theme.BRIGHT_YELLOW}{k:<15}{Theme.RESET}{v}")
        else:
            print(Theme.styled("  Usage: pkg <install|remove|list|search|info> [name]", Theme.YELLOW))

    # ── Driver Commands ───────────────────────────────────────────────

    def _cmd_drivers(self, args: str):
        parts = args.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "list"
        name = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            loaded = self.kernel.drivers.list_loaded()
            if not loaded:
                print(Theme.styled("  No drivers loaded.", Theme.DIM))
            else:
                print(f"  {'DRIVER':<20}{'VERSION':<10}{'TYPE':<20}{'STATUS':<10}")
                print(f"  {'------':<20}{'-------':<10}{'----':<20}{'------':<10}")
                for d in loaded:
                    status = Theme.styled("LOADED", Theme.SUCCESS_COLOR)
                    print(f"  {d['name']:<20}{d['version']:<10}{d['type']:<20}{status}")
        elif subcmd == "available":
            for name in self.kernel.drivers.list_available():
                print(f"  {Theme.BRIGHT_CYAN}{name}{Theme.RESET}")
        elif subcmd == "load" and name:
            self.kernel.drivers.load_driver(name)
        elif subcmd == "unload" and name:
            self.kernel.drivers.unload_driver(name)
        else:
            print(Theme.styled("  Usage: drivers <list|available|load|unload> [name]", Theme.YELLOW))

    # ── Help & Exit ───────────────────────────────────────────────────

    def _cmd_startx(self, _args: str):
        print(Theme.styled("  [GUI] Initializing graphical subsystem...", Theme.SYSTEM_COLOR))
        try:
            from kivy.app import App
            from kivy.uix.label import Label
            class UmerApp(App):
                def build(self):
                    return Label(text="Umer OS Graphical Shell (Stage 7 Demo)")
            print(Theme.styled("  [GUI] Launching Kivy interface...", Theme.SUCCESS_COLOR))
            UmerApp().run()
        except ImportError:
            print(Theme.styled("  [GUI] Error: Kivy not installed. Graphical shell unavailable.", Theme.ERROR_COLOR))
            print(Theme.styled("  [GUI] Falling back to Fluidic Terminal Shell.", Theme.YELLOW))

    def _cmd_help(self, _args: str):
        print(Theme.styled("  Available Commands:", Theme.HEADER_COLOR))
        cmds = [
            ("ls [path]", "List directory contents"),
            ("cat <path>", "Read a file"),
            ("write <path> <data>", "Write data to a file"),
            ("mkdir <path>", "Create a directory"),
            ("rm <path>", "Delete a file"),
            ("stat <path>", "Show file/dir metadata"),
            ("ps", "List scheduled tasks"),
            ("ai <query>", "Ask the AI Assistant"),
            ("qseed", "Generate quantum random seed"),
            ("ota", "Run OTA update check"),
            ("pkg <sub> [name]", "Package manager (install/remove/list/search/info)"),
            ("drivers <sub> [name]", "Driver manager (list/available/load/unload)"),
            ("sysinfo", "Show system information"),
            ("startx / gui", "Launch graphical UI shell"),
            ("help", "Show this help"),
            ("exit / quit", "Shutdown the OS"),
        ]
        for cmd, desc in cmds:
            print(f"  {Theme.BRIGHT_CYAN}{cmd:<22}{Theme.RESET}{desc}")

    def _cmd_exit(self, _args: str):
        print(Theme.styled("  Shutting down Umer OS...", Theme.SYSTEM_COLOR))
        self.running = False