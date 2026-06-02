#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Microfinance AI — Local Dev Startup Script
# Runs Flask backend (port 5001) + Vite frontend (port 5173) together
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          MICROFINANCE AI — LOCAL DEV SERVER              ║"
echo "╔══════════════════════════════════════════════════════════╗"
echo ""
echo "  Backend  →  http://localhost:5001"
echo "  Frontend →  http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo "══════════════════════════════════════════════════════════════"
echo ""

# ── 1. Activate Python virtual environment ──────────────────────────────────
VENV_DIR="$PROJECT_DIR/env"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    echo "✅  Virtual environment activated: $VENV_DIR"
else
    echo "⚠️   No 'env' virtual environment found. Trying system Python..."
fi

# ── 2. Load backend .env ────────────────────────────────────────────────────
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a          # auto-export all variables
    source "$PROJECT_DIR/.env"
    set +a
    echo "✅  Backend .env loaded"
fi

# ── 3. Start Flask backend in background ───────────────────────────────────
echo ""
echo "🚀  Starting Flask backend..."
cd "$PROJECT_DIR"
python app.py &
BACKEND_PID=$!
echo "    Backend PID: $BACKEND_PID"

# Wait a moment for backend to boot
sleep 2

# ── 4. Start Vite frontend in background ───────────────────────────────────
echo ""
echo "🚀  Starting Vite frontend (using .env.local for local API URL)..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo "    Frontend PID: $FRONTEND_PID"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Both servers are running. Open http://localhost:5173"
echo "══════════════════════════════════════════════════════════════"
echo ""

# ── 5. Wait — kill both if Ctrl+C ──────────────────────────────────────────
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait $BACKEND_PID $FRONTEND_PID
