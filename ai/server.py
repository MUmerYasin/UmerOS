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
Umer OS — AI HTTP Service  [TODAY]
===================================
FastAPI server that bridges the Flutter AI Assistant (desktop shell)
to the consent-gated provider stack. Binds 127.0.0.1 only.

Run:   python -m ai.server          (or uvicorn ai.server:app)

Endpoints
---------
GET    /health
GET    /api/ai/status
GET    /api/ai/providers
POST   /api/ai/chat                 {message, session_id?, provider_id?, model?, stream?}
GET    /api/ai/config               (api keys masked)
PATCH  /api/ai/config               (merge; accepts providers.api_key entries)
GET    /api/ai/consent              POST /api/ai/consent/{pid}  DELETE same
GET    /api/ai/local/catalog        POST /api/ai/local/download {model_id}
GET    /api/ai/local/downloads      DELETE /api/ai/local/models/{filename}

Author:  Umer OS Project
License: GPLv3
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai.assistant_service import chat_service
from ai.consent import governance
from ai.model_manager import ModelManager

log = logging.getLogger("UmerOS.AI.Server")

HOST = "127.0.0.1"
PORT = int(__import__("os").environ.get("UMEROS_AI_PORT", "8421"))

app = FastAPI(title="UmerOS AI Service", version="2.0")

# Loopback-only CORS so the desktop shell can call us from any local
# renderer without exposing the API to the network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # loopback-bound server; local UI origin varies
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

models = ModelManager()


# ── schemas ──────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = "default"
    provider_id: Optional[str] = None
    model: Optional[str] = None
    stream: bool = False


class ConfigPatch(BaseModel):
    updates: Dict[str, Any]


class ConsentRequest(BaseModel):
    note: str = ""


class DownloadRequest(BaseModel):
    model_id: str


# ── health / status ──────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "umer-ai"}


@app.get("/api/ai/status")
def status() -> dict:
    return chat_service.status()


@app.get("/api/ai/providers")
def providers() -> list:
    return chat_service.list_providers()


# ── chat ─────────────────────────────────────────────────────────────────

def _sse_format(chunk: str) -> str:
    return f"data: {json.dumps({'delta': chunk})}\n\n"


@app.post("/api/ai/chat")
def chat(req: ChatRequest):
    if req.stream:
        from fastapi.responses import StreamingResponse
        try:
            gen = chat_service.chat_stream(
                req.message, session_id=req.session_id,
                provider_id=req.provider_id, model=req.model)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        def event_stream():
            yield "data: {\"start\": true}\n\n"
            try:
                for delta in gen:
                    yield _sse_format(delta)
                yield "data: [DONE]\n\n"
            except Exception as exc:  # noqa: BLE001
                yield _sse_format(f"\n[stream error] {exc}")
                yield "data: [DONE]\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        result = chat_service.chat(
            req.message, session_id=req.session_id,
            provider_id=req.provider_id, model=req.model)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Provider error: {exc}")
    return result


# ── config ───────────────────────────────────────────────────────────────

@app.get("/api/ai/config")
def get_config() -> dict:
    return chat_service.public_config()


@app.patch("/api/ai/config")
def patch_config(patch: ConfigPatch) -> dict:
    """Merge updates. providers.<id>.api_key='***saved***' keeps stored value."""
    updates = dict(patch.updates)
    prov_updates = updates.pop("providers", None)
    if isinstance(prov_updates, dict) and prov_updates:
        current = dict(chat_service.config.get("providers") or {})
        for pid, pcfg in prov_updates.items():
            entry = dict(current.get(pid) or {})
            key = pcfg.get("api_key")
            if key in (None, "", "***saved***"):
                pcfg.pop("api_key", None)
            else:
                entry["api_key"] = key
            for field_name, value in pcfg.items():
                if field_name != "api_key":
                    entry[field_name] = value
            current[pid] = entry
        updates["providers"] = current
    return chat_service.save_config(updates)


# ── consent ──────────────────────────────────────────────────────────────

@app.get("/api/ai/consent")
def get_consent() -> dict:
    return governance.list_consents()


@app.post("/api/ai/consent/{provider_id}")
def grant_consent(provider_id: str, req: ConsentRequest) -> dict:
    governance.grant_consent(provider_id, note=req.note)
    return {"ok": True}


@app.delete("/api/ai/consent/{provider_id}")
def revoke_consent(provider_id: str) -> dict:
    governance.revoke_consent(provider_id)
    return {"ok": True}


# ── local models ─────────────────────────────────────────────────────────

@app.get("/api/ai/local/catalog")
def local_catalog() -> list:
    return models.catalog()


@app.get("/api/ai/local/downloads")
def local_downloads() -> list:
    return models.snapshot()


@app.post("/api/ai/local/download")
def local_download(req: DownloadRequest) -> dict:
    result = models.start_download(req.model_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404,
                            detail=result.get("error", "unknown model"))
    return result


@app.post("/api/ai/local/cancel/{model_id}")
def local_cancel(model_id: str) -> dict:
    return {"ok": models.cancel_download(model_id)}


@app.delete("/api/ai/local/models/{filename}")
def local_delete(filename: str) -> dict:
    if not models.delete_model(filename):
        raise HTTPException(status_code=404, detail="Unknown model file.")
    return {"ok": True}


@app.on_event("shutdown")
def _cleanup() -> None:  # pragma: no cover
    llamacpp = chat_service.registry.get("llamacpp")
    if llamacpp and hasattr(llamacpp, "unload"):
        llamacpp.unload()


def main() -> None:  # pragma: no cover
    import uvicorn
    log.info("UmerOS AI service listening on http://%s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":  # pragma: no cover
    main()
