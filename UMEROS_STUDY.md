# UmerOS — Detailed Study

**Subject:** `F:\Pension Person Details\UmerOS` (git branch `master`)
**Method:** static reading of ~1,860 source files + executed quality gates (pytest, coverage, `flutter analyze`, `flutter test`) on the live working tree.
**Date of study:** 2026-10-06

> **How to read the numbers.** Line counts below are *non-blank* lines (PowerShell `Measure-Object -Line`). Raw total lines are ~25–30 % higher. Everything marked **[verified]** was executed, not inferred.

---

## 1. What UmerOS actually is

UmerOS is **not an operating system**. It is a ~239 k-line Python research platform that *re-implements and simulates* operating-system concepts in user space, plus a Flutter desktop shell, plus a large amount of generated catalogue code.

The project's own README is unusually honest about this (`README.md:11`, `README.md:57`: *"most kernel facilities are user-space simulations/prototypes"*). The gap is not in the README's *reality boundary* paragraph — it is in the details: several flagship claims (a working scheduler, a zero-trust capability gate, bootable initramfs images, Qiskit-grade runtime, a Python interpreter UI) are either dead code, unwired, or mock.

Three distinct things live in this repository, and conflating them is the main source of confusion:

| Layer | What it is | Volume | Maturity |
| --- | --- | --- | --- |
| **A. Core system model** | `kernel/`, `boot/`, `core/`, `quantum/`, `ai/`, `security/`, `fs/`, `initrd/`, `network/`, `compatibility/`, `drivers/`, `virt/` | ~120 k LOC | Real algorithms surrounded by simulation; wiring is the weak point |
| **B. FHS userland emulation** | `bin/`, `sbin/`, `etc/`, `usr/`, `lib/`, `dev/`, `proc/`, `var/`, `srv/`, `opt/`, `media/`, `mnt/`, `root/`, `home/`, `tmp/`, `legal/`, `sources/`, `backup/` | ~110 k LOC | ~83 % machine-generated templates; largely unreachable from `main.py` |
| **C. Front-ends & process artifacts** | `ui/flutter_ui/` (Flutter), `ui/*.py` (legacy PyQt6), `tests/`, `.workbuddy-ai/memory/`, `MainTask/` | ~20 k LOC + docs | Flutter shell is real but the tree is currently red |

---

## 2. Scale, measured

**[verified]** Filtering out `node_modules`, `.git`, `build`, `dist`, `__pycache__`, `.pytest_cache`, `liboqs`, `__nope_backup__`:

- **1,859 files, 651.7 MB** (bulk is Flutter Windows build output and the vendored `liboqs` build tree)
- **849 Python files, 238,789 non-blank lines**
- **53 Dart files** in `ui/flutter_ui/lib`
- **128 Markdown files**; `liboqs/` alone is **11,611 files** (vendored Open Quantum Safe C library)
- `Old Linux Code/` — **exists but is empty (0 files)**. `MainTask/codex_project_context.md:49` describes a 93,684-file Linux 7.1.0 snapshot; it is gone. `.workbuddy-ai/memory/MEMORY.md:14` still lists it as "reference-only".

Largest Python packages by non-blank LOC:

```
29,235  drivers/       (75 files)   21,714  etc/        (81)
21,014  quantum/       (50)         20,181  usr/        (61)
18,905  tests/         (96)         16,349  bin/        (44)
15,770  compatibility/ (50)         10,394  lib/        (30)
10,319  boot/          (28)          9,264  kernel/     (38)
 7,277  dev/           (49)          6,168  srv/        (12)
 5,231  opt/           (15)          4,566  initrd/     (17)
 4,159  ui/            (7)           3,569  virt/       (15)
 2,617  ai/            (10)          2,439  security/   (14)
```

Note the inversion: `ai/` — the headline "AI-native" subsystem — is 2,617 lines and 10 files. `drivers/` and `etc/` are 20× larger.

---

## 3. The architectural template (why the code looks like it does)

Most of Layer B, and `drivers/`, were generated from a small number of templates. Recognising them makes the repo legible immediately.

**Template A — "FHS catalogue Command"** (`bin/`, ~190 classes)

```python
class NLSCommand(Command):            # bin/usr_share_nls.py:32
    name = "nls-dir"
    description = "Display /usr/share/nls - Native Language Support"
    category = "system"
    privileges = ["user"]

    def execute(self, args=None, stdin=None, stdout=None) -> int:   # annotation is a lie
        return ("/usr/share/nls:\n  Native Language Support catalogs\n")
```

Four class attributes plus a `execute()` that returns a **string literal**. Nothing ever prints it. Roughly 4,700 lines of descriptive text are unreachable documentation wearing a function signature.

**Template B — "Manager over dataclass catalogue"** (`etc/`, `usr/`, `lib/`, `opt/`, `var/`, `media/`, `mnt/`, `home/`, `root/`, `tmp/`, `legal/`, `sources/`)

GPL header → docstring citing an FHS section → `@dataclass` record with `to_line()`/`to_dict()` → module-level `DEFAULT_*` literal catalogue → `class XManager` with `_load()`/`_write()` → CRUD methods returning `{"success": bool, ...}` → optional `_selftest()`.

**Template C — "driver framework"** (`drivers/`, ~60 of 75 modules)

SCREAMING_CASE constant catalogue → `IntEnum`/`IntFlag` ID catalogue → `@dataclass` kernel-struct mirrors → module-level dict registry → one `*Manager`/`*Controller` class with simulated register read/write → `*_register()` helpers → print-only `__main__` demo.

**Consequence:** the codebase is internally consistent and easy to scan, but a large fraction of its mass is *data*, not *behaviour*, and the constants are frequently wrong (see §7.4).

---

## 4. The real startup path

`main.py` is 17 lines:

```python
from boot.init import boot
if __name__ == "__main__":
    boot()
```

`boot/init.py:82-86` → `Bootloader().display_waiver()` → `check_hardware()` → `asyncio.run(loader.load_kernel())` → `UmerKernel().boot()`.

**[verified]** The `AttributeError: 'UmerKernel' object has no attribute 'start'` bug recorded in `MainTask/codex_project_context.md:42` **no longer exists** — `async def boot()` is defined inside the class at `kernel/umer_kernel.py:931`. That context file (dated 2026-06-22) is stale on this and on three other points: it names `bootloader/` (now `boot/`), `filesystem/` (now `fs/`), and `ai/assistant.py` as the AI entry point (now `ai/umer_ai.py`).

