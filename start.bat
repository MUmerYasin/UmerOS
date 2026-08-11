@echo off
echo ============================================
echo   UmerOS - Starting Backend + Frontend
echo ============================================
echo.

:: Start Python backend
echo [1/2] Starting Python quantum server on port 8420...
start "UmerOS Backend" cmd /k "cd /d F:\Pension Person Details\UmerOS\quantum && python -m uvicorn quantum_server:app --host 0.0.0.0 --port 8420 --reload"

:: Wait for server to be ready
echo [2/2] Waiting for backend to start...
timeout /t 3 /nobreak >nul

:: Start Flutter app
echo Starting Flutter desktop app...
start "UmerOS Frontend" cmd /k "cd /d F:\Pension Person Details\UmerOS\ui\flutter_ui && flutter run -d windows"

echo.
echo Both services are starting.
echo   Backend:  http://localhost:8420/health
echo   Frontend: Flutter desktop window
echo.
echo Close this window or press Ctrl+C to stop.
pause
