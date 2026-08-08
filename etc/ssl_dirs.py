"""
UmerOS /etc SSL Directories
==============================
Manages SSL certificate directories and configuration.

FHS 3.0 entries:
  /etc/ssl/                    — SSL configuration
  /etc/ssl/certs/              — CA certificates
  /etc/ssl/private/            — Private keys
  /etc/ssl/openssl.cnf         — OpenSSL configuration
  /etc/ca-certificates/        — CA certificates (Debian/Ubuntu)
  /etc/ca-certificates.conf    — CA certificates list

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.SSLDirs")


class SSLDirsManager:
    """Manages /etc/ssl/ directories and CA certificate configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.ssl_path = self.etc_path / "ssl"
        self.ca_path = self.etc_path / "ca-certificates"

    def initialize(self) -> bool:
        try:
            (self.ssl_path / "certs").mkdir(parents=True, exist_ok=True)
            (self.ssl_path / "private").mkdir(parents=True, exist_ok=True)
            self.ca_path.mkdir(parents=True, exist_ok=True)
            (self.ca_path / "updated").mkdir(parents=True, exist_ok=True)
            self._create_openssl_conf()
            self._create_ca_certificates_conf()
            self._create_ssl_config()
            log.info("Initialized /etc/ssl/ and /etc/ca-certificates/")
            return True
        except Exception as e:
            log.error("Failed to initialize SSL dirs: %s", e)
            return False

    def _create_openssl_conf(self) -> None:
        fp = self.ssl_path / "openssl.cnf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/ssl/openssl.cnf - OpenSSL configuration\n"
            "# UmerOS OpenSSL Configuration\n\n"
            "HOME = .\n"
            "RANDFILE = $ENV::HOME/.rnd\n\n"
            "[ req ]\n"
            "default_bits = 2048\n"
            "default_md = sha256\n"
            "distinguished_name = req_distinguished_name\n"
            "attributes = req_attributes\n"
            "x509_extensions = v3_ca\n"
            "prompt = no\n\n"
            "[ req_distinguished_name ]\n"
            "C = US\n"
            "ST = State\n"
            "L = City\n"
            "O = UmerOS\n"
            "OU = UmerOS SSL\n"
            "CN = umeros.local\n\n"
            "[ req_attributes ]\n"
            "challengePassword = A challenge password\n\n"
            "[ v3_ca ]\n"
            "basicConstraints = critical, CA:TRUE\n"
            "keyUsage = keyCertSign, cRLSign\n"
            "subjectKeyIdentifier = hash\n"
            "authorityKeyIdentifier = keyid:always, issuer\n\n"
            "[ v3_req ]\n"
            "basicConstraints = CA:FALSE\n"
            "keyUsage = digitalSignature, keyEncipherment\n"
            "subjectAltName = @alt_names\n\n"
            "[ alt_names ]\n"
            "DNS.1 = umeros.local\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/ssl/openssl.cnf")

    def _create_ca_certificates_conf(self) -> None:
        fp = self.ca_path / "ca-certificates.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/ca-certificates.conf - CA certificates list\n"
            "# UmerOS CA Certificates Configuration\n"
            "# Lines starting with '!' are disabled\n\n"
            "DST_Root_CA_X3.pem\n"
            "ISRG_Root_X1.pem\n"
            "ISRG_Root_X2.pem\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/ca-certificates.conf")

    def _create_ssl_config(self) -> None:
        fp = self.etc_path / "ssl.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/ssl.conf - SSL system configuration\n"
            "# UmerOS SSL Configuration\n\n"
            "# Default SSL certificate directory\n"
            "SSL_CERT_DIR=/etc/ssl/certs\n\n"
            "# Default SSL certificate file\n"
            "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt\n\n"
            "# OpenSSL configuration\n"
            "OPENSSL_CONF=/etc/ssl/openssl.cnf\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/ssl.conf")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "ssl_path_exists": self.ssl_path.exists(),
            "openssl_conf_exists": (self.ssl_path / "openssl.cnf").exists(),
            "certs_count": len(list((self.ssl_path / "certs").iterdir())) if (self.ssl_path / "certs").exists() else 0,
            "private_count": len(list((self.ssl_path / "private").iterdir())) if (self.ssl_path / "private").exists() else 0,
            "ca_certificates_exists": self.ca_path.exists(),
            "ca_certificates_conf_exists": (self.ca_path / "ca-certificates.conf").exists(),
        }
