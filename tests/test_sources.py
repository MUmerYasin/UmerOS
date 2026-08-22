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
pytest test suite for UmerOS /sources subsystem.
"""

import sys
from pathlib import Path
import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from sources import (
    BibliographyRegistry,
    SourceCategory,
    SourceReference,
    SYSTEM_V_SIGNALS,
    SignalDispatcher,
    SignalAction,
    GlossaryRegistry,
    GlossaryEntry,
    KernelDocsRegistry,
    SourceTreeManager,
    SourcesManager,
)


def test_bibliography():
    reg = BibliographyRegistry()
    assert len(reg.list_all()) >= 15
    kern = reg.get("kernighan1984unix")
    assert kern is not None
    assert "Brian W. Kernighan" in kern.authors


def test_signals():
    disp = SignalDispatcher()
    assert len(SYSTEM_V_SIGNALS) == 31
    assert SYSTEM_V_SIGNALS[9].name == "SIGKILL"
    assert not SYSTEM_V_SIGNALS[9].can_catch

    called = []
    disp.register_handler("SIGUSR1", lambda s, c: called.append(s))
    res = disp.send_signal(100, "SIGUSR1")
    assert res["success"]
    assert 10 in called


def test_glossary():
    glo = GlossaryRegistry()
    assert len(glo.list_all()) >= 45
    assert glo.get("fhs") is not None


def test_kernel_docs():
    doc = KernelDocsRegistry.get_doc("proc.txt")
    assert doc is not None
    assert "1.1 /proc/cpuinfo" in doc["sections"]


def test_sources_manager():
    mgr = SourcesManager()
    summary = mgr.get_summary()
    assert summary["total_bibliography_sources"] >= 15
    assert summary["total_signals_defined"] == 31

    search_res = mgr.search_all("proc")
    assert search_res["total_matches"] >= 1