Three live problems on this path:

1. **Non-interactive boot aborts by design.** `boot/init.py:55-67` fails closed unless stdin is a TTY or `--accept-eula` is passed. But `main.py:17` calls `boot()` with no arguments, and the flag is only parsed in `boot/init.py:91` under `if __name__ == "__main__"`. So `python main.py` **cannot** be run non-interactively (CI, containers, service managers), and if it *is* given the flag via `python -m boot.init`, `interactive=False` (`kernel/umer_kernel.py:1039`) means the shell never starts and the idle loop at `:1044` never exits — **the boot hangs forever**.
2. `lib.lostfound` is imported under `try/except` (`kernel/umer_kernel.py:62-71`) and *does* exist, but the failure path is silent — the whole fsck/`/lost+found` sequence (`:993-1007`) is skipped with no log if the import ever fails.
3. `kernel/umer_kernel.py:915` calls `self.taint.add("TAINT_KERNEL_PANIC")`, but `kernel/taint.py:55-64` defines no such flag and `add` raises `ValueError:104-105`. **The panic handler crashes instead of panicking.**

---

## 5. Subsystem verdicts

### 5.1 Kernel (`kernel/`, 9,264 LOC)

The real orchestration is `UmerKernel.__init__` (`:765-862`) and `boot()` (`:931-1050`). Around it:

- **`umer_kernel.py` is 1,943 lines, of which ~716 lines (`:1228-1943`) are a commented-out duplicate of the entire kernel** — 37 % of the file.
- The kernel **re-implements** `Task`/`HybridScheduler`/`AIResourceManager`/`AIFirewall`/`LocalAIAssistant` locally (`:77-192`) rather than importing the real ones. The local `HybridScheduler.add_task` is `self._tasks[task.pid] = task` — **the scheduler the kernel actually runs has no scoring and no `start()`**, so `kernel/scheduler.py`'s `HybridScheduler.start()` is never called by anything.
  - This makes the README's scheduling formula (`README.md:170`) *accurate but describing dead code*. `kernel/scheduler.py:141` really is `(sup * priority) / (cpu_time + EPSILON)`.
- Placeholders visible in the boot path: `AIFirewall` and `LocalAIAssistant` are `pass` (`:184-187`); `QFS` prints a hardcoded `{"compression_ratio": "90%"}` (`:190-192`); `DNSResolver`/`HTTPClient` are `pass` (`:546-547`); `VPNTunnel`, `UpdateManager`, `MockPackageManager`, `DriverManager`, `BuildTool` are `print`-only (`:548-565`).
- `AIResourceManager.predict_allocation` fabricates numbers with `random.uniform` (`:132`); `QuantumScheduler.execute_superposition` prints *"Tasks completed with Zero Error"* unconditionally (`:181`) and calls `time.sleep` inside async code (`:173,177`).

**Genuinely real primitives:** `ipc_bus.py` HMAC-SHA256 with `compare_digest` (`:98,110`); `kernel/scheduler.py` cooperative task lifecycle; `signals.py` bounded queue; `softirq.py` bitmask/priority drain; `sysctl.py` typed range-checked registry; `taint.py` monotonic bitmask; `pid_allocator.py` cyclic allocator.

**Weaknesses:** `memory_manager.free` ignores `pid` (`:161`) and the bump pointer never reuses freed space; `ipc_bus.try_receive` **skips verification entirely by design** (`:310-328`); the HMAC key is per-instance `os.urandom(32)` never exchanged, so only the same object can verify; `CapabilityManager.check()` is **never called** anywhere in the repo.

### 5.2 Boot (`boot/`, 10,319 LOC + C sources)

A genuine split between real parsers and fabrication:

- **Real byte parsing:** `efi_stub.py:232-330` (PE/COFF offsets correct), `bootloader.verify_kernel` SHA3-512 (`:188-205`), `initrd/cpio.py` newc writer reached via `initrd_manager.py:441-485`.
- **Wrong offsets:** `bzimage.py` reads `start_sys_seg` at 0x1f6 (spec 0x20c), `handover_offset` at 0x26c (0x264), `kernel_info_offset` at 0x270 (0x268), and reads `xloadflags` as u32 when it is u16. `microcode.py:132-140` uses a non-Intel header layout.
- **Fabrication:** `kernel_signing.SignatureVerifier.verify:258-276` returns **VALID for any file starting with `MZ`** — keys are never consulted. `kernel_image.create_sample_kernel:469-523` writes a fake vmlinuz (gzip magic + `urandom`). `efi_system.install_grub:687-693` writes **4,096 NUL bytes as `BOOTX64.EFI`** and reports success. `initrd_manager.verify_image:378` marks any existing file VALID.
- `boot/uefi_stub.c` self-declares non-functional, and `boot/init.py:73-75` honestly says so.

`boot/python_vm/` is a **from-scratch C Python interpreter**: real refcounted object model (`Objects/*.c`, ~139 entry points) and a real bytecode dispatch loop (`VM/vm.c:72-423`). But the compiler silently drops almost everything: only one-argument `print(...)`, `name = expr`, `import`, and `from x import y` compile (`Compiler/compiler.c:604-729`); comparisons and all jump opcodes are **never emitted** (`:478-588`), so `if`, `while`, functions, classes and lists do not work. Integers are 64-bit C longs with silent wraparound, and `long_power` is an O(exp) loop that hangs on `2**999999999`. **The compiled `umeros_python.exe` and the full CMake `build/` tree are committed to git.**

### 5.3 Quantum (`quantum/`, 21,014 LOC)

The strongest research package in the repo, with a clear line between real and mock:

