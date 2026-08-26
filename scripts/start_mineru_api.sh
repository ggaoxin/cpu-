#!/usr/bin/env bash
# 启动 mineru-api 常驻服务（vllm-engine 后端，预加载模型）。
# 生产环境推荐用 supervisor 守护（见 config/supervisor/），本脚本供手动/调试用。
#
# 用法：bash scripts/start_mineru_api.sh [--foreground]
#   --foreground 前台运行（不 detach，便于看日志）

set -euo pipefail

ENV=/root/autodl-tmp/conda/envs/mineru_vllm
PORT=${MINERU_API_PORT:-8899}

# flashinfer JIT 需要 ninja（conda bin）+ nvcc（cuda bin）
export PATH="$ENV/bin:/usr/local/cuda/bin:$PATH"
export CUDA_HOME=/usr/local/cuda
export MINERU_API_MAX_CONCURRENT_REQUESTS=${MINERU_API_MAX_CONCURRENT_REQUESTS:-8}

CMD=("$ENV/bin/mineru-api" --host 127.0.0.1 --port "$PORT" --enable-vlm-preload true)

if [[ "${1:-}" == "--foreground" ]]; then
    echo "[mineru-api] 前台启动 port=$PORT ..."
    exec "${CMD[@]}"
else
    echo "[mineru-api] 后台启动 port=$PORT (日志 /tmp/mineru-api.log)"
    nohup "${CMD[@]}" > /tmp/mineru-api.log 2>&1 &
    echo "[mineru-api] PID=$! 等待就绪..."
    for i in $(seq 1 30); do
        sleep 3
        if curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
            echo "[mineru-api] 就绪 (port=$PORT)"
            exit 0
        fi
        echo "  等待中... ($i)"
    done
    echo "[mineru-api] 未就绪，查看 /tmp/mineru-api.log" >&2
    exit 1
fi
