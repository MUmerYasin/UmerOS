"""
UmerOS /srv — Protocol-Specific Service Handlers
=================================================

Provides protocol-specific logic, directory management, and test servers
for services hosted under /srv (WWW, FTP, Git, Rsync, TFTP, Samba/NFS).

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import http.server
import logging
import os
import socketserver
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fhs import StandardProtocol
from service import ServiceConfig, ServiceRecord

log = logging.getLogger("UmerOS.Srv.Protocols")


class WWWServiceHandler:
    """Handles Web / HTTP / HTTPS site data under /srv/www or /srv/<domain>/www."""

    @staticmethod
    def setup_vhost(
        base_dir: Path | str,
        vhost_domain: str,
        document_root_name: str = "htdocs",
    ) -> Dict[str, Path]:
        """
        Creates a virtual host document root inside the service tree.
        """
        base = Path(base_dir).resolve()
        vhost_dir = base / "vhosts" / vhost_domain
        doc_root = vhost_dir / document_root_name
        cgi_dir = vhost_dir / "cgi-bin"
        logs_dir = vhost_dir / "logs"

        for d in (vhost_dir, doc_root, cgi_dir, logs_dir):
            d.mkdir(parents=True, exist_ok=True)

        index_file = doc_root / "index.html"
        if not index_file.exists():
            index_file.write_text(
                f"<!DOCTYPE html>\n<html><body><h1>{vhost_domain}</h1><p>Served from UmerOS /srv</p></body></html>",
                encoding="utf-8",
            )

        return {
            "vhost_dir": vhost_dir,
            "document_root": doc_root,
            "cgi_dir": cgi_dir,
            "logs_dir": logs_dir,
        }

    @staticmethod
    def start_test_server(doc_root: Path | str, port: int = 8080) -> Tuple[threading.Thread, socketserver.TCPServer]:
        """
        Starts a background HTTP test server serving files from the document root.
        """
        doc_root_str = str(Path(doc_root).resolve())

        class CustomHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=doc_root_str, **kwargs)

        server = socketserver.TCPServer(("127.0.0.1", port), CustomHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return thread, server


class FTPServiceHandler:
    """Handles FTP service data under /srv/ftp."""

    @staticmethod
    def setup_ftp_tree(base_dir: Path | str) -> Dict[str, Path]:
        base = Path(base_dir).resolve()
        pub_dir = base / "pub"
        incoming_dir = base / "incoming"
        conf_dir = base / "conf"

        for d in (pub_dir, incoming_dir, conf_dir):
            d.mkdir(parents=True, exist_ok=True)

        readme = pub_dir / "README.txt"
        if not readme.exists():
            readme.write_text(
                "Welcome to the UmerOS Anonymous FTP Archive.\n"
                "Files in /pub are publicly readable.\n"
                "Files can be dropped into /incoming.\n",
                encoding="utf-8",
            )

        return {"pub": pub_dir, "incoming": incoming_dir, "conf": conf_dir}


class GitServiceHandler:
    """Handles Git repositories under /srv/git."""

    @staticmethod
    def create_bare_repository(base_dir: Path | str, repo_name: str) -> Path:
        """
        Creates a bare repository directory structure under /srv/git/repositories/<repo_name>.git
        """
        base = Path(base_dir).resolve()
        repos_dir = base / "repositories"
        repos_dir.mkdir(parents=True, exist_ok=True)

        if not repo_name.endswith(".git"):
            repo_name += ".git"

        repo_path = repos_dir / repo_name
        repo_path.mkdir(parents=True, exist_ok=True)

        # Standard git bare layout
        for sub in ("branches", "hooks", "info", "objects/info", "objects/pack", "refs/heads", "refs/tags"):
            (repo_path / sub).mkdir(parents=True, exist_ok=True)

        head_file = repo_path / "HEAD"
        if not head_file.exists():
            head_file.write_text("ref: refs/heads/main\n", encoding="utf-8")

        config_file = repo_path / "config"
        if not config_file.exists():
            config_file.write_text(
                "[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = true\n",
                encoding="utf-8",
            )

        desc_file = repo_path / "description"
        if not desc_file.exists():
            desc_file.write_text(f"UmerOS Git repository {repo_name}\n", encoding="utf-8")

        return repo_path

    @staticmethod
    def list_repositories(base_dir: Path | str) -> List[str]:
        base = Path(base_dir).resolve()
        repos_dir = base / "repositories"
        if not repos_dir.exists():
            return []
        return [p.name for p in sorted(repos_dir.iterdir()) if p.is_dir()]


class RsyncServiceHandler:
    """Handles Rsync shares and configuration under /srv/rsync."""

    @staticmethod
    def generate_rsyncd_conf(base_dir: Path | str, module_name: str, comment: str = "UmerOS Rsync Share") -> str:
        base = Path(base_dir).resolve()
        shares_dir = base / "shares" / module_name
        shares_dir.mkdir(parents=True, exist_ok=True)

        conf = (
            f"[{module_name}]\n"
            f"    path = {shares_dir}\n"
            f"    comment = {comment}\n"
            f"    read only = yes\n"
            f"    list = yes\n"
            f"    uid = nobody\n"
            f"    gid = nogroup\n"
        )
        conf_file = base / "conf" / f"{module_name}.conf"
        conf_file.parent.mkdir(parents=True, exist_ok=True)
        conf_file.write_text(conf, encoding="utf-8")
        return conf


class TFTPServiceHandler:
    """Handles TFTP / PXE Boot service data under /srv/tftp."""

    @staticmethod
    def setup_pxe_boot(base_dir: Path | str) -> Dict[str, Path]:
        base = Path(base_dir).resolve()
        boot_dir = base / "boot"
        pxe_dir = base / "pxelinux.cfg"
        images_dir = base / "images"

        for d in (boot_dir, pxe_dir, images_dir):
            d.mkdir(parents=True, exist_ok=True)

        default_menu = pxe_dir / "default"
        if not default_menu.exists():
            default_menu.write_text(
                "DEFAULT menu.c32\n"
                "PROMPT 0\n"
                "TIMEOUT 100\n"
                "LABEL umeros\n"
                "  MENU LABEL UmerOS Network Boot\n"
                "  KERNEL /boot/vmlinuz\n"
                "  APPEND initrd=/boot/initrd.img\n",
                encoding="utf-8",
            )

        return {"boot": boot_dir, "pxelinux.cfg": pxe_dir, "images": images_dir}


class SambaNfsServiceHandler:
    """Handles Network file shares under /srv/nfs and /srv/samba."""

    @staticmethod
    def generate_nfs_export_line(share_path: Path | str, client: str = "*", options: str = "rw,sync,no_subtree_check") -> str:
        p = Path(share_path).resolve()
        return f"{p} {client}({options})\n"

    @staticmethod
    def generate_samba_share_section(share_name: str, share_path: Path | str, comment: str = "UmerOS Samba Share") -> str:
        p = Path(share_path).resolve()
        return (
            f"[{share_name}]\n"
            f"    comment = {comment}\n"
            f"    path = {p}\n"
            f"    browseable = yes\n"
            f"    read only = no\n"
            f"    create mask = 0775\n"
            f"    directory mask = 0775\n"
        )