- **Real:** `simulator.py` statevector (complex128), a full unitary gate set with a unitarity assertion (`gates.py:55-59`), a correct density-matrix path (`simulator.py:341-368`), correct `KrausChannel` (`info.py:227-240`), real BFS routing with SWAP insertion (`transpiler.py:297-329`), real REST clients for IBM/IonQ/Rigetti/Braket with tokens from env vars and **no hard-coded keys**, and a genuine liboqs wrapper (`crypto_pqc.py:144-182`).
- **Mock:** `ibm_runtime_service.py:161-183` — a class named `QiskitRuntimeService` whose `least_busy()` returns the string `"fake_brisbane"`, `run()` returns `job-0`, and `result()` returns empty — **exported from the package as the IBM runtime SDK** (`__init__.py:175-182`).
- **Broken:** BB84 `_measure_qubits` **discards the prepared circuit** and measures a blank one (`qkd.py:136-146`), so QBER is always ≈0.5 and an eavesdropper is always "detected". E91 discards its own measurement (`:325-331`). The transpiler's decomposition and optimisation passes can **never fire** because they compare lowercase gate names (`"swap"`, `"rz"`) against the uppercase `Gate.name` (`transpiler.py:216-278,404-419`).
- **Cost:** gate application materialises a full 2ⁿ×2ⁿ unitary per gate (`simulator.py:260-284`) — O(4ⁿ) memory, not the O(2ⁿ) the README implies. Practical ceiling is ~10–12 qubits, not the "~20" claimed in `backend.py:159`.
- Qiskit *is* declared in `requirements.txt:27-31` and `setup.py:105-106`, but is only imported lazily inside two methods (`backend.py:296,356`) and never at module scope. "Cirq" appears zero times in code.
- Duplicated stacks: two transpilers, two statevector engines, two error-mitigation libraries (`_v2` versions imported by nothing), two `ClassicalRegister` definitions.

### 5.4 AI (`ai/`, 2,617 LOC)

- **No machine learning.** Prediction is EWMA + least-squares slope with fixed weights (`umer_ai.py:242-284,399-410`). The only ML import, `onnxruntime` at `:516-517`, assigns `self._onnx_model` which is **never read**.
- Workload classification divides RSS bytes by 8 MiB (`:307`), so any process over 4.8 MiB is labelled `memory_bound`.
- **The kernel does not use this package at all** — `kernel/umer_kernel.py:1628` (`# from ai.umer_ai import ...`) is commented out, and the kernel defines its own `AIResourceManager`.
- Consent gating exists and is fail-closed by design (`ai/consent.py:95-103`, default-deny; atomic ledger writes). But the gate reads `provider.kind` (`assistant_service.py:167-172`), which **comes from user config** (`providers.py:543`) and is writable through `PATCH /api/ai/config` (`server.py:159-178`) — on a server with **no authentication on any route** and `allow_origins=["*"]` (`:61-67`). Relabelling OpenAI as `"local"` bypasses consent entirely; the built-in `custom` slot already defaults to `kind="local"` with an arbitrary `base_url`.
- `model_manager.py:60-91` downloads GGUF files from mutable HuggingFace `resolve/main` URLs with **no hash, signature, or commit pinning**, then loads them in-process via llama.cpp.

### 5.5 Security (`security/`, 2,439 LOC + `core/`)

- **`core/capability_gate.py` is fail-open in production.** `require()` raises only when a manager is wired; otherwise it logs `"PERMISSIVE: ... allowing"` (`:144-153`). `gate.wire(...)` is called **only from three test files**. `kernel/umer_kernel.py:783` builds a real `CapabilityManager` and never connects it — so ~70 `gate.require(...)` sites across the OS are warnings. This is documented as a deliberate trade-off in `.workbuddy-ai/memory/remediation_progress.md:48` ("permissive-when-unwired / fail-closed-when-wired so CLI/tests do not regress"), but it means the "zero-trust" claim is not in force.
- `security/sandbox.py` is a Python dict of PIDs with advisory checks — no namespaces, seccomp, cgroups or containers.
- `security/crypto_engine.py` is real AES-256-GCM with per-encrypt `os.urandom(12)` nonce and no hard-coded key — but it is **misnamed** "Post-Quantum", and `sign`/`verify` are HMAC-SHA512 reusing the encryption key.
- `security/tls_utils.py` verifies by default but exposes `strict=False` → `CERT_NONE` (`:102-104`), and `run_uvicorn_secure` defaults to `host="0.0.0.0"` (`:212`).
- `security/antivirus/api_server.py` is **dead code whose auth fix died with it**: `create_app()` returns `None` because the route registrations and `return app` are indented *inside* the auth middleware (`:126-171`).
- The AV signature database is fabricated: EICAR is real, but "WannaCry" is stored as a 64-hex **SHA-256 in the `md5=` field** so it can never match (`signatures.py:74`).
- **Ungated privileged path:** `srv/systemd_manager.py:1669` runs `subprocess.run(cmd, shell=True)` on `ExecStart=` strings parsed from unit files — no capability gate, no allow-list, and it violates the project's own H5 rule (list-form, no `shell=True`) recorded in `tests/test_host_subprocess_security.py:17-26`.

**Secrets:** `settings.local.json` is not valid JSON (it is an OpenRouter `fetch()` snippet), and its bearer value is the literal placeholder **`REDACTED-ROTATE-ME`** — the previously leaked key has been redacted. `.gitignore` covers it. `legal/consent.py:144-145` computes its "cryptographic" consent token as unkeyed SHA-256 over entirely public values, and `_load` never verifies it.

### 5.6 Storage, initrd, network, cloud, packages, installer

- **QFS (`fs/qfs.py`)** — genuine SHA3-256 content addressing (`:97`), dedup (`:99-101`), LZMA (`:229`), snapshots (`:579-598`). But whole-file blocks (**no chunking**), no persistence (`export`/`import_from` promised at `:420-421` do not exist), the XOR-delta stage is unreachable because `write_file` resets the compressor first (`:476`), and `restore_snapshot` leaves `self._indexer` stale (`:616-618`). "Quantum-inspired" is branding.
- **initrd (`initrd/`, 4,566 LOC)** — real 8-phase enum state machine (`phase_machine.py:69-127`), real archiver registry, 12 hook points, 6 scenarios. **But the CPIO writer/reader use the wrong newc padding rule** (`cpio.py:158,162` pad relative to each field; Linux `N_ALIGN` pads relative to the 110-byte record start), so a real kernel rejects the stream after the first entry, and `inspect` mis-reads genuine dracut images. `tests/test_initrd.py:163` locks the bug in. The images also contain no interpreter or binaries, so "bootable" (`initrd/README.md:24`) is false. `linuxrc.py:314` raises `NameError` (`RamDiskState` not imported).
- **network (`network/`, 1,292 LOC)** — the most genuinely working layer: real `asyncio.open_connection`, real `start_server`, real `getaddrinfo`, real aiohttp/urllib HTTP, real DoH JSON queries. mDNS and QoS are dictionaries; `vpn_tunnel.py` is honestly labelled a repeating-key-XOR simulation.
- **cloud (`cloud/`, 1,309 LOC)** — `compute.py` self-declares "no hypervisor, container runtime, network namespace, or disk image is created" (`:13-17`). OTA is "SIMULATED" (`update_system.py:17`) with a hardcoded manifest and a 28-byte constant "download"; its signature verification *is* genuinely fail-closed (`:276-291`) — which means `run_update_pipeline` can never succeed, since the canned manifest has no `signature` key.
- **packages (`packages/`, 905 LOC)** — the most shipping-ready subsystem: real Ed25519 verification over a full-payload SHA3-256 hash against a pinned trust store, fail-closed on missing signature/untrusted key, constant-time compares (`umer_pkg.py:390-477`), and a real transactional install with snapshot + rollback (`:529-598`). **But `setup.py:136` registers `umer-pkg=packages.umer_pkg:main` and `main()` does not exist** — the console script cannot run.
- **installer (`installer/`, 543 LOC)** — the `"I AGREE"` waiver is real and case-sensitive (`:259`), non-interactive denies (`:255-257`). It is bypassable via `run(consent_override=True)` (`:508-512`), nominally guarded by a permissive gate. Rollback is `shutil.rmtree(self._install_root)` (`:478`) — the backup JSON is never read (`:314-343`), so "fully restores the pre-installation state" is false. Two rival installers survive: `kernel/setup_umer_os.py` (accepts a single `Y`) and `tools/installer.py` (accepts bare ENTER, then `rmtree` into `/umer_os`).

