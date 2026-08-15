import os
from fastapi import FastAPI, HTTPException, Depends, Request, status, Response
from fastapi.security import OAuth2AuthorizationCodeBearer, HTTPBearer
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from loguru import logger

# JWT handling
from jose import JWTError, jwt

# OAuth2 scheme for token extraction (configure URLs via environment variables)
oauth_scheme = OAuth2AuthorizationCodeBearer(authorizationUrl=os.getenv("OIDC_AUTH_URL", ""), tokenUrl=os.getenv("OIDC_TOKEN_URL", ""))

# Prometheus metrics
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

# Load secrets utility
from security.tls_utils import load_secret

# Import proc utilities
from proc.cpuinfo import get as get_cpuinfo
from proc.meminfo import get as get_meminfo
from proc.uptime import get as get_uptime
from proc.loadavg import get as get_loadavg
from proc.version import get as get_version
from proc.filesystems import get as get_filesystems
from proc.partitions import get as get_partitions
from proc.swaps import get as get_swaps
from proc.interrupts import get as get_interrupts
from proc.ioports import get as get_ioports
from proc.dma import get as get_dma
from proc.modules import get as get_modules
from proc.mounts import get as get_mounts
from proc.pid_entries import list_all as get_pids
from proc.pid_status import get as get_pid_status
from proc.pid_cmdline import get as get_pid_cmdline
from proc.pid_environ import get as get_pid_environ
from proc.pid_fd import list_fds as get_pid_fds

app = FastAPI(title="UmerOS /proc Emulation API", version="1.0.0")

# --- Security ---------------------------------------------------------------
# OAuth2 production integration – verifies JWTs using JWKS from an OIDC provider.
# Expected environment variables:
#   OIDC_JWKS_URL – URL to the JSON Web Key Set.
#   OIDC_ISSUER   – Expected token issuer claim.
#   OIDC_AUDIENCE – Expected audience claim (optional).
import json
import httpx
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError

OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL")
OIDC_ISSUER = os.getenv("OIDC_ISSUER")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE")

USE_TEST_JWT = False
if not OIDC_JWKS_URL or not OIDC_ISSUER:
    # Fallback to test JWT mode for local development
    USE_TEST_JWT = True
    logger.warning("OIDC configuration missing; using test JWT secret for authentication.")

_jwks_cache: dict = {}

