#

**Master Engineering Blueprint Reference:** `MainTask/prompt/Umer_OS_Antigravity_Master_Prompt.md`

---

## 1. Overview & Purpose

The `/legal` subsystem enforces legal liability disclaimers, explicit user consent gates (`I AGREE`), contributor attributions, open-source multi-licensing compliance, donation channels, and pre-execution safety checkpoints across UmerOS.

### Key Pillars:
1. **Official Disclaimer & Limitation of Liability (Appendix E):**
   - Software provided "AS IS", without warranty of any kind.
   - Authors and contributors bear no liability for data loss or hardware changes.
   - Mandatory recommendation for users to perform system backups before operations.
2. **Cryptographic Consent Gate & Audit Ledger:**
   - Enforces explicit user agreement (`I AGREE`) before installation or running critical microkernel/HAL procedures.
   - Records machine fingerprint, hostname, user ID, timestamp, and SHA-256 consent token in a persistent ledger.
3. **Contributors & Attribution (Appendix D):**
   - Roster of core architects (`Umer`), AI pairing intelligence (DeepMind Antigravity), and community contributors.
   - DCO (Developer Certificate of Origin) and CLA compliance verification.
4. **Project Sustainability & Donations (Appendix F):**
   - Funding channels (GitHub Sponsors, OpenCollective, Grants).
   - Donor recognition tiers (Platinum, Gold, Silver, Backer, Community).
5. **Maintainer Profiles (Appendix C):**
   - Verified maintainer identities with PQC Dilithium and PGP cryptographic key fingerprints.
6. **Pre-Execution Safety & Backup Engine:**
   - Disk space verification and automated safety snapshot creation before dangerous or low-level operations.

---

## 2. Architecture & Modules

| Module | Description |
|---|---|
| `disclaimer.py` | Legal disclaimers, liability waivers, warranty exclusions, risk classifications. |
| `consent.py` | Mandatory user consent gate, `I AGREE` validation, cryptographic audit ledger. |
| `contributors.py` | Contributor registry, DCO certification, attribution markdown generation. |
| `donations.py` | Sustainability channels, sponsorship tiers, donor ledger. |
| `licenses.py` | Multi-license compatibility framework (Apache-2.0, GPL-2.0, MIT) & scanner. |
| `maintainers.py` | Core maintainer profiles with Dilithium PQC & PGP key fingerprints. |
| `safety_check.py` | Pre-execution safety inspector, disk headroom checks, automated backup checkpoints. |
| `manager.py` | Master `LegalManager` coordinating all compliance systems. |
| `cli.py` | Command-line management tool `legal_ctl`. |
| `test_legal.py` | Standalone test suite. |

---

## 3. Python API Usage

```python
from legal import (
    LegalManager,
    ConsentManager,
    DisclaimerRegistry,
    SafetyChecker,
    RiskLevel,
)

# 1. Initialize master coordinator
mgr = LegalManager()

# 2. Check if user has consented
if not mgr.consent.has_consented("installer"):
    # Interactive consent gate
    mgr.consent.require_consent_interactive("installer")

# 3. View contextual disclaimers
notice = DisclaimerRegistry.get_notice("kernel_hal")
print(notice.full_text)

# 4. Run pre-execution safety check with automatic backup
safety_res = SafetyChecker.verify_safety(
    operation_name="flash_kernel",
    risk_level=RiskLevel.HIGH,
    target_path="/boot",
    create_backup=True,
)
print(safety_res.summary())

# 5. List verified maintainers
for m in mgr.maintainers.list_all():
    print(f"{m.name} - PQC Key: {m.pqc_public_key_fingerprint}")
```

---

## 4. Command-Line Interface (`legal_ctl`)

```bash
# View legal disclaimers
python -m legal.cli disclaimer general
python -m legal.cli disclaimer tldp
python -m legal.cli disclaimer installer

# Grant explicit legal consent
python -m legal.cli consent installer --user admin

# Verify consent status
python -m legal.cli verify installer

# List recognized contributors
python -m legal.cli contributors

# View donation channels and sponsor wall
python -m legal.cli donations

# View maintainers and PQC fingerprints
python -m legal.cli maintainers

# Scan directory for license header compliance
python -m legal.cli licenses .

# Run pre-execution safety check
python -m legal.cli safety-check partition_disk --risk high

# Show legal system summary
python -m legal.cli summary
```

---

## 5. Testing

Run standalone test suite:
```bash
python legal/test_legal.py
```
Or via pytest:
```bash
pytest tests/test_legal.py
```
