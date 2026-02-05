#!/bin/zsh
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT" || exit 1

source venv/bin/activate || { echo "❌ venv не найден"; exit 1; }
export PYTHONUNBUFFERED=1

mkdir -p .pids
echo $$ > .pids/worker.pid

echo "⚙️  Запуск Worker..."
python3 src/worker.py
