@echo off
REM ===================================================================
REM  Umer OS — Windows launcher
REM ===================================================================
REM  Starts the UmerOS Python backend and the Flutter desktop
REM  frontend in two separate console windows so they stay up.
REM
REM  Usage:
REM      start.bat            (default: backend + frontend)
REM      start.bat backend    (Python backend only)
REM      start.bat frontend   (Flutter frontend only)
REM
REM  Environment overrides:
REM      UMER_BACKEND_PORT  - port for the FastAPI/Uvicorn backend
REM                            (default 8420)
REM      UMER_FLUTTER_DIR   - path to the Flutter project
REM                            (default ui\flutter_ui)
REM      UMER_PYTHON        - python interpreter to use
REM                            (default: python on PATH)
REM ===================================================================

setlocal EnableExtensions EnableDelayedExpansion

REM ----- Defaults --------------------------------------------------------
if not defined UMER_BACKEND_PORT set "UMER_BACKEND_PORT=8420"
if not defined UMER_FLUTTER_DIR  set "UMER_FLUTTER_DIR=ui\flutter_ui"
if not defined UMER_PYTHON       set "UMER_PYTHON=python"

REM ----- Resolve repo root ----------------------------------------------
set "UMER_ROOT=%~dp0"
if "%UMER_ROOT:~-1%"=="\" set "UMER_ROOT=%UMER_ROOT:~0,-1%"

REM ----- Mode ------------------------------------------------------------
set "UMER_MODE=%~1"
if "%UMER_MODE%"=="" set "UMER_MODE=both"

echo ============================================
echo   UmerOS - launcher (mode=%UMER_MODE%)
echo ============================================
echo   Repo root:      %UMER_ROOT%
echo   Backend port:   %UMER_BACKEND_PORT%
echo   Flutter dir:    %UMER_ROOT%\%UMER_FLUTTER_DIR%
echo.

REM ----- Backend ---------------------------------------------------------
if /I "%UMER_MODE%"=="both" goto :start_backend
if /I "%UMER_MODE%"=="backend" goto :start_backend
goto :skip_backend

:start_backend
echo [1/2] Starting UmerOS Python backend on port %UMER_BACKEND_PORT%...
start "UmerOS Backend" /D "%UMER_ROOT%" cmd /k ^
  "set PYTHONPATH=%UMER_ROOT%&& %UMER_PYTHON% -m uvicorn quantum.quantum_server:app --host 0.0.0.0 --port %UMER_BACKEND_PORT% --log-config uvicorn_logger.json"
echo   waiting for backend to bind...
timeout /t 3 /nobreak >nul
goto :after_backend

:skip_backend
echo [skip] Backend launch skipped (mode=%UMER_MODE%)

:after_backend

REM ----- Frontend --------------------------------------------------------
if /I "%UMER_MODE%"=="both" goto :start_frontend
if /I "%UMER_MODE%"=="frontend" goto :start_frontend
goto :skip_frontend

:start_frontend
echo [2/2] Starting Flutter desktop frontend...
start "UmerOS Frontend" /D "%UMER_ROOT%\%UMER_FLUTTER_DIR%" cmd /k ^
  "flutter run -d windows"
goto :after_frontend

:skip_frontend
echo [skip] Frontend launch skipped (mode=%UMER_MODE%)

:after_frontend

echo.
echo UmerOS services are starting.  Close this window or press
echo Ctrl+C in each service window to stop them.
echo.
echo   Backend health: http://localhost:%UMER_BACKEND_PORT%/health
echo.
endlocal
pause
