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
UmerOS /etc/ppp/ Configuration Manager
Manages PPP (Point-to-Point Protocol) configuration.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PPPPeer:
    """A PPP peer configuration."""
    name: str
    user: str = "user"
    password: str = ""
    phone_number: str = ""
    baud: int = 115200
    mtu: int = 1500
    mru: int = 1500
    noauth: bool = True
    defaultroute: bool = True
    usepeerdns: bool = True
    persist: bool = True
    maxfail: int = 10
    holdoff: int = 30


class PPPConfigManager:
    """Manages /etc/ppp/ configuration."""

    def __init__(self, ppp_path: str = "/etc/ppp"):
        self.ppp_path = Path(ppp_path)
        self.peers: Dict[str, PPPPeer] = {}
        self.chatscripts_path = self.ppp_path / "chatscripts"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create ppp directory structure."""
        self.ppp_path.mkdir(parents=True, exist_ok=True)
        self.chatscripts_path.mkdir(parents=True, exist_ok=True)

    def add_peer(self, peer: PPPPeer) -> None:
        """Add a PPP peer configuration."""
        self.peers[peer.name] = peer
        self._write_peer_file(peer)

    def _write_peer_file(self, peer: PPPPeer) -> None:
        """Write a peer configuration file."""
        content = f"# PPP peer: {peer.name}\n"
        content += f"plugin pppoe.so\n"
        content += f"noauth\n" if peer.noauth else ""
        content += f"defaultroute\n" if peer.defaultroute else ""
        content += f"usepeerdns\n" if peer.usepeerdns else ""
        content += f"persist\n" if peer.persist else ""
        content += f"maxfail {peer.maxfail}\n"
        content += f"holdoff {peer.holdoff}\n"
        content += f"mtu {peer.mtu}\n"
        content += f"mru {peer.mru}\n"
        content += f"nodetach\n"
        
        if peer.user:
            content += f"user {peer.user}\n"
        if peer.password:
            content += f"password {peer.password}\n"
        
        peer_file = self.ppp_path / f"peers/{peer.name}"
        peer_file.parent.mkdir(parents=True, exist_ok=True)
        peer_file.write_text(content, encoding='utf-8')

    def get_peer(self, name: str) -> Optional[PPPPeer]:
        """Get a PPP peer configuration."""
        return self.peers.get(name)

    def list_peers(self) -> List[str]:
        """List all configured PPP peers."""
        return list(self.peers.keys())

    def create_chatscript(self, phone_number: str, script_name: str = "default") -> None:
        """Create a chat script for dial-up."""
        content = f"# Chat script for {script_name}\n"
        content += "ABORT 'BUSY'\n"
        content += "ABORT 'NO CARRIER'\n"
        content += "ABORT 'NO DIALTONE'\n"
        content += "ABORT 'ERROR'\n"
        content += "ABORT 'NO ANSWER'\n"
        content += "TIMEOUT 30\n"
        content += f"\"\" AT\n"
        content += f"OK-OK-OK ATZ\n"
        content += f"OK ATD{phone_number}\n"
        content += f"CONNECT \"\"\n"
        
        script_file = self.chatscripts_path / script_name
        script_file.write_text(content, encoding='utf-8')
