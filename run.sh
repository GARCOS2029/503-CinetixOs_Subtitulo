#!/bin/bash
# ============================================================
# CinetixOS 503 — Subtitulos para proyeccion (macOS)
# Zero-Cloud / Local-First ($0.00)
# ============================================================

set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🎬 ========================================================"
echo "   CINETIXOS 503 — SUBTITULOS PARA PROYECCION"
echo "   Modo: Zero-Cloud / Local-First (\$0.00)"
echo "============================================================"

PYTHON_BIN=""
if [ -f "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12" ]; then
    PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
elif command -v python3.12 &> /dev/null; then
    PYTHON_BIN="$(command -v python3.12)"
elif command -v python3 &> /dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ No se encontro Python 3.12 en el sistema."
    exit 1
fi

if ! command -v ffmpeg &> /dev/null; then
    echo "❌ Falta ffmpeg. Instalalo con: brew install ffmpeg"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "📦 Creando entorno virtual aislado (.venv)..."
    "$PYTHON_BIN" -m venv --system-site-packages .venv
fi
source .venv/bin/activate

echo "📦 Verificando dependencias en .venv..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo "🧠 Comprobando Ollama (traduccion local)..."
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama no responde. Arrancalo con 'ollama serve' para la traduccion."
else
    echo "✓ Ollama activo."
fi

PORT=5030
echo "🚀 Arrancando servidor local en http://127.0.0.1:${PORT}"
lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true
(sleep 2 && open "http://127.0.0.1:${PORT}") &

exec python -m uvicorn backend.app:app --host 127.0.0.1 --port ${PORT} --reload
