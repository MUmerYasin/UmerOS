# UmerOS — Long-term Project Memory

## Standing working conventions (Code Review Expert / Kim)
- **Review-standard-first workflow:** After *every* study (file/folder/design/dependency), update `MainTask/Raw Data/Code Review Standards and Process.md` — bump version, fold findings into §1/§4/§7/§9/§11. Standing user instruction; do not treat studies as read-only.
- **Authoritative sources (priority):** `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + `LICENSE`/`setup.py` (repo wins when a source is aspirational, e.g. README "Project Structure").

## Decided inconsistencies
- **H7 → GPL-3.0 canonical.** Sweep Apache-2.0 strays in prompts/docs/code to GPLv3.
- **H11 → Flutter (Dart) canonical frontend; backend = Python only.** `ui/*.py` (Tkinter/CLI) is retired legacy (H25); UI MUST follow HCI (Nielsen 10) — §4.8.

## Folder scope map (full detail in standard §9, H1–H239)
- `boot/` = /boot toolkit. 🔴 H27/H28/H29 trust missing/disabled/auto-waiver. +H30–H34.
- `bin/` = ~44 FHS cmds. H6/H35 wrong exec sig (27/44); 🔴 H37 `-f` auth bypass. H36/H38–H40.
- `build/` = PyInstaller. 🔴 H42 unsigned; H41 Tkinter not Flutter. H43–H45.
- `cloud/` = OTA. 🔴 H46 verify fail-open. H47–H49.
- `compatibility/` = foreign-OS. 🔴 H51 ZeroTrustContainer fail-open. H50/H52–H54.
- `core/` = base Command. H55 fix exec sig (root of H6/H35); H56 privileges unenforced. H57.
- `dev/` = ~43 /dev nodes. 🟡 H60 mknod no cap; H59 0o666. H58/H61. Cleanest.
- `drivers/` = 75 modules. 🔴 H64 static JWT + unauth /metrics; 🟡 H66 no cap MMIO/PCI. H62/H63/H69.
- `etc/` = 81 /etc cfg. 🔴 H73 sudoers no cap + NOPASSWD; 🟡 H72 pam permit. H70/H71.
- `examples/` = 2 demos. 💭 H74/H75.
- `feedback/` = BROKEN pkg. 🟡 H76–H79.
- `fs/` = VFS. 🟡 H80 no cap; H81 Apache stray. H82. First tier-label folder.
- `home/` = /home. 🔴 H83 tar extractall no filter; 🟡 H84 path-traversal username. H85–H88.
- `HostFiles/` = 3 assets. 🟡 H90 host write+auto-open. H89.
- `initrd/` = 17 early-boot. 🔴 H91 eval(); H92 no cap; H93 cpio traversal. H94–H97.
- `installer/` = 3 files. 🔴 H98 double Installer; H99 waiver fail-open; H101 rmtree rollback. H100/H102–H109.
- `kernel/` = 40-file microkernel. 🔴 H110 no-op placeholders → zero-trust/IPC/mem INERT; H111 dummy CryptoEngine.verify→True; H112 SecuritySandbox.register prints. H113–H127 (sudo no auth, kill/shutdown ungated, cap unwired, GUI Popen Tkinter, ipc skips HMAC, is_root bypass, cgroup allow, kivy drift, dead REPLs, import-time crypto, udev RUN unimpl+0o666, panic taint).
- `legal/` = 12-file consent pkg. 🔴 H128 Apache-2.0 primary (no GPL-3.0; H7 lives here); H129 audit fail-open; H130 get_license_text GPL returns Apache; H131 consent fails OPEN; H135 cli hardcodes "I AGREE". 🟡 H132 forgeable token; H136 DCO decorative; H138 hardcoded fingerprints; H139 soft safety_check. 🔴/🟡 H140 broken test_legal Test 4; H141 tests encode fail-open. 💭 H137 real PII/IBANs.
- `lib/` = 33-source /lib sim. BEST-disciplined (full baseline, zero dangerous calls, fsck fail-closed). 🔴 H3 `PASSWORD="password"`; H146 ssl `_check_is_trusted` fail-open; H147 `is_expired`→False. 💭 H148 string-parse sim; 🟡 H149 ~23 Apache strays (largest cluster, H7); 💭 H150 pam_permit.
- `liboqs/` = vendored UNPINNED OQS C (MIT, conflicts H7 → H151 🟡). Real FIPS-203/204/205 PQC. Live PQC NOT wired; UmerOS uses `quantum/crypto_pqc.py` (silent fallback → H152 🔴) + `kernel/pqcrypto_.py` (H153 🟡). 🔴 H154 OTA hardcoded fake sig. 💭 H155 dead/unwired.
- `media/` = 12 /media. 🔴 H156 no cap on mount/auto-mount/udisks2; H157 rw mount w/o noexec,nosuid,nodev. 🟡 H158 authz unwired; H159 fstab skips validate; H160 5 Apache strays. 💭 H161–H165.
- `mnt/` = 7 /mnt. 🔴 H166 no cap mount/remove/fstab; H167 rmtree symlink TOCTOU; H168 fstab write un-gated/drops comments. 🟡 H169 noexec missing; H170 validator advisory; H171 mtab clobber. 💭 H172–H175; 🟡 H176 6 Apache strays. Better than media (7 `_selftest` functional; audit.py safe).
- `network/` = 6 modules. 🔴 H177 no cap egress; H178 SSRF (no internal-range block). 🟡 H179 XOR "encryption"; H180 plaintext DNS. 💭 H181/H182.
- `opt/` = 14 /opt. 🔴 H184 no cap; H185 path-traversal file rw; H186 rmtree traversal; H187 cmd-injection launcher. 🟡 H188 profile.d inject; H189 hardcodes /etc/opt; H193 svc exec. 💭 H190–H192.
- `packages/` = 3 modules (best small baseline). 🔴 H194 tar-slip; H195 manifest traversal; H196 fail-open "Signed"; H197 payload not hashed; H198 no cap. 🟡 H199 lex compare; H200 Apache stray; H201 fuzzy match; H204 symlink extract. 💭 H202/H203.
- `proc/` = 24 /proc (CLEANEST dangerous-call hygiene, zero subprocess/eval/etc). 🔴 H205 write enforces only mode (no cap); H206 ~60 sysctl ungated; H207 oom_score_adj ungated; H208 irq affinity ungated. 🟡 H209 no-op rw; H210 hostname newline/registry bypass; H211 fabricated CapEff. 💭 H212 baseline; H213 missing GPL; H214 simulated fallback.
- `quantum/` = 62 modules (ZERO dangerous calls). 🔴 H215 Apache stray; H216 silent classical downgrade (H152); H217 plaintext creds; H221 0.0.0.0:8420 + wildcard CORS + no auth. 🟡 H218 no TLS pin; H219 toy QKD; H220 simulator QRNG. 💭 H222 CLI token argv; H223 2nd Apache stray; H224 print leak; H225 REST tokens clear.
- `root/` = 9 FHS /root modules (~87 KB). ZERO dangerous calls (cleanest alongside proc/quantum) + safe `os.chmod` (0700/0644/0600) + `shell.py` strips `LD_*` + `shlex.quote` + model read-only `safety.py`. 🟡 H226 10 Apache-2.0 strays (largest single-folder cluster, H7); 🟡 H227 `passwd.write()`/`upsert()` rewrite `/etc/passwd` ungated (cap family); 🟡 H228 `mail.ensure()` creates home @umask (~0755) not 0700. 💭 H229 `.bak` world-readable; H230 `home.ensure` chmod follows symlink + arbitrary CLI path; H231 dotfile template name traversal.
- `sbin/` = 9 FHS /sbin modules (~95 KB). **CLEANEST folder overall** — fully SIMULATED (ZERO dangerous calls AND zero real syscalls; every command prints+returns, mutating in-memory dicts). Only `maintenance.MktempCommand` does a real (safe, `tempfile` 0600) write. 🟡 H232 **missing GPL-3.0 header in all 9 modules** (zero GPL/Apache/Copyright strings — "missing-header" variant of H7, distinct from the Apache strays). 💭 H233 `SbinManager.execute()` + each `execute()` no cap gate / no audit log (ungated pattern for real wiring); 💭 H234 mount/filesystem ops simulated vs in-memory tables, real wiring must harden (`nosuid,nodev,noexec` + path checks, per mnt/media H156–H168); 💭 H235 commands masquerade as functional (`halt`/`mount -a` do nothing) → false-state risk. Models: `mount.py` global-state save/restore in `_selftest`, `mktemp` safe tempfile.
- `scripts/` = 2 dev/CI tooling scripts (1,736 B) — NOT a shipped runtime (helpers only). Bright spot: both use `subprocess` **injection-safe** (argv-list, no `shell=True`). 🟡 H236 missing GPL-3.0 header in both files (H7 missing-header variant, like sbin H232); 🟡 H237 `test_endpoint.generate_test_jwt` hardcodes `secret="test-secret"` (HS256) = **same** trusted secret as `drivers.driver_service` 🔴 H64 — the test legitimates the broken auth and would PASS against the vulnerable service, masking H64; 💭 H238 fixed `time.sleep(3)` readiness wait (flaky CI) + hits endpoint with a forged token bypassing any `CapabilityManager`/auth; 💭 H239 `install_deps.py` `pip install -r requirements.txt` unpinned (supply-chain: compromised/edited requirements installs arbitrary pkgs as current user) + `capture_output=True` buffers whole log; neither file has `from __future__`. Models: argv-list subprocess in both.

## Known 🔴 hotspots (fail-open / cap-gate / dummy-crypto family) — full table in standard §9
H1 live OpenRouter key; H2/H91 eval initrd; H3 PASSWORD="password"; H17 SB verify fail-open; H27/H28/H29 boot; H37 bin auth bypass; H46 OTA; H51 compat; H60 dev; H64 drivers; H66 drivers; H73 etc sudoers; H83 home tar; H91/H92/H93 initrd; H98/H99/H101 installer; H110/H111/H112 kernel inert; H128/H129/H130/H131/H135 legal; H146/H147 lib SSL; H152 quantum fallback; H154 OTA fake sig; H156/H157 media; H166/H167/H168 mnt; H177/H178 network; H184/H185/H186/H187 opt; H194–H198 packages; H205–H208 proc; H215/H216/H217/H221 quantum.

## Project layout notes
- ~735 active Python modules; `tests/` unittest/pytest split, NO CI; `security_scan.yml` only workflow.
- `Old Linux Code/` (~93k) reference-only, excluded.
- **Cross-cutting remediation pass (offered 19×, NOT yet requested):** fix fail-open / cap-gate / dummy-crypto family — H17/H27/H28/H29/H46/H51/H60/H64/H66/H73/H83/H91/H92/H93/H98/H99/H101/H110/H111/H112/H113/H115/H117/H128/H129/H130/H131/H135/H146/H147/H152/H154/H156/H157/H166/H167/H168/H177/H178/H184/H185/H186/H187/H194/H195/H196/H197/H198/H205/H206/H207/H208/H215/H216/H217/H221/**H227**. `quantum/` adds 4 🔴 + 3 🟡 + 4 💭; `root/` adds 0 🔴 + 3 🟡 (H226 Apache cluster H7, H227 cap-gate on /etc/passwd, H228 mail home perms) + 3 💭 (H229 `.bak`, H230 symlink chmod, H231 template traversal); `sbin/` adds 0 🔴 + 1 🟡 (H232 missing GPL header, H7 missing-header variant) + 3 💭 (H233 no cap gate/audit, H234 mount hardening pending, H235 simulated-command false state) — fully simulated, no live exploit; `scripts/` adds 0 🔴 + 2 🟡 (H236 missing GPL header H7 missing-header; H237 test JWT shares prod `test-secret`, legitimates 🔴 H64) + 2 💭 (H238 sleep(3) readiness + forged-token bypass; H239 unpinned pip install supply-chain). Total hotspots now **H1–H239**.
