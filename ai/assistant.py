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
Umer OS — Assistant module shim  [TODAY]
=========================================
Review Hotspot H19 consolidation: this file used to carry a duplicate,
non-functional ``AIAssistant`` stub that drifted from the real engine.

The canonical assistant now lives in ``ai.umer_ai.LocalAIAssistant``
(diagnostics + fallback) on top of ``ai.assistant_service.ChatService``
(consent-gated multi-provider chat). Import either path from here so
older callers keep working:

    from ai.assistant import AIAssistant          # -> LocalAIAssistant
    from ai.assistant import get_chat_service     # -> shared ChatService

Author:  Umer OS Project
License: GPLv3
"""

from ai.umer_ai import LocalAIAssistant
from ai.assistant_service import ChatService, chat_service


class AIAssistant(LocalAIAssistant):
    """Backwards-compatible alias for :class:`LocalAIAssistant`."""

    def __init__(self) -> None:  # old stub took no args
        super().__init__()


def get_chat_service() -> ChatService:
    """Return the process-wide consent-gated chat service."""
    return chat_service


__all__ = ["AIAssistant", "ChatService", "get_chat_service"]
