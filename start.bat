@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM Microfinance AI — Windows Local Dev Startup Script
REM Runs Flask backend (port 5001) + Vite frontend (port 5173) together
REM ─────────────────────────────────────────────────────────────────────────────

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║          MICROFINANCE AI — LOCAL DEV SERVER              ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo   Backend  →  http://localhost:5001
echo   Frontend →  http://localhost:5173
echo.
echo   Close both terminal windows to stop the servers.
echo ══════════════════════════════════════════════════════════════
echo.

REM ── 1. Activate Python virtual environment ──────────────────────────────────
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
    echo [OK] Virtual environment activated: .venv
) else if exist "%~dp0env\Scripts\activate.bat" (
    call "%~dp0env\Scripts\activate.bat"
    echo [OK] Virtual environment activated: env
) else (
    echo [WARNING] No virtual environment found. Using system Python...
)

REM ── 2. Start Flask backend in a new window ──────────────────────────────────
echo.
echo Starting Flask backend...
start "MicrofinanceAI-Backend" cmd /k "cd /d %~dp0 && python app.py"

REM Wait a moment for backend to boot
timeout /t 3 /nobreak >nul

REM ── 3. Start Vite frontend in a new window ──────────────────────────────────
echo Starting Vite frontend...
start "MicrofinanceAI-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ══════════════════════════════════════════════════════════════
echo   Both servers are starting. Open http://localhost:5173
echo ══════════════════════════════════════════════════════════════
echo.
pause
