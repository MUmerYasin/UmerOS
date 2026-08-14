import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json

app = FastAPI()

class DriverCommand(BaseModel):
    command: str
    args: list[str] = []

@app.post("/exec")
async def exec_command(cmd: DriverCommand):
    try:
        result = subprocess.run([cmd.command, *cmd.args], capture_output=True, text=True, check=True)
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=400, detail={"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Command not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
