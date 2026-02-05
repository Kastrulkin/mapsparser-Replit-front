#!/bin/zsh
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT" || exit 1

source venv/bin/activate || { echo "❌ venv не найден"; exit 1; }
export PYTHONUNBUFFERED=1

echo "🚀 Запуск Web API..."
python3 src/main.py
