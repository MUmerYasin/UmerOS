#!/usr/bin/env bash
# ====================================================================
#  Umer OS — POSIX launcher (macOS / Linux)
# ====================================================================
#  Starts the UmerOS Python backend and the Flutter desktop
#  frontend in two background processes.
#
#  Usage:
#      ./start.sh                 (default: backend + frontend)
#      ./start.sh backend         (Python backend only)
#      ./start.sh frontend        (Flutter frontend only)
#      ./start.sh stop            (stop any running services)
#
#  Environment overrides:
#      UMER_BACKEND_PORT  - port for the FastAPI/Uvicorn backend
#                            (default 8420)
#      UMER_FLUTTER_DIR   - path to the Flutter project
#                            (default ui/flutter_ui)
#      UMER_PYTHON        - python interpreter to use
#                            (default: python3)
# ====================================================================

set -euo pipefail

# ----- Defaults --------------------------------------------------------
: "${UMER_BACKEND_PORT:=8420}"
: "${UMER_FLUTTER_DIR:=ui/flutter_ui}"
: "${UMER_PYTHON:=python3}"

# ----- Resolve repo root ----------------------------------------------
UMER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${UMER_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

PID_DIR="${UMER_ROOT}/.run"
mkdir -p "${PID_DIR}"

# ----- Mode ------------------------------------------------------------
MODE="${1:-both}"

start_backend() {
  echo "[1/2] Starting UmerOS Python backend on port ${UMER_BACKEND_PORT}..."
  nohup "${UMER_PYTHON}" -m uvicorn quantum.quantum_server:app \
      --host 0.0.0.0 \
      --port "${UMER_BACKEND_PORT}" \
      --log-config "${UMER_ROOT}/uvicorn_logger.json" \
      >"${PID_DIR}/backend.log" 2>&1 &
  echo $! >"${PID_DIR}/backend.pid"
  echo "    pid: $(cat "${PID_DIR}/backend.pid")  log: ${PID_DIR}/backend.log"
  sleep 2
}

start_frontend() {
  echo "[2/2] Starting Flutter desktop frontend..."
  nohup flutter run -d "$(uname -s | tr '[:upper:]' '[:lower:]')" \
      >"${PID_DIR}/frontend.log" 2>&1 &
  echo $! >"${PID_DIR}/frontend.pid"
  echo "    pid: $(cat "${PID_DIR}/frontend.pid")  log: ${PID_DIR}/frontend.log"
}

stop_services() {
  for svc in backend frontend; do
    pidfile="${PID_DIR}/${svc}.pid"
    if [[ -f "${pidfile}" ]]; then
      pid="$(cat "${pidfile}" 2>/dev/null || true)"
      if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
        echo "Stopping ${svc} (pid ${pid})..."
        kill "${pid}" || true
        sleep 1
        kill -9 "${pid}" 2>/dev/null || true
      fi
      rm -f "${pidfile}"
    fi
  done
}

case "${MODE}" in
  both)
    start_backend
    start_frontend
    ;;
  backend)
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  stop)
    stop_services
    exit 0
    ;;
  *)
    echo "Usage: $0 [both|backend|frontend|stop]" >&2
    exit 2
    ;;
esac

cat <<EOF

UmerOS services are starting.  Stop with:
  $0 stop

  Backend health: http://localhost:${UMER_BACKEND_PORT}/health
  Backend log:    ${PID_DIR}/backend.log
  Frontend log:   ${PID_DIR}/frontend.log
EOF
