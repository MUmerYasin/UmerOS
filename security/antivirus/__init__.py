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

"""UmerOS Antivirus Engine - Signature + Heuristic + Real-time Protection."""

from .engine import AntivirusEngine
from .signatures import SignatureDatabase
from .scanner import FileScanner
from .realtime import RealtimeMonitor
from .quarantine import QuarantineManager
from .heuristics import HeuristicAnalyzer

__all__ = [
    "AntivirusEngine",
    "SignatureDatabase",
    "FileScanner",
    "RealtimeMonitor",
    "QuarantineManager",
    "HeuristicAnalyzer",
]