### 5.7 Drivers (`drivers/`, 29,235 LOC — the largest package)

- **Zero live hardware access.** A package-wide grep for `ctypes|CDLL|mmap|os.open|/dev/|/sys/|ioctl|fcntl|socket|subprocess` returns 109 hits, **all** of which are docstrings, comments, string labels or local variable names. The only host I/O is `fpga.py:147-155` (a user-supplied `open()`) and `/proc` reads via the unrelated FastAPI service in `driver_service.py`.
- **`drivers/crypto.py` ships a silently broken AES.** `_AES_SBOX` at `:143-145` is corrupted from index 208 — line 144 repeats `0x5c`, so the table is **not a bijective S-box**. AES, AES-GCM, CBC, CTR and XTS therefore cannot produce standard ciphertext, while `_demo()` only prints booleans instead of checking known-answer vectors.
- **Constant catalogues are half-authentic.** Exact: PCI config offsets and ioport flags (`pci.py:35-90`), USB `bRequest`/descriptor types (`usb.py:78-94`), `I2C_M_*` (`i2c.py:44-47`), termios `CS8`/`CREAD`/`CLOCAL` (`tty.py:65-69`). Invented/shifted: `SPI_CPOL = 0x10` (kernel 0x02, and it collides with `SPI_3WIRE` on the next line), `IRQF_SHARED = 0x800` (kernel 0x80), the entire MTD type ladder (`mtd.py:35-42`), `GPIOF_PULL_UP`/`PULL_DOWN` (not kernel GPIO flags), `CRTSCTS = 0x0400` (that is HUPCL's value). ACPI table signatures, AML opcodes and MTD ioctl numbers are **absent entirely**.
- `device_tree.py` has **no FDT/DTB support** and its only function always raises `TypeError` — it passes `compatible=` to a `Device.__init__` that accepts only `(name, hardware_type, bus)` (`device_tree.py:37` vs `device.py:29`).
- `example_ioctl_driver.py:24` imports `from .ioctl import ...` and **`drivers/ioctl.py` does not exist**.
- The claimed H62 fix (tier labels on all 75 modules) is **not present** — a case-sensitive grep finds zero tier labels.
- Runtime reachability is **zero**: the only live import is `tests/test_driver_service.py:117`; `kernel/umer_kernel.py:1653` is commented out. The docs point at a `kernel.drivers.*` package that does not exist.

### 5.8 Compatibility & virtualisation

- **`compatibility/x86_runner.py` (1,549 lines)** is a **real** x86-64 interpreter: genuine ModRM/SIB/disp decoding including RIP-relative (`:311-381`), REX last-wins (`:437-441`), 16 GPRs plus flags, paged memory, thunk dispatch. But coverage is ~90 of 256 one-byte opcodes (<5 % of the ISA), **OF and PF are never computed** (`:1472-1485`), 8+ handlers retain the off-by-one the git commit fixed only for prefixes, and REX.W imm32 opcodes desync the stream.
- **`win32_runner.py` executes untrusted PE code with no safety model** beyond a caller-settable step cap, and its default import table wires guest IAT entries to **real host filesystem calls** — `CreateFileA`/`DeleteFileA`/`MoveFileA` (`win32_runner.py:143-145` → `win_kernel32.py:201-274`). No capability gate, no jail.
- **PE parsing is genuine** (COFF/optional-header/section/data-directory `struct` unpacking with bounds checks), but `pe_relocations.py` **never applies a relocation**, `pe_resources.py` resolves depth-≥2 offsets against the wrong base, and `pe_exports.py`/`pe_loader.py` let `struct.error` escape on malformed input.
- **`signed_pe.py` verifies nothing cryptographically** — no ASN.1, no PKCS#7, no digest — yet `WinVerifyTrust` returns `ERROR_SUCCESS` for any PKCS#7-typed blob, and its own shipped selftest proves a fabricated "Microsoft Corporation" certificate passes (`:364-403`).
- **`registry_hive.py` cannot parse a real hive**: it scans hbins in 4-byte steps ignoring cell sizes (`:274-287`), unpacks 15 struct fields into 18 names (`struct.error` on the first real key), `_parse_lf` ends in `pass` so nothing is linked, and `_parse_vk` is never called.
- **Win32 surface: 161 symbols, ~30 functional** out of ~5,000 real exports. Most return constants (`VirtualProtect`→True, `FindFirstFileExW`→-1). `MultiByteToWideChar` returns a length without writing the destination. `SetLastError` is one process-global slot, not per-thread. Handles are `id(obj) & 0xFFFFFFFF`.
- **`virt/kvm/` contains no ioctl numbers and never opens `/dev/kvm`.** `run_vcpu` says *"for simulation, we just return the run struct"* (`kvm_main.py:296-304`). It is a 263-function model of KVM kernel internals — useful as study scaffolding, not a port.
- Flutter's newest `virt_kvm_app.dart` (uncommitted, 1,241 lines) is the current work front and is what breaks the Flutter build (§6).

### 5.9 The FHS userland (`bin/`, `sbin/`, `usr/`, `lib/`, `etc/`, `dev/`, `proc/`, …)

The largest block, and the least reachable.

- **Real, working code:** `bin/essential_commands.py` (`cat`/`cp`/`mv`/`rm`/`ls` with real file I/O and POSIX return codes), `bin/permissions.py` (real symbolic-mode algebra, real `os.chmod`, `ls -l` formatting), `bin/process.py` (real `/proc/<pid>/stat` parsing with correct field offsets), `lib/elf_parser.py` (**genuine** ELF64/32 parsing with `DT_NEEDED`/`SONAME`/`RPATH` resolution), `lib/dynamic_linker.py` (a real `ldconfig`/`ld.so.cache` builder), `usr/man_page.py` (real roff directive parsing and page reading), `srv/systemd_manager.py` (a real `[Unit]/[Service]/[Install]` parser) and `etc/pam_config.py` (a real PAM stack tokeniser, including the bracketed control form).
- **Constants a reader would trust but which are wrong:** six of eight `SECCOMP_RET_*` action codes (`usr/seccomp.py:50-56`), `DT_SYMTAB`/`DT_SYMBOL` (`lib/elf_parser.py:83,86`), `cksum` implemented as a byte sum (`bin/usr_cmds.py:3198`).
- **Duplication:** `bin/usr_cmds.py` (3,226 lines) and `bin/usr_commands.py` (1,658) share **55 identical class names**; `bin/bin_manager.py` routes all 55 to the latter, so the former's copies are dead. `CksumCommand` and `DpkgCommand` are each **defined twice in one file** (`:870`/`:3187`, `:1257`/`:3210`) with the earlier silently shadowed. Three separate fstab implementations (2,366 lines for one file format) diverge exactly where correctness matters — only one is capability-gated.
- **`etc/` is 96 % ungated:** only 3 of 81 modules gate privileged writes, so `HostsManager()` with its default `base_path="/"` **writes the real `/etc/hosts`** (`etc/hosts.py:88,138,148`) with no gate and no guard. `media/mount_ops.py` shells out to real `mount(8)`/`umount(8)`; `mnt/mount_ops.py` only simulates.
- **`dev/` does not implement device numbers at all** — `dev/makedev.py:41-69` is a 25-entry literal table and `dev/core.py:92` delegates to the host's `os.makedev`.
- **`srv/yum_manager.py:582` reads `.repo` files with `json.loads`** — the extension imitates DNF, the format is JSON.
- **`etc/sudoers.py` has no parser at all** — it is a writer that regenerates the whole file (`:174-188`), destroying directives it did not produce.
- **Runtime reachability: essentially zero.** Grepping the whole repo for imports of `bin`/`sbin`/`usr`/`lib` finds exactly one non-test consumer: `kernel/umer_kernel.py:62-71` → `lib.lostfound`. The live shell is `kernel/shell_commands.py` (2,030 lines, ~200 commands) with an incompatible `execute(ctx, args)` signature — and it **fabricates hardware output** (lspci, lsusb, lshw, dmidecode, hdparm, "Found 0 bad blocks").

### 5.10 UI (`ui/`)

- **Flutter (`ui/flutter_ui/`, 53 Dart files)** is genuinely the canonical shell. `main.dart` matches the README exactly. `ai_service.dart` really calls `http://127.0.0.1:8421` with real `HttpClient` requests, timeouts and typed models; `quantum_service.dart` really calls `http://localhost:8420` — both matching the Python servers (`ai/server.py:55`, `quantum/quantum_server.py:552`).
- Honesty is mixed: `ai_assistant_app.dart:4` states "No simulated data: offline or error", and `data_source_badge.dart` exists to label provenance — but `network_manager_app.dart:23` hardcodes a fake `lo` interface list and `package_manager_app.dart:38` hardcodes `_packages`. `quantum_service.dart:409` hardcodes `fidelityEstimate: 0.95` even though the model parses a real value from JSON.
- **Legacy Python UI:** `ui/umeros_gui.py` (1,847 lines) and `ui/launch_gui.py` (1,363) are **PyQt6**, not Kivy as `docs/architecture.md` claims. Not imported by anything.

---

## 6. Live quality gates — [verified] on this machine

Environment: **Python 3.14.6**, pytest 9.1.1, Flutter/Dart present at `C:\src\flutter\bin`. The project declares `requires-python = ">=3.12"`; only 3.14 is installed here.

### Python test suite

```
python -m pytest tests/ -q        →  4 failed, 2267 passed, 56 skipped in 60.50s
                                        (2327 collected)
```

**Read the four failures carefully — two are real bugs, not environment noise:**

| Failure | Diagnosis |
| --- | --- |
| `test_boot_init.py::test_matching_hash_accepted` | **Real bug.** The test computes `hashlib.sha3_256(data)` (64 hex chars) at `test_boot_init.py:140`, but `verify_kernel` uses `hashlib.sha3_512()` (`boot/bootloader.py:188`) and compares against 128 hex chars. Fails on every platform. |
| `test_grub_cli.py::test_parse_grub_cfg` | **Real bug.** The test passes the repo root (`:14-15`); `parse_grub_cfg` looks for `<root>/boot/grub.cfg` (`backup/grub_cli.py:93`), but the fixture lives at `tests/grub.cfg`. Fails on every platform. |
| `test_bin.py::TestSelfTest::test_permissions_selftest` | POSIX-only: `bin/permissions.py:758` calls `pwd.getpwnam`, unavailable on Windows. |
| `test_dev_manager.py::test_sync_to_filesystem_refuses_escaping_node` | Expects a WARNING log that is not emitted on this host. |

### Coverage [verified]

```
--cov=. --cov-report=term   →   TOTAL  120178 statements, 73324 missed, 39%
```

The README/`pyproject.toml` floor of 30 % is met with headroom (the CI comment claims 36 % measured 2026-08-26). Packages with essentially no coverage despite their size: `drivers/`, `usr/`, `bin/` (beyond `essential_commands`/`permissions`), `feedback/`, `sdk/`, `scripts/`, `examples/`.

### Flutter gates [verified]

```
flutter analyze  →  2 errors, 4 warnings, 4 infos
flutter test     →  39 passed, 3 test files FAILED TO COMPILE
```

Both errors are in the current uncommitted work-in-progress on the virt/KVM app:

- `virt_kvm_app.dart:1088` — `error - The getter 'chip' isn't defined for the type 'Icons'`
- `kvm_service.dart:161` — `error - Can't define a const constructor for a class with non-final fields` (`IRQBypassPeer`, field `bool connected`)

`git status` confirms these are the two newest, uncommitted files. **The Flutter side of the repo does not currently build.**

### CI is inert

`.github/workflows/ci.yml:7-9` triggers on `push`/`pull_request` to **`main`**. `git rev-parse --abbrev-ref HEAD` → **`master`**. **CI has never run on this repository's actual branch.** Separately, `ruff`, `mypy` and `pre-commit` jobs are all `continue-on-error: true` (admitted at `ci.yml:67,85,112` and in `README.md:445`), so only `test` and `doc-drift` actually gate.

### Repository hygiene

- `boot/python_vm/build/**` — CMake cache, `.obj` files, `.ninja_log`, `CMakeCCompilerId.exe` — is **committed to git**.
- `requirements.txt` is properly bounded (`>=x,<y`) and includes qiskit, cirq, `liboqs-python`, `llama-cpp-python`.
- 10 scratch/debug files committed in `tests/` (`_dbg_path*.py`, `_dbg_unc*.py`, `_t.py`, `_envdbg.py`, `_mmap_trace.py`, `_unused_trace.py`, `_pe_test.py`, `fix_h40_tier_labels.py`) — none match `test_*.py`, so pytest does not collect them.
- `.gitignore` contains a literal Windows path pattern (`F:\Pension Person Details\UmerOS\Old Linux Code/`) — a broken pattern.
- In-package test files (`legal/test_legal.py`, `srv/test_srv.py`, `opt/test_opt.py`, `tmp/test_tmp.py`, `sources/test_sources.py`) use custom `-> bool` runners, and because their functions are named `test_*` **pytest collects them but ignores return values** — they can never fail.

---

## 7. Documentation vs reality (drift audit)

The README is far more careful than most projects of this kind. These specific claims still do not hold:

| Claim | Reality |
| --- | --- |
| `README.md:459-478` kernel example: `UmerKernel(total_memory_bytes=...)`, `.init()`, `.spawn_process()`, `.inject_ai_manager()`, `.main_loop()`, `.kill_process()`, `.list_processes()` | **None of these exist.** `UmerKernel.__init__(self)` takes no arguments (`kernel/umer_kernel.py:765`); the method list is `__init__`, `request_shutdown`, `_register_default_sysctls`, `panic`, `boot`, `run_loop`, `uptime`, `status`, `shutdown`, `start_gui_shell`. `scripts/check_readme_drift.py` passes it because it only verifies the *module* exists, never the symbols. |
| `README.md:200` names `quantum/statevector.py` | No such file; the class is `Statevector` in `simulator.py:44`. |
| `README.md:283` sdk "re-exports … kernel, quantum, AI and UI entry points" | `sdk/__init__.py:41-45` exports exactly two names: `UmerApp`, `BuildTool`. |
| `README.md:167-173,184` scheduling model as the live model | Accurate for `kernel/scheduler.py` — which is **never started**. The live scheduler is the 20-line stub in `umer_kernel.py:94-113`. |
| `README.md:215-220` "`ai/` package is local-first by design" | Describes a package the kernel does not import (`umer_kernel.py:1628` is commented out). |
| `README.md:545-555` security guidance ("zero-trust") | The capability gate is fail-open (§5.5); `srv/systemd_manager.py:1669` has an ungated `shell=True` path. |
| `README.md:287-316` repository map lists ~800 LOC for `fs/` etc. | Broadly correct on structure, but omits `bin/`, `lib/`, `usr/`, `etc/`, `dev/`, `proc/` — which are ~45 % of the Python code. |

**`docs/` is substantially stale.** `docs/api_reference.md:7-18` documents `from sdk.kernel_api import UmerKernel, Task, HybridScheduler` and three sibling modules — **none of `sdk/kernel_api.py`, `sdk/quantum_api.py`, `sdk/ai_api.py`, `sdk/ui_toolkit.py` exist.** `docs/architecture.md` describes a Kivy UI, a `test_quantum_extra.py` suite, a `test_drivers.py` suite, and "431 tests passing" (there are 2,327). `docs/driver_writing_guide.md:8,53` imports `kernel.drivers.base_driver`, a package that does not exist. `tests/README.md` still advertises "HAL C stub + ctypes binding" and `make build`.

**The README's *reality boundary* paragraph, the TODAY/EXPERIMENTAL/FUTURE/BLOCKED tiers, `docs/HARDWARE_REQUIREMENTS.md`, and `docs/user_manual.md` are the trustworthy parts.** Note that the tier labels are applied inconsistently: `drivers/` has **zero** tier labels despite the convention being enforced elsewhere, and several `[TODAY]` labels sit on files whose entire body returns a descriptive string.

---

## 8. The development process (important context)

This repository is being driven by an **AI-assisted, human-in-the-loop remediation loop**, and that explains its structure more than any architectural decision:

- `MainTask/Raw Data/Code Review Standards and Process.md` (625 lines, 355 KB, **v1.43**) defines **307 hotspots**: 66 RED blockers, 152 YELLOW suggestions, 89 BLUE nits (H1–H307).
- `.workbuddy-ai/memory/remediation_progress.md` (548 lines) is the single source of fix status; `.workbuddy-ai/memory/MEMORY.md` holds conventions and a per-package colour map. ~90 dated session logs sit beside them.
- **All 66 RED blockers are closed** (sessions 1–33): path-traversal (CWE-22), fail-open checks, dummy crypto, and the capability-gate wiring cluster.
- The YELLOW sweep is at **session 78**, currently working `drivers/` (H66).
- Every applied fix carries an inline `# [FIX Hxxx]` comment — which is why the source is littered with them.

The recurring convention *"drift-recon first: always verify the standard's premise against live repo state — many H premises are stale/overstated"* is the single most important thing to adopt if you continue this work: several remediation items were closed on the grounds that the original premise was already false.

**Two consequences of this process worth flagging:**

1. The "permissive-when-unwired / fail-closed-when-wired" capability-gate pattern was chosen deliberately to avoid regressing CLI and tests — but it means the security model is decorative in production. The H-item is closed; the risk is open.
2. Fixes are recorded in six bookkeeping surfaces (checkpoint, standard §9 row, MEMORY pointer, daily log, session overview, and the code comment). Documentation *about* the process is now comparable in volume to the code it governs.

---

## 9. Health assessment

**Genuinely good, keep and build on:**

1. `tests/` — 2,327 real tests with genuine fail-closed assertions and module-level gate patching (`tests/test_cap_gate.py` is a good example). 39 % coverage of 120 k statements. This is the project's strongest asset.
2. `core/path_guard.py` — a correct, genuinely-used CWE-22 guard.
3. `quantum/` core — real statevector/density-matrix simulation, correct Kraus math, a working gate set, real provider REST clients.
4. `packages/umer_pkg.py` — real Ed25519 trust chain with a transactional install and rollback. One line from being usable.
5. `network/` — real sockets, real DNS, real HTTP.
6. `compatibility/x86_runner.py` + `pe_loader.py` — a real (if small) x86-64 interpreter and a real PE parser.
7. `lib/elf_parser.py`, `srv/systemd_manager.py`, `etc/pam_config.py` — real parsers.
8. The README's honesty about scope.

**The five things that most limit the project:**

1. **Nothing from Layer B is reachable from `main.py`.** ~110 k lines of userland have exactly one non-test consumer. The live shell is a different subsystem with an incompatible interface.
2. **The security model is fail-open in practice.** The gate is unwired, `CapabilityManager.check()` is never called, `try_receive` skips IPC verification, `signed_pe` accepts any `MZ` file, and `srv/systemd_manager.py:1669` is an ungated `shell=True` path.
3. **Flagship simulators are demos wearing production names:** `QiskitRuntimeService` returning `"fake_brisbane"`, BB84 measuring a blank circuit, a fake vmlinuz, a 4 KiB NUL `BOOTX64.EFI`, `virtualenv`-style stubs returning success constants.
4. **Silently wrong constants and algorithms** in code a reader would trust: `drivers/crypto.py`'s non-bijective AES S-box, six wrong `SECCOMP_RET_*` codes, wrong ELF `DT_*` numbers, a byte-sum `cksum`, wrong `bzImage`/microcode header offsets.
5. **The whole tree is red right now:** 4 Python tests fail (2 for real), `flutter analyze` has 2 errors, 3 Flutter test files do not compile, and CI has never run because it targets `main` while the branch is `master`.

---

## 10. Suggested next actions (highest leverage first)

> **Status (2026-10-06):** items **2, 4, 5, 7 and 9 are done** — see §11.
> Items 1, 3, 6, 8 and 10 remain open.

1. **Make CI actually run:** change `.github/workflows/ci.yml:7-9` branches from `main` to `master`. Nothing else you fix will be protected until this is done.
2. **Fix the four failing tests** — two are one-line source/test mismatches (`sha3_256`→`sha3_512` in `test_boot_init.py:140`; point `test_grub_cli.py:14` at `tests/` or move the fixture to `boot/grub.cfg`).
3. **Unbreak the Flutter tree:** `Icons.chip` → an existing icon in `virt_kvm_app.dart:1088`, and drop `const` (or make `connected` final) at `kvm_service.dart:159-161`.
4. **Wire the capability gate:** call `gate.wire(kernel.capabilities)` in `UmerKernel.__init__` and reconsider the permissive default. This single change activates ~70 enforcement points.
5. **Decide the future of Layer B.** Either wire `bin`/`usr`/`etc` into the shell (large, requires interface unification) or mark it explicitly as a non-executable reference corpus. Leaving 110 k unreachable lines labelled `[TODAY]` is the project's biggest credibility risk.
6. **Delete or fix the misleading simulators** — at minimum rename `QiskitRuntimeService`, make `signed_pe.WinVerifyTrust` return "not verified", and stop `boot` reporting success for fabricated images.
7. **Fix `setup.py:136`** (`umer-pkg=packages.umer_pkg:main`) — either add `main()` or remove the entry point.
8. **Un-track `boot/python_vm/build/`** and add it to `.gitignore`.
9. **Repair the CPIO padding rule** in `initrd/cpio.py` (and its test) if initramfs interoperability matters.
10. **Reconcile the docs with the code:** update `docs/api_reference.md` and `docs/architecture.md` to the real API surface, or delete them — right now they teach an API that does not exist.

---

## 11. Remediation applied — 2026-10-06

Five of the actions above were implemented and verified. **Full suite: 2,308 passed,
56 skipped, 0 failed** (was 4 failed / 2,267 passed). No pre-existing test was
weakened; every fix is covered by a new or strengthened test.

### Action 2 — the four failing tests

| Test | Root cause | Fix |
| --- | --- | --- |
| `test_boot_init.py::test_matching_hash_accepted` | Test hashed with SHA3-256; `verify_kernel` uses SHA3-512 (`boot/bootloader.py:188`). Failed on every platform. | Test now uses `sha3_512`. |
| `test_grub_cli.py::test_parse_grub_cfg` | `parse_grub_cfg(root)` looks for `<root>/boot/grub.cfg`; the fixture lives at `tests/grub.cfg`. Failed on every platform. | Test stages the fixture into `tmp_path/boot/grub.cfg`, so it is hermetic and no misleading `boot/grub.cfg` is added to the repo. |
| `test_bin.py::TestSelfTest::test_permissions_selftest` | **Cross-test contamination:** `test_bin.py` injected an empty stub `pwd` module into `sys.modules` and never removed it, so `bin/permissions.py` did `import pwd` successfully but found no `getpwnam`. | Stubs are now API-complete (raise `KeyError` like the real modules), and `bin/permissions.py` gained a `_posix_lookup()` helper that tolerates an absent or API-less `pwd`/`grp`. |
| `test_dev_manager.py::test_sync_to_filesystem_refuses_escaping_node` | **Cross-test contamination:** `tests/test_kernel_security.py` called `logging.disable(logging.CRITICAL)` at module scope. pytest imports all modules during *collection*, so logging was suppressed for the entire session and `assertLogs` saw nothing. | Scoped to `setUpModule`/`tearDownModule` with save/restore. |

### Action 4 — the capability gate is now wired

- `core/capability_gate.py`: added an explicit **principal** (`wire(cm, principal=PID)`), `snapshot()`/`restore()`, and a `UMEROS_STRICT_GATE=1` environment override that makes fail-closed the process default for hardened deployments.
- `kernel/umer_kernel.py`: `UmerKernel.__init__` now calls `gate.wire(self.capabilities, principal=SYSTEM_PID)`; `shutdown()` gained a Phase 6 that restores the pre-boot posture, so a boot/shutdown cycle cannot leak a fail-closed state into the process.
- **Concrete effect:** `gate.enforcing` was permanently `False`, which silently disabled two real defences that key off it — the SSRF destination filter (`network/http_client.py:314`) and the unsandboxed-container refusal (`compatibility/container_engine.py:164`). Both now activate inside a booted kernel, and a non-principal identity is denied by default.
- **Honest scope:** the kernel principal is privileged by construction, so this does not make the kernel's own library calls fail. Per-task principal separation (so a service running as PID_INIT is genuinely denied `sys.admin`) remains future work.
- `tests/conftest.py` (new): autouse fixture that snapshots/restores the capability gate and the package trust store around every test, so this class of leak cannot recur.

### Action 5 — Layer B is now declared, not implied

Decision: **declare the reference corpus explicitly** rather than attempt to wire it. Wiring would require unifying four incompatible `Command.execute` contracts across ~230 modules — months of work that would not make any single feature better. The credibility risk was the labelling.

- `docs/reference_corpus.md` (new) — authoritative record with the measured evidence and the promotion procedure.
- `scripts/check_layer_reachability.py` (new) — recomputes the reachable set from `main.py` by static AST analysis and fails if a declared non-executable package becomes reachable, or loses its marker. Wired into CI.
- **Measured result: only `boot`, `core`, `kernel` and `lib` are reachable.** 31 packages are reference corpus.
- All 31 reference packages now carry `# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md` in their `__init__.py` (applied idempotently by `scripts/mark_reference_packages.py`, verified by the checker and by `tests/test_layer_reachability.py`).
- `README.md` repository map now labels every entry `[LIVE]` or `[REF]`, and the newcomers list starts with the classification.

### Action 7 — `umer-pkg` works

- `packages/umer_pkg.py`: implemented the missing `main()` (argparse CLI: `install`, `remove`, `update`, `search`, `info`, `list`, `verify`, `stats`, `build`, `--json`, isolated `--install-dir/--registry-dir/--cache-dir`), returning POSIX exit codes.
- **Latent bug found and fixed:** `remove()` called `Path(...)` at lines 621-622 but `pathlib.Path` was never imported — so uninstalling any package whose directory existed raised `NameError`. The existing suite never exercised that path.
- `tests/test_umer_pkg_cli.py` (new, 12 tests): proves the entry point `setup.py` registers actually resolves, exercises exit codes, and drives a full signed **build → verify → install → list → info → remove** cycle against a throwaway Ed25519 signer, plus an unsigned-refusal test.

### Action 9 — CPIO is now kernel-valid

- `initrd/cpio.py`: the name field was padded relative to itself; the newc format pads the **whole record**, whose 110-byte header makes the offset `110 % 4 == 2`. Every record was therefore two bytes short and a real kernel would reject the stream after the first entry. Added `_name_padding()` using Linux's `N_ALIGN` rule and used it in both the writer and the reader.
- **Verified against an independent oracle:** the writer's output is now **byte-identical** to a reference archive constructed by hand from `#define N_ALIGN(len) ((((len) + 1) & ~3) + 2)`, and the reader correctly parses that reference archive.
- **Second latent bug found:** `CpioEntry.mode` defaulted to `0o644` without file-type bits, so `CpioEntry(name=..., data=...)` was silently written as a zero-length payload. The default is now a regular-file mode.
- `tests/test_initrd.py`: the old round-trip test (which enshrined the bug) is joined by tests that assert the 4-byte record-alignment invariant directly, the trailer's 124-byte length, and that a bare entry keeps its data.

### Additional fatal bugs found on the primary entry point

While verifying that the kernel changes did not break boot, `python main.py` was found to **crash on every run** — two consecutive defects that no test covered because nothing exercised `UmerKernel.boot()` end-to-end:

1. `kernel/umer_kernel.py` — `self.vfs.mkdir("/tmp")` raised `FileExistsError`, because `VirtualFileSystem.__init__` already pre-populates `/tmp`. Fixed by using the idempotent `parents=True` form (which the constructor itself uses).
2. `kernel/umer_kernel.py` — `self.crypto.decrypt(nonce, ciphertext)` passed two arguments to a method that unpacks `(nonce, ciphertext)` from **one**. Fixed to `decrypt((nonce, ciphertext))`.

`tests/test_boot_smoke.py` (new) now runs the real entry point in a subprocess and asserts a clean exit plus ordered boot checkpoints, and separately asserts the gate is wired during the kernel's life and released after shutdown. It was confirmed by hand: boot now reaches the shell and exits 0.

*Note: the study's earlier claim that non-interactive boot hangs is wrong for the redirected-stdin case — the shell receives EOF and shuts down cleanly. It remains true that `main.py` cannot forward `--accept-eula`.*

### Still open

1. **CI branch trigger** (`main` vs `master`) — one line, and the highest-leverage remaining item.
2. **Flutter tree** — `flutter analyze` still reports 2 errors in the in-progress virt/KVM app.
3. **Misleading simulators** (`QiskitRuntimeService`, `signed_pe.WinVerifyTrust`, fabricated boot artifacts).
4. **Un-track `boot/python_vm/build/`.**
5. **Reconcile `docs/api_reference.md` / `docs/architecture.md`** — they still document an API that does not exist.
6. **`network/vpn_tunnel.receive()`** discards the nonce that `send()` drops, so `self.crypto.decrypt(ciphertext)` cannot satisfy the tuple-shaped API. Unreachable today (the boot path only calls `send`), but latent.

---

## Appendix — quick reference

| Item | Value |
| --- | --- |
| Python files / non-blank LOC | 849 / 238,789 |
| Dart files (`flutter_ui/lib`) | 53 |
| Tests collected / result | 2,364 / **2,308 passed, 56 skipped, 0 failed** |
| Coverage | 39 % of 120,178 statements |
| `flutter analyze` / `flutter test` | 2 errors, 4 warnings / 39 passed, 3 files fail to compile |
| Default branch / CI trigger | `master` / `main` → **CI never runs** |
| Boot entry | `main.py` → `boot.init.boot()` → `UmerKernel.boot()` — **[verified working, exit 0]** |
| Live runtime | `boot`, `core`, `kernel`, `lib` only (see `docs/reference_corpus.md`) |
| Service ports | AI `127.0.0.1:8421` (`UMEROS_AI_PORT`), quantum `:8420` |
| Declared Python | `>=3.12` (host has 3.14.6 only) |
| License | GPL-3.0-or-later |
| Vendored trees | `liboqs/` (11,611 files), `Old Linux Code/` (**empty**) |
| Remediation standard | 307 hotspots, 66 RED all closed, YELLOW sweep at session 78 |
