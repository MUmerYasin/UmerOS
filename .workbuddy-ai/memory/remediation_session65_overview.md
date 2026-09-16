# UmerOS Remediation — Session 65 (H48)

## H48 — `cloud/ota_updater/update_system.py` hardcoded simulated OTA endpoint: RESOLVED (real fix)

### Premise (standard §9, H48 — 🟡 YELLOW)
`cloud/ota_updater/update_system.py:22` hardcoded `update_url = "https://updates.umeros.dev/latest"` — a simulated domain baked into code; no pinned/verified update source, no cert or signing-key pinning (extends H47).

### Drift-recon
- The hardcoded URL is live, but at **line 66** (shifted from the standard's `:22` by the H47 baseline rewrite), inside `UpdateManager.__init__`.
- No test depends on the URL (grep `tests/` for `update_url`/`updates.umeros.dev` → 0 hits). Repo env-var convention is `UMEROS_*` (e.g. `UMEROS_ALLOW_UNSIGNED`, `UMEROS_QUANTUM_AUTH_KEY`).

### Fix (applied to `cloud/ota_updater/update_system.py`, `# [FIX H48]`)
1. **Externalize endpoint to config** — `self.update_url` now resolves from `UMEROS_OTA_UPDATE_URL` (falling back to a named `DEFAULT_OTA_UPDATE_URL` constant) and may also be injected via a new `update_url=` constructor arg. The simulated default domain remains only as the documented fallback.
2. **Pin the update-server cert + signing key** — `UMEROS_OTA_SERVER_CERT_FP` (default placeholder SHA-256 fingerprint `DEFAULT_OTA_SERVER_CERT_FP`, explicitly marked "NOT a real cert") + `UMEROS_OTA_PINNED_HOST` (`DEFAULT_OTA_PINNED_HOST`); the signing public key (`trusted_public_key`, already the fail-closed verify pin from H46/H154) is now documented as the signature pin.
3. **Fail closed on mismatch** — new `_assert_update_source_trusted()` is called at the top of `check_for_updates()` and refuses the update when: endpoint is not HTTPS; host is loopback/link-local/internal (`_UNTRUSTED_OTA_HOSTS`); a cert fingerprint is pinned but the host ≠ pinned expected host; or unsigned updates are not allowed and no signing key is pinned. On refusal it returns a "no update" manifest (fail-closed — never silently applies).

### Verification
- `py_compile` clean; import smoke-test OK (`UpdateManager` still re-exported by `cloud/ota_updater/__init__.py`).
- Behaviour matrix (default config has no `UMEROS_OTA_ALLOW_UNSIGNED`):
  - default config → trusted (`_assert_update_source_trusted()` == True); simulated `check_for_updates()` still returns `latest_version` 2.1.0 (unchanged).
  - override to `https://evil.example.com/latest` (no re-pin) → **refused** (host ≠ pinned cert host).
  - `http://...` plaintext → **refused** (not HTTPS).
  - no `trusted_public_key` + unsigned forbidden → **refused**.
  - consistent re-pin (`UMEROS_OTA_UPDATE_URL` + `UMEROS_OTA_PINNED_HOST`) → trusted.

### Bookkeeping closed (6 surfaces)
- Checkpoint box `- [ ]` → `- [x]` (location corrected `:22` → file only).
- Standard §9 row H48 🟡 → 🟢 + RESOLVED note (location `:22` → file only).
- NEXT pointer → **H49**; NEXT header `session 65`.
- MEMORY YELLOW pointer → session 65 + `cloud/` folder map `🟢 H46,H154,H47,H48; 🟡 H49`.
- Daily log `2026-09-16.md` Session 65 entry.
- This overview.
