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
Umer OS — Resource Predictor shim  [TODAY]
============================================
Review Hotspot H19 consolidation: this module used to carry a ~356-line
duplicate of the canonical EWMA resource predictor (a second, divergent
``ResourcePredictor`` competing with ``ai.umer_ai.AIResourceManager``).

The single source of truth for resource prediction now lives in
``ai.umer_ai.AIResourceManager`` — it owns persistence, pattern detection,
z-score spike detection, and workload classification, and it is already wired
into ``SelfHealingEngine``, ``AIGovernance`` and the kernel bootstrap
(``NullAIResourceManager``).  H19 therefore selected it as the one canonical
predictor.

This file now re-exports that class under the legacy ``ResourcePredictor``
name so any old importer keeps working, but new code should depend on
``ai.umer_ai.AIResourceManager`` directly.  The divergent per-PID helper logic
that lived here was removed because it had no callers in the tree.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

# [FIX H19] Consolidate the duplicated predictor into the canonical
# ai.umer_ai.AIResourceManager.  ResourcePredictor is retained only as an
# import-compatible alias; the standalone duplicate implementation was deleted.
from ai.umer_ai import AIResourceManager as ResourcePredictor


__all__ = ["ResourcePredictor"]