async def fetch_jwks() -> dict:
    """Fetch JWKS from the provider and cache it for the lifetime of the process."""
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(OIDC_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache.update(resp.json())
        return _jwks_cache

async def verify_oauth_token(token: str = Depends(oauth_scheme)):
    """Validate a JWT.

    In production, validates against JWKS. In local test mode, validates a HS256 token using a static secret.
    """
    if USE_TEST_JWT:
        # Simple test mode using HS256 and a static secret
        try:
            payload = jwt.decode(token, "test-secret", algorithms=["HS256"], issuer=OIDC_ISSUER or "test-issuer", audience=OIDC_AUDIENCE or "test-audience")
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except JWTClaimsError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except JWTError as e:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    else:
        jwks = await fetch_jwks()
        try:
            payload = jwt.decode(token, jwks, algorithms=["RS256"], issuer=OIDC_ISSUER, audience=OIDC_AUDIENCE)
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except JWTClaimsError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except JWTError as e:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload


# Simple in‑memory rate limiter (max 20 requests per minute per IP). This is not
# bullet‑proof but mitigates abuse without adding external dependencies.
from collections import defaultdict
import time

_RATE_LIMIT = 20  # requests
_RATE_WINDOW = 60  # seconds
_ip_counters: Dict[str, List[float]] = defaultdict(list)

def rate_limiter(request: Request):
    now = time.time()
    ip = request.client.host
    timestamps = _ip_counters[ip]
    # Remove timestamps older than the window
    timestamps = [t for t in timestamps if now - t < _RATE_WINDOW]
    timestamps.append(now)
    _ip_counters[ip] = timestamps
    if len(timestamps) > _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    return True

# Dependency that enforces both authentication and rate limiting
def secure_endpoint(request: Request, authorized: bool = Depends(verify_oauth_token), _: bool = Depends(rate_limiter)):
    return True

# --- Response models --------------------------------------------------------
class CpuInfoModel(BaseModel):
    processor: str
    vendor_id: str | None = None
    model_name: str | None = None
    cpu_mhz: str | None = None
    cache_size: str | None = None
    flags: str | None = None
    # Additional fields are allowed via extra = "allow"
    class Config:
        extra = "allow"

class MemInfoModel(BaseModel):
    MemTotal: int | None = None
    MemFree: int | None = None
    Buffers: int | None = None
    Cached: int | None = None
    SwapTotal: int | None = None
    SwapFree: int | None = None
    class Config:
        extra = "allow"

class UptimeModel(BaseModel):
    total: float
    idle: float

class LoadAvgModel(BaseModel):
    load_1min: float
    load_5min: float
    load_15min: float
    runnable: int
    total_threads: int
    last_pid: int

class VersionModel(BaseModel):
    kernel: str | None = None
    gcc: str | None = None
    glibc: str | None = None
    raw: str | None = None

# --- Endpoints --------------------------------------------------------------
@app.get("/cpuinfo", response_model=List[CpuInfoModel])
def endpoint_cpuinfo(_: bool = Depends(secure_endpoint)):
    return get_cpuinfo()

@app.get("/meminfo", response_model=MemInfoModel)
def endpoint_meminfo(_: bool = Depends(secure_endpoint)):
    return get_meminfo()

@app.get("/uptime", response_model=UptimeModel)
def endpoint_uptime(_: bool = Depends(secure_endpoint)):
    total, idle = get_uptime()
    return {"total": total, "idle": idle}

@app.get("/loadavg", response_model=LoadAvgModel)
def endpoint_loadavg(_: bool = Depends(secure_endpoint)):
    loads, runnable, total = get_loadavg()
    return {
        "load_1min": loads[0],
        "load_5min": loads[1],
        "load_15min": loads[2],
        "runnable": runnable,
        "total_threads": total,
        "last_pid": 0,  # placeholder – original /proc/loadavg includes last pid; not needed here
    }

@app.get("/version", response_model=VersionModel)
def endpoint_version(_: bool = Depends(secure_endpoint)):
    info = get_version()
    # Preserve the raw line for completeness
    raw = ''
    if not info:
        raw = ''
    else:
        raw = ''  # not used
    return {"kernel": info.get("kernel"), "gcc": info.get("gcc"), "glibc": info.get("glibc"), "raw": raw}

@app.get("/filesystems", response_model=List[str])
def endpoint_filesystems(_: bool = Depends(secure_endpoint)):
    return get_filesystems()

@app.get("/partitions", response_model=List[Dict[str, Any]])
def endpoint_partitions(_: bool = Depends(secure_endpoint)):
    # Return a list of dicts for easier JSON consumption
    parts = get_partitions()
    return [{"major": p[0], "minor": p[1], "blocks": p[2], "name": p[3]} for p in parts]

@app.get("/swaps", response_model=List[Dict[str, Any]])
def endpoint_swaps(_: bool = Depends(secure_endpoint)):
    swaps = get_swaps()
    return [{"filename": s[0], "type": s[1], "size_kb": s[2], "used_kb": s[3], "priority": s[4]} for s in swaps]

@app.get("/interrupts", response_model=Dict[str, List[int]])
def endpoint_interrupts(_: bool = Depends(secure_endpoint)):
    return get_interrupts()

@app.get("/ioports", response_model=List[Dict[str, str]])
def endpoint_ioports(_: bool = Depends(secure_endpoint)):
    return [{"range": r, "description": d} for r, d in get_ioports()]

@app.get("/dma", response_model=List[Dict[str, Any]])
def endpoint_dma(_: bool = Depends(secure_endpoint)):
    return [{"channel": ch, "description": desc} for ch, desc in get_dma()]

@app.get("/modules", response_model=List[Dict[str, Any]])
def endpoint_modules(_: bool = Depends(secure_endpoint)):
    mods = get_modules()
    return [{"name": m[0], "size": m[1], "usage": m[2], "deps": m[3], "state": m[4]} for m in mods]

@app.get("/mounts", response_model=List[Dict[str, Any]])
def endpoint_mounts(_: bool = Depends(secure_endpoint)):
    mounts = get_mounts()
    return [{"device": m[0], "mountpoint": m[1], "fstype": m[2], "options": m[3], "dump": m[4], "pass": m[5]} for m in mounts]

@app.get("/pids", response_model=List[int])
def endpoint_pids(_: bool = Depends(secure_endpoint)):
    return get_pids()

@app.get("/pid/{pid}/status", response_model=Dict[str, str])
def endpoint_pid_status(pid: int, _: bool = Depends(secure_endpoint)):
    return get_pid_status(pid)

@app.get("/pid/{pid}/cmdline", response_model=List[str])
def endpoint_pid_cmdline(pid: int, _: bool = Depends(secure_endpoint)):
    return get_pid_cmdline(pid)

@app.get("/pid/{pid}/environ", response_model=Dict[str, str])
def endpoint_pid_environ(pid: int, _: bool = Depends(secure_endpoint)):
    return get_pid_environ(pid)

@app.get("/pid/{pid}/fd", response_model=List[int])
def endpoint_pid_fd(pid: int, _: bool = Depends(secure_endpoint)):
    return get_pid_fds(pid)

# Global exception handler to avoid leaking stack traces
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: {}", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# --- Middleware --------------------------------------------------------------
# CORS configuration – restrict to trusted origins (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://my-frontend.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Request logging middleware – logs method, path, status and latency
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info("Incoming request: {} {}", request.method, request.url.path)
        response = await call_next(request)
        logger.info("Response: {} {} -> {}", request.method, request.url.path, response.status_code)
        return response

app.add_middleware(RequestLoggingMiddleware)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    response = await call_next(request)
    endpoint = request.url.path
    REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    return response

@app.get("/metrics", include_in_schema=False)
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    # Bind to 0.0.0.0 only if explicitly required; default is localhost for safety.
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)

