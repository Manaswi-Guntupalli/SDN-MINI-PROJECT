#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
    python3 -m venv --system-site-packages .venv
fi

source .venv/bin/activate
python3 -m pip install --upgrade pip

if python3 -m pip install -r requirements.txt; then
    echo "[INFO] Ryu installed in virtual environment."
else
    echo "[WARN] Ryu install failed (common on Python 3.12 with legacy Ryu hooks)."
    echo "[WARN] Falling back to OS-Ken system package."
    if ! command -v osken-manager >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y python3-os-ken
    fi
fi

if [[ -x "$ROOT_DIR/.venv/bin/ryu-manager" ]]; then
    MANAGER_BIN="$ROOT_DIR/.venv/bin/ryu-manager"
elif [[ -x "$ROOT_DIR/.venv/bin/osken-manager" ]]; then
    MANAGER_BIN="$ROOT_DIR/.venv/bin/osken-manager"
elif command -v ryu-manager >/dev/null 2>&1; then
    MANAGER_BIN="$(command -v ryu-manager)"
elif command -v osken-manager >/dev/null 2>&1; then
    MANAGER_BIN="$(command -v osken-manager)"
else
    echo "[ERROR] No controller manager found after setup."
    exit 1
fi

echo "[INFO] Virtual environment ready at $ROOT_DIR/.venv"
echo "[INFO] Controller manager path: $MANAGER_BIN"
