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

#!/usr/bin/env python3
"""
UmerOS - /etc/ssl manager
FHS 3.0: /etc/ssl contains SSL/TLS certificates and keys.
/etc/ssl/certs/ — CA certificates
/etc/ssl/private/ — private keys
/etc/ssl/openssl.cnf — OpenSSL configuration
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

SSL_DIR = Path(os.environ.get("UMEROS_SSL", "/etc/ssl"))
CERTS_DIR = SSL_DIR / "certs"
PRIVATE_DIR = SSL_DIR / "private"
OPENSSL_CONF = SSL_DIR / "openssl.cnf"

DEFAULT_OPENSSL_CONF = """# OpenSSL configuration - UmerOS
HOME            = .
RANDFILE        = $ENV::HOME/.rnd

[req]
default_bits    = 2048
distinguished_name = req_distinguished_name
prompt          = no

[req_distinguished_name]
C  = PK
ST = Punjab
L  = Islamabad
O  = UmerOS
CN = umerOS
"""


class SSLConfigManager:
    """Manages /etc/ssl certificates and configuration."""

    def __init__(self):
        CERTS_DIR.mkdir(parents=True, exist_ok=True)
        PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        if not OPENSSL_CONF.exists():
            OPENSSL_CONF.write_text(DEFAULT_OPENSSL_CONF, encoding="utf-8")

    def list_certs(self) -> List[str]:
        return sorted(f.name for f in CERTS_DIR.iterdir() if f.is_file()) if CERTS_DIR.exists() else []

    def read_openssl_conf(self) -> str:
        return OPENSSL_CONF.read_text(encoding="utf-8") if OPENSSL_CONF.exists() else ""

    def add_cert(self, name: str, content: str) -> None:
        (CERTS_DIR / name).write_text(content, encoding="utf-8")

    def cert_path(self, name: str) -> Path:
        return CERTS_DIR / name

    def private_key_path(self, name: str) -> Path:
        return PRIVATE_DIR / name
