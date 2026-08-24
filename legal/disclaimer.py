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
UmerOS Legal & Compliance — Disclaimer & Limitation of Liability Subsystem
==========================================================================

Implements official disclaimers, liability waivers, warranty exemptions,
and safety recommendations per the Linux Filesystem Hierarchy standard
( Disclaimer) and UmerOS Master Engineering Blueprint.



Core Legal Mandates:
--------------------
1. No Liability: No liability for the contents, instructions, or scripts
   is accepted. Use concepts, code, and system alterations strictly at your own risk.
2. System Safety & Backups: Because low-level OS operations, partition changes,
   and experimental modules could potentially damage a system, users are
   strongly advised to proceed with caution and perform full system backups.
3. As-Is Provision: Software and documentation are provided "AS IS", without
   warranty of any kind, express or implied.
4. AI & Quantum Simulation Notice: AI predictions and quantum circuit
   simulations are experimental and not guaranteed for mission-critical life-safety.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import enum
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class RiskLevel(str, enum.Enum):
    """Classification of technical risk for operations."""
    SAFE = "safe"                      # Read-only or sandboxed
    MODERATE = "moderate"              # User configuration changes
    HIGH = "high"                      # Service reconfiguration, package install
    CRITICAL = "critical"              # Kernel module load, disk partition, low-level HAL


@dataclass
class DisclaimerNotice:
    """A structured legal disclaimer notice."""
    title: str
    summary: str
    full_text: str
    risk_level: RiskLevel = RiskLevel.MODERATE
    requires_explicit_consent: bool = True
    backup_recommended: bool = True
    version: str = "2.0.0"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        return d


# ── Canonical UmerOS & TLDP Disclaimer Text ───────────────────────────────

TLDP_DISCLAIMER_TEXT = """
FILESYSTEM HIERARCHY — APPENDIX E. DISCLAIMER
====================================================
No liability for the contents of this document or software is accepted.
Use the concepts, examples, commands, and other content at your own risk.
There may be errors and inaccuracies that could potentially damage your system.
Proceed with caution. Although this is highly unlikely, you are strongly
recommended to perform system backups before proceeding.
"""

UMEROS_MASTER_DISCLAIMER_TEXT = """
UMEROS UNIVERSAL OPERATING SYSTEM — LEGAL LIABILITY WAIVER & WARRANTY DISCLAIMER
=================================================================================
1. EXPERIMENTAL RESEARCH SYSTEM:
   UmerOS is a Python-first, AI-native, quantum-inspired operating system research
   prototype. Features labeled 'TODAY', 'EXPERIMENTAL', and 'FUTURE' provide
   different maturity guarantees.

2. NO WARRANTY (AS-IS):
   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT.

3. LIMITATION OF LIABILITY:
   IN NO EVENT SHALL THE AUTHORS, COPYRIGHT HOLDERS, DEEPMIND AI ASSISTANTS,
   OR CONTRIBUTORS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY,
   WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF,
   OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

4. MANDATORY BACKUP RECOMMENDATION:
   Low-level hardware access, quantum simulation buffers, and microkernel
   scheduling modifications can cause system instability. Users must maintain
   independent, verified backups of all critical data before running kernel services.
"""


class DisclaimerRegistry:
    """Registry providing contextual disclaimers and safety notices."""

    _NOTICES: Dict[str, DisclaimerNotice] = {
        "general": DisclaimerNotice(
            title="UmerOS General Legal Disclaimer",
            summary="General liability waiver and warranty disclaimer for UmerOS.",
            full_text=UMEROS_MASTER_DISCLAIMER_TEXT.strip(),
            risk_level=RiskLevel.MODERATE,
            requires_explicit_consent=True,
            backup_recommended=True,
        ),
        "tldp": DisclaimerNotice(
            title="TLDP Linux Filesystem Hierarchy Disclaimer",
            summary="Official TLDP Appendix E disclaimer regarding system modifications.",
            full_text=TLDP_DISCLAIMER_TEXT.strip(),
            risk_level=RiskLevel.MODERATE,
            requires_explicit_consent=False,
            backup_recommended=True,
        ),
        "installer": DisclaimerNotice(
            title="UmerOS Installation & Deployment Waiver",
            summary="Mandatory pre-installation legal consent and liability waiver.",
            full_text=(
                "INSTALLATION LIABILITY WAIVER:\n"
                "Installing UmerOS may alter system configuration, boot partitions,\n"
                "and device drivers. By proceeding, you accept all technical and legal\n"
                "liability for any hardware changes or data loss.\n"
                "Type 'I AGREE' to accept these terms."
            ),
            risk_level=RiskLevel.HIGH,
            requires_explicit_consent=True,
            backup_recommended=True,
        ),
        "kernel_hal": DisclaimerNotice(
            title="Kernel HAL & Direct Hardware Access Disclaimer",
            summary="Low-level ctypes/Cython driver execution disclaimer.",
            full_text=(
                "LOW-LEVEL DRIVER NOTICE:\n"
                "Direct hardware abstraction layer (HAL) execution bypasses standard\n"
                "user-space memory protection. Faulty drivers may crash the host system."
            ),
            risk_level=RiskLevel.CRITICAL,
            requires_explicit_consent=True,
            backup_recommended=True,
        ),
        "quantum_ai": DisclaimerNotice(
            title="Quantum Simulation & AI Inference Notice",
            summary="Notice regarding simulated qubits and probabilistic AI outputs.",
            full_text=(
                "QUANTUM & AI NOTICE:\n"
                "Quantum state simulation and AI-assisted task scheduling are probabilistic.\n"
                "Do not rely on outputs for life-critical or financial execution without verification."
            ),
            risk_level=RiskLevel.SAFE,
            requires_explicit_consent=False,
            backup_recommended=False,
        ),
    }

    @classmethod
    def get_notice(cls, category: str = "general") -> DisclaimerNotice:
        return cls._NOTICES.get(category, cls._NOTICES["general"])

    @classmethod
    def list_notices(cls) -> Dict[str, DisclaimerNotice]:
        return dict(cls._NOTICES)
