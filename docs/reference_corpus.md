# UmerOS Layer Classification — Live Runtime vs. Reference Corpus

**Status:** authoritative · **Enforced by:** [`scripts/check_layer_reachability.py`](../scripts/check_layer_reachability.py) · **Decided:** 2026-10-06

---

## 1. The decision

UmerOS contains ~239 k lines of Python. A reader could previously be forgiven for
believing all of it runs. It does not.

**Only four packages are reachable from the boot path.** Everything else is
reference corpus: a large, largely template-generated body of code that is
exercised by its own unit tests and by nothing else.

We are **declaring that split explicitly** rather than attempting to wire the
corpus into the runtime. Wiring it would require unifying four mutually
incompatible `Command.execute` contracts across ~230 modules and replacing the
kernel's live shell registry — a multi-month project that would not, on its own,
make any single feature work better. The credibility problem is the *labelling*,
and that is fixable now.

---

## 2. The evidence

Measured by static import-graph analysis from `main.py` (nothing is executed):

```
$ python scripts/check_layer_reachability.py
entry point            : main.py
reachable packages     : 4
  boot core kernel lib
reference-corpus pkgs  : 31
  ai backup bin cloud compatibility dev drivers etc feedback fs home initrd
  installer legal media mnt network opt proc quantum root sbin sdk security
  sources srv tmp ui usr var virt
OK: no package declared non-executable is reachable from main.py.
```

The boot path is:

```
main.py
  └── boot.init.boot()
        └── kernel.umer_kernel.UmerKernel
              ├── kernel.{pid_allocator, taint, sysctl, panic, signals, cgroup,
              │          audit, workqueue, cred, reboot, resource, softirq,
              │          memory_manager, ipc_bus, capability_manager}
              ├── core.capability_gate            (H113 wiring)
              └── lib.lostfound                   (fsck / lost+found)
```

Plus `kernel/shell_commands.py`, which is the *live* interactive shell
(`execute(ctx, args)`), and which is a different implementation from
`bin/bin_manager.py` (reachable only from tests).

---

## 3. What each layer is

### Live runtime — `boot/`, `core/`, `kernel/`, `lib/`

Executed by `python main.py`. This is the only code whose behaviour a user
actually experiences. Its maturity labels remain
**TODAY / EXPERIMENTAL / FUTURE / BLOCKED** as before.

### Reference corpus — the other 31 packages

Not reachable from `main.py`. Two distinct sub-populations, and it is important
not to tar them with one brush:

| Sub-population | Packages | What it really is |
| --- | --- | --- |
| **FHS userland emulation** | `bin`, `sbin`, `usr`, `etc`, `dev`, `lib`*, `proc`, `var`, `srv`, `opt`, `media`, `mnt`, `root`, `home`, `tmp`, `legal`, `sources`, `backup`, `feedback` | ~110 k lines modelling a Linux userland in Python. ~83 % is generated from one of two templates; a minority is genuinely good code (see §4). |
| **Research & service corpora** | `quantum`, `ai`, `security`, `network`, `cloud`, `fs`, `initrd`, `compatibility`, `virt`, `drivers`, `installer`, `packages`†, `sdk`, `ui` | Self-contained research packages and pre-Flutter front-ends. Many have real algorithms and their own test suites, but nothing on the boot path imports them. |
| **Script directories** | `examples`, `tools` | Plain scripts, not importable packages. |

\* `lib` is partially live: `lib/lostfound` **is** reachable via the kernel; the
rest of `lib/` is not.
† `packages` is reachable from the `umer-pkg` console script, not from `main.py`.

---

## 4. What "reference corpus" does *not* mean

It does not mean worthless. Several corpus modules are the best engineering in
the repository:

- `lib/elf_parser.py` — genuine ELF32/64 header, section and `.dynamic` parsing
  with `DT_NEEDED` / `DT_SONAME` / `DT_RUNPATH` resolution.
- `srv/systemd_manager.py` — a real `[Unit]` / `[Service]` / `[Install]` parser.
- `etc/pam_config.py` — a real PAM stack tokeniser including the bracketed
  control form.
- `bin/essential_commands.py`, `bin/permissions.py`, `bin/process.py` — working
  file, permission and `/proc/<pid>/stat` handling.
- `compatibility/x86_runner.py` + `pe_loader.py` — a real (small) x86-64
  interpreter and a real PE parser.

It means: **nothing on the boot path executes it**, so its presence is not
evidence that a feature works.

---

## 5. How the classification is kept honest

`scripts/check_layer_reachability.py` recomputes the reachable set from
`main.py` and fails (exit 1) if:

1. a package declared reference becomes reachable — the doc and this file must
   then be updated; or
2. a declared package no longer exists or is not importable.

It is intended to be run in CI alongside `scripts/check_readme_drift.py`.

Every reference package also carries a marker in its `__init__.py`:

```python
# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md
```

`[REFERENCE-ONLY]` is a **reachability** classification and is orthogonal to the
**maturity** tiers (`TODAY` / `EXPERIMENTAL` / `FUTURE` / `BLOCKED`). A module can
be `[REFERENCE-ONLY]` *and* `[TODAY]`: it is finished code that nothing runs.

---

## 6. Promoting a package to the live runtime

To move a package out of the reference corpus:

1. Make `main.py` (or something it reaches) import it — not its tests.
2. Unify its command/manager interface with the live contract. For the FHS
   packages this is the blocker: `core/command.py` declares
   `execute(args=None) -> int`, while `kernel/shell_commands.py` declares
   `execute(ctx, args)` and `bin/shell.py` returns a `Tuple[int, str]`.
3. Add it to `LIVE` in the checker and remove it from `REFERENCE`.
4. Update the repository map in `README.md` and this file.

Until step 1 is done for a package, treat every capability it claims as
*designed*, not *delivered*.

---

## 7. Consequences for documentation

- `README.md`'s subsystem descriptions describe **design intent** for corpus
  packages and **behaviour** for live ones. The repository map has been updated
  to say which is which.
- Existing `docs/*.md` files that present corpus APIs as working entry points
  (notably `docs/api_reference.md` and `docs/architecture.md`) should be read
  against this classification.
