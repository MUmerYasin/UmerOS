import os
import sys
import subprocess
import time
import httpx
import jwt
from pathlib import Path

# Helper to start the FastAPI app in a subprocess
def start_app():
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "drivers.driver_service:app", "--host", "127.0.0.1", "--port", "8000"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # Wait a moment for the server to start
    time.sleep(3)
    return proc

# Helper to generate a test JWT (HS256) if no JWKS is provided
def generate_test_jwt():
    secret = "test-secret"
    payload = {
        "sub": "test-user",
        "iss": os.getenv("OIDC_ISSUER", "test-issuer"),
        "aud": os.getenv("OIDC_AUDIENCE", "test-audience"),
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token

def main():
    proc = start_app()
    try:
        token = generate_test_jwt()
        headers = {"Authorization": f"Bearer {token}"}
        url = "http://127.0.0.1:8000/cpuinfo"
        resp = httpx.get(url, headers=headers, timeout=10)
        print("Status code:", resp.status_code)
        print("Response JSON:", resp.json())
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
