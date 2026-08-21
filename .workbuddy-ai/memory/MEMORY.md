# UmerOS — Long-term Project Memory

## Standing working conventions (Code Review Expert / Kim)
- **Review-standard-first workflow:** After *every* study (file/folder/design/dependency), update `MainTask/Raw Data/Code Review Standards and Process.md` — bump version, fold findings into §1/§4/§7/§9/§11. Standing user instruction; do not treat studies as read-only.
- **Authoritative sources (priority):** `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + `LICENSE`/`setup.py` (repo wins when a source is aspirational, e.g. README "Project Structure").

## Decided inconsistencies
- **H7 → GPL-3.0 canonical.** Sweep Apache-2.0 strays in prompts/docs/code to GPLv3.
- **H11 → Flutter (Dart) canonical frontend.** Backend = Python only. Drop `kivy` from `requirements.txt`; `ui/*.py` (Tkinter/CLI) is retired legacy (H25). UI MUST follow HCI (Nielsen 10) — §4.8.

## Folder scope map (studied 1→kernel; full detail in the standard)
- `boot/` = `/boot` mgmt toolkit (FHS/GRUB/EFI/SB). 🔴 H27 verify_kernel trusts missing, H28 is_binary_trusted trusts DISABLED, H29 init auto-accepts waiver. +H30–H34.
- `bin/` = ~44 FHS user cmd modules (19k LOC). H6/H35 wrong exec sig (27/44); 🔴 H37 LoginCommand -f auth bypass. H36/H38/H39/H40. Subprocess injection-safe.
- `build/` = PyInstaller output; only `.spec` reviewable → 🔴 H42 unsigned (codesign=None); H41 ships Tkinter not Flutter. H43–H45.
- `cloud/` = OTA updater. 🔴 H46 verify_and_apply fail-open (no real verify). H47–H49.
- `compatibility/` = foreign-OS app layer. 🔴 H51 ZeroTrustContainer fail-open gate; H50/H52/H53/H54. Best tier-labels.
- `core/` = base `Command` class. H55 fix exec sig (ROOT of H6/H35); H56 privileges unenforced; H57.
- `dev/` = ~43 `/dev` node modules. 🟡 H60 os.mknod no cap gate; H59 0o666 default; H58/H61. Cleanest folder.
- `drivers/` = 75 driver modules (~35k LOC). 🔴 H64 driver_service static JWT "test-secret" + unauth /metrics; 🟡 H66 no cap gate MMIO/PCI/crypto. H62/H63/H69.
- `etc/` = 81 `/etc` cfg modules (24k LOC). 🔴 H73 sudoers no cap gate + NOPASSWD; 🟡 H72 pam permit non-blocking. H70/H71.
- `examples/` = 2 demo modules (62 LOC). 💭 H74/H75 (teaches open pattern).
- `feedback/` = BROKEN pkg (imports missing modules). 🟡 H76/H77/H78/H79.
- `fs/` = VFS over QFS CAS. 🟡 H80 no cap gate; H81 Apache stray; H82. First tier-label folder.
- `home/` = `/home` subsystem (10 files). 🔴 H83 tar extractall no filter; 🟡 H84 path-traversal username; H85/H86/H87/H88.
- `HostFiles/` = 3 text assets. 🟡 H90 HostBridge host write + auto-open (legacy H25); H89.
- `initrd/` = 17 early-boot modules (5k LOC, best baseline). 🔴 H91 eval(); H92 no cap gate boot ops; H93 cpio traversal; H94/H95/H96/H97.
- `installer/` = 3 files. 🔴 H98 double UmerInstaller; H99 waiver fail-open; H101 rollback rmtree; H100/H102–H109.
- `kernel/` = 40-file microkernel (~10k LOC). Two tiers: strong baseline cluster + off-baseline toy/REPL cluster. 🔴 H110 no-op placeholders → zero-trust/IPC/mem INERT (real modules commented out L1569-71); H111 dummy CryptoEngine.verify→True; H112 SecuritySandbox.register only prints. H113–H127 (sudo no auth, kill/shutdown ungated, cap lifecycle unwired, GUI Popen Tkinter, ipc try_receive skips HMAC, is_root bypass, cgroup implicit-allow, umer_kernel1 dep, Kivy drift, dead REPLs, import-time crypto, kivy req, udev RUN unimpl+0o666, panic taint ValueError).

## Known 🔴 security hotspots (fail-open / cap-gate / dummy-crypto family)
- H1 live OpenRouter key `settings.local.json`.
- H2→H91 `eval()` initrd history.
- H3 `PASSWORD="password"` lib/security.py.
- H17 SecureBoot.verify_image fail-open.
- H27 boot verify_kernel trusts missing.
- H28 efi is_binary_trusted trusts DISABLED.
- H29 boot init auto-accepts waiver.
- H37 bin LoginCommand -f auth bypass.
- H46 cloud OTA verify_and_apply fail-open.
- H51 compatibility ZeroTrustContainer fail-open gate.
- H60 dev os.mknod no cap gate.
- H64 drivers static JWT + unauth /metrics.
- H66 drivers no cap gate MMIO/PCI/crypto.
- H73 etc sudoers no cap gate + NOPASSWD.
- H83 home tar extractall no filter.
- H91 initrd eval().
- H92 initrd no cap gate on boot ops.
- H93 initrd cpio traversal.
- H98 installer double UmerInstaller.
- H99 installer waiver fail-open.
- H101 installer rollback rmtree.
- **H110 kernel no-op placeholders → zero-trust/IPC/mem account INERT.**
- **H111 kernel dummy CryptoEngine.verify → True.**
- **H112 kernel SecuritySandbox.register only prints.**

## Project layout notes
- ~735 active Python modules; `tests/` unittest/pytest split, NO CI test step; `security_scan.yml` only workflow.
- `Old Linux Code/` (~93k files) reference-only, excluded from review.
- **Cross-cutting remediation pass (offered 6×, NOT yet requested):** fix the fail-open / cap-gating / dummy-crypto family — H17/H27/H28/H29/H46/H51/H60/H64/H66/H73/H83/H91/H92/H93/H98/H99/H101/H110/H111/H112/H113/H115/H117. Awaits user go-ahead.
