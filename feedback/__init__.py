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
UmerOS /feedback -- Community Feedback, Bug Reports & GNU FDL Subsystem
=======================================================================

Implements the community feedback framework, bug/correction/suggestion
pipeline, and GNU Free Documentation License (GFDL) engine



Modules:
--------
models        - FeedbackEntry, FeedbackKind, FeedbackStatus, FeedbackPriority
collector     - FeedbackCollector: submit, validate & persist feedback reports
tracker       - FeedbackTracker: triage, assign, resolve & audit lifecycle
channels      - Channel definitions (email, GitHub Issues, mailing-list, IRC/Matrix)
gfdl          - GFDLLicense: GNU Free Documentation License 1.3 text & compliance checker
manager       - FeedbackManager: master coordinator
cli           - feedback_ctl command-line controller

Author: Muhammad Umer Yasin / UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import sys as _sys
from os import path as _p

_this_dir = _p.dirname(_p.abspath(__file__))
if _this_dir not in _sys.path:
    _sys.path.insert(0, _this_dir)

from models import (
    FeedbackEntry,
    FeedbackKind,
    FeedbackStatus,
    FeedbackPriority,
)
from collector import FeedbackCollector
from tracker import FeedbackTracker
from channels import FeedbackChannel, UMEROS_FEEDBACK_CHANNELS
from gfdl import GFDLLicense, GFDL_SECTIONS
from manager import FeedbackManager, get_default_feedback_manager

__version__ = "1.0.0"

__all__ = [
    "FeedbackEntry",
    "FeedbackKind",
    "FeedbackStatus",
    "FeedbackPriority",
    "FeedbackCollector",
    "FeedbackTracker",
    "FeedbackChannel",
    "UMEROS_FEEDBACK_CHANNELS",
    "GFDLLicense",
    "GFDL_SECTIONS",
    "FeedbackManager",
    "get_default_feedback_manager",
]
