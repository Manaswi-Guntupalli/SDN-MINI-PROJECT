#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTROLLER_APP="$ROOT_DIR/controller/qos_priority_controller.py"
EXPERIMENT_SCRIPT="$ROOT_DIR/scripts/sdn_qos_experiment.py"

resolve_ryu_manager() {
    if [[ -x "$ROOT_DIR/.venv/bin/ryu-manager" ]]; then
        echo "$ROOT_DIR/.venv/bin/ryu-manager"
        return 0
    fi

    if [[ -x "$ROOT_DIR/.venv/bin/osken-manager" ]]; then
        echo "$ROOT_DIR/.venv/bin/osken-manager"
        return 0
    fi

    if command -v ryu-manager >/dev/null 2>&1; then
        command -v ryu-manager
        return 0
    fi

    if command -v osken-manager >/dev/null 2>&1; then
        command -v osken-manager
        return 0
    fi

    echo ""
    return 1
}

cd "$ROOT_DIR"

cleanup() {
    if [[ -n "${CONTROLLER_PID:-}" ]]; then
        kill "$CONTROLLER_PID" >/dev/null 2>&1 || true
    fi
    sudo mn -c >/dev/null 2>&1 || true
}

start_controller() {
    local qos_flag="$1"
    QOS_ENABLED="$qos_flag" "$RYU_MANAGER_BIN" "$CONTROLLER_APP" > "artifacts/controller_${qos_flag}.log" 2>&1 &
    CONTROLLER_PID=$!
    sleep 2
}

run_one() {
    local mode="$1"
    local qos_flag="$2"

    echo "[INFO] Running mode: $mode"
    mkdir -p artifacts
    start_controller "$qos_flag"

    sudo -E python3 "$EXPERIMENT_SCRIPT" --mode "$mode" --output-dir artifacts

    kill "$CONTROLLER_PID" >/dev/null 2>&1 || true
    unset CONTROLLER_PID
    sudo mn -c >/dev/null 2>&1 || true
}

trap cleanup EXIT

mkdir -p artifacts

RYU_MANAGER_BIN="$(resolve_ryu_manager || true)"
if [[ -z "$RYU_MANAGER_BIN" ]]; then
    echo "[ERROR] No controller manager found (ryu-manager or osken-manager)."
    echo "[ERROR] Run: bash scripts/setup_env.sh"
    exit 1
fi

if [[ "$MODE" == "baseline" ]]; then
    run_one "baseline" "0"
elif [[ "$MODE" == "qos" ]]; then
    run_one "qos" "1"
elif [[ "$MODE" == "all" ]]; then
    rm -rf artifacts/baseline artifacts/qos
    run_one "baseline" "0"
    run_one "qos" "1"
    python3 "$ROOT_DIR/scripts/compare_latency.py" | tee artifacts/latency_comparison.txt
else
    echo "Usage: $0 [baseline|qos|all]"
    exit 1
fi

echo "[INFO] Demo execution finished. Artifacts are in artifacts/."
