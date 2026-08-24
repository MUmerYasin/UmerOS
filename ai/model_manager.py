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
Umer OS — Local LLM Download Manager  [TODAY]
==============================================
Lets users bring their own model: browses a curated catalogue of
open-weight GGUF models (small enough for laptops), downloads them to
``~/.umeros/models/``, tracks progress, supports cancel + delete.

Downloads are plain HTTPS from Hugging Face ``resolve/main`` URLs —
no extra dependency required. Progress is polled by the UI through
:meth:`ModelManager.snapshot`.

Author:  Umer OS Project
License: GPLv3
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.AI.Models")

DEFAULT_MODELS_DIR = os.environ.get(
    "UMEROS_AI_MODELS_DIR",
    os.path.join(os.path.expanduser("~"), ".umeros", "models"),
)


@dataclass
class CatalogEntry:
    model_id: str          # stable id used by API/UI
    filename: str          # gguf file on disk
    title: str             # human name
    size_gb: float
    params: str            # "0.5B" / "1.5B" ...
    quant: str             # "Q4_K_M" etc.
    description: str
    url: str


CATALOG: List[CatalogEntry] = [
    CatalogEntry(
        "qwen2.5-0.5b-instruct-q4", "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "Qwen 2.5 Instruct", 0.4, "0.5B", "Q4_K_M",
        "Tiny but surprisingly capable. Great first local model.",
        "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    CatalogEntry(
        "qwen2.5-1.5b-instruct-q4", "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "Qwen 2.5 Instruct", 1.0, "1.5B", "Q4_K_M",
        "Balanced quality/speed for 8 GB RAM machines.",
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    CatalogEntry(
        "llama3.2-1b-instruct-q4", "llama-3.2-1b-instruct-q4_k_m.gguf",
        "Llama 3.2 Instruct", 0.8, "1B", "Q4_K_M",
        "Meta's compact assistant model, strong multilingual chat.",
        "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"),
    CatalogEntry(
        "llama3.2-3b-instruct-q4", "llama-3.2-3b-instruct-q4_k_m.gguf",
        "Llama 3.2 Instruct", 2.0, "3B", "Q4_K_M",
        "Best small-model quality; needs ~4 GB RAM.",
        "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"),
    CatalogEntry(
        "phi-3.5-mini-instruct-q4", "phi-3.5-mini-instruct-q4_k_m.gguf",
        "Phi-3.5 Mini", 2.2, "3.8B", "Q4_K_M",
        "Microsoft's reasoning-heavy mini; excellent at code Q&A.",
        "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf"),
    CatalogEntry(
        "gemma-2-2b-it-q4", "gemma-2-2b-it-q4_k_m.gguf",
        "Gemma 2 Instruct", 1.7, "2.6B", "Q4_K_M",
        "Google's efficient chat model with good instruction following.",
        "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf"),
]


@dataclass
class DownloadJob:
    model_id: str
    filename: str
    title: str
    total_bytes: int = 0
    downloaded_bytes: int = 0
    status: str = "queued"          # queued|downloading|done|error|cancelled
    error: str = ""
    started_ts: float = field(default_factory=time.time)
    cancel_flag: bool = False

    def public(self) -> dict:
        pct = (self.downloaded_bytes / self.total_bytes * 100.0
               if self.total_bytes else 0.0)
        return {
            "model_id": self.model_id,
            "filename": self.filename,
            "title": self.title,
            "status": self.status,
            "progress": round(pct, 1),
            "downloaded_mb": round(self.downloaded_bytes / 1e6, 1),
            "total_mb": round(self.total_bytes / 1e6, 1),
            "error": self.error,
        }


class ModelManager:
    """Catalogue + downloader + installed-model registry."""

    def __init__(self, models_dir: Optional[str] = None) -> None:
        self.models_dir = models_dir or DEFAULT_MODELS_DIR
        os.makedirs(self.models_dir, exist_ok=True)
        self._jobs: Dict[str, DownloadJob] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ── catalog ─────────────────────────────────────────────────────────

    def catalog(self) -> List[dict]:
        installed = set(self.installed_filenames())
        return [{
            "id": e.model_id,
            "filename": e.filename,
            "title": e.title,
            "params": e.params,
            "quant": e.quant,
            "size_gb": e.size_gb,
            "description": e.description,
            "installed": e.filename in installed,
        } for e in CATALOG]

    def _entry(self, model_id: str) -> Optional[CatalogEntry]:
        return next((e for e in CATALOG if e.model_id == model_id), None)

    # ── installed ────────────────────────────────────────────────────────

    def installed_filenames(self) -> List[str]:
        try:
            return sorted(f for f in os.listdir(self.models_dir)
                          if f.lower().endswith(".gguf"))
        except OSError:
            return []

    def installed_details(self) -> List[dict]:
        out = []
        for fn in self.installed_filenames():
            path = os.path.join(self.models_dir, fn)
            try:
                size_gb = round(os.path.getsize(path) / 1e9, 2)
            except OSError:
                size_gb = 0.0
            entry = next((e for e in CATALOG if e.filename == fn), None)
            out.append({
                "filename": fn,
                "title": entry.title if entry else fn,
                "size_gb": size_gb,
                "path": path,
            })
        return out

    def delete_model(self, filename: str) -> bool:
        """Delete a downloaded .gguf. Name validated against dir listing."""
        safe_names = self.installed_filenames()
        if filename not in safe_names:
            log.warning("Refusing to delete unknown model file '%s'.", filename)
            return False
        try:
            os.remove(os.path.join(self.models_dir, filename))
            log.info("Deleted model '%s'.", filename)
            return True
        except OSError as exc:
            log.error("Failed deleting '%s': %s", filename, exc)
            return False

    # ── download orchestration ───────────────────────────────────────────

    def start_download(self, model_id: str) -> dict:
        entry = self._entry(model_id)
        if not entry:
            return {"ok": False, "error": f"Unknown model id '{model_id}'."}
        with self._lock:
            job = self._jobs.get(model_id)
            if job and job.status in ("queued", "downloading"):
                return {"ok": True, "already_running": True,
                        "job": job.public()}
            job = DownloadJob(model_id=entry.model_id,
                              filename=entry.filename,
                              title=entry.title)
            self._jobs[model_id] = job
        th = threading.Thread(target=self._worker, args=(job, entry.url),
                              daemon=True, name=f"dl-{model_id}")
        self._threads[model_id] = th
        th.start()
        return {"ok": True, "job": job.public()}

    def cancel_download(self, model_id: str) -> bool:
        job = self._jobs.get(model_id)
        if not job or job.status not in ("queued", "downloading"):
            return False
        job.cancel_flag = True
        return True

    def snapshot(self) -> List[dict]:
        with self._lock:
            jobs = list(self._jobs.values())
        return [j.public() for j in jobs]

    # ── worker ───────────────────────────────────────────────────────────

    def _worker(self, job: DownloadJob, url: str) -> None:
        dest = os.path.join(self.models_dir, job.filename)
        tmp = dest + ".part"
        job.status = "downloading"
        try:
            req = urllib.request.Request(url, headers={"User-Agent":
                                                       "UmerOS-AI/2.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, \
                    open(tmp, "wb") as fh:
                total = resp.headers.get("Content-Length")
                job.total_bytes = int(total) if total else 0
                while True:
                    if job.cancel_flag:
                        job.status = "cancelled"
                        log.info("Download cancelled: %s", job.model_id)
                        break
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fh.write(chunk)
                    job.downloaded_bytes += len(chunk)

            if job.status == "downloading":
                shutil.move(tmp, dest)
                job.status = "done"
                log.info("Downloaded '%s' (%.1f MB).",
                         job.filename, job.downloaded_bytes / 1e6)
            elif job.status == "cancelled":
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = str(exc)[:300]
            log.error("Download failed (%s): %s", job.model_id, exc)
            try:
                os.remove(tmp)
            except OSError:
                pass
