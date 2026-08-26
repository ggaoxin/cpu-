#!/usr/bin/env bash
# mineru-api CPU 版启动脚本（pipeline 后端，onnxruntime，不依赖 vllm/GPU）。
# 与 GPU 版 mineru_api_guarded.sh 的差异：
#   1) 不清 GPU 残留进程 / 不等显存释放（无 GPU）
#   2) 不传 --enable-vlm-preload（无 vllm，不预加载 VLM 模型）
#   3) conda 环境改为 mineru_cpu（甲方自建，pip install "mineru[core,pipeline]" 不带 vllm）
# 用法：bash scripts/mineru_api_cpu.sh [--foreground]
#   生产用 supervisor 守护（见 config/supervisor/mineru-api-cpu.conf）

set -euo pipefail

# ⚠️ 甲方部署时按实际 conda 环境路径改 ENV
ENV=${MINERU_CPU_ENV:-/root/autodl-tmp/conda/envs/mineru_cpu}
export PATH="$ENV/bin:$PATH"
export MINERU_API_MAX_CONCURRENT_REQUESTS=${MINERU_API_MAX_CONCURRENT_REQUESTS:-3}   # CPU 并发调低
# onnxruntime/torch CPU 线程数：留 2 核给后端(uvicorn)+GLM(httpx IO)。
# 8 核机设 4，16 核机设 6-8。过大抢核反慢，过小单请求慢。
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-4}
PORT=${MINERU_API_PORT:-8899}

# 不带 --enable-vlm-preload（CPU pipeline 无需加载 vllm VLM）
CMD=("$ENV/bin/mineru-api" --host 127.0.0.1 --port "$PORT")

if [[ "${1:-}" == "--foreground" ]]; then
    echo "[mineru-api-cpu] 前台启动 port=$PORT (backend=pipeline) ..."
    exec "${CMD[@]}"
else
    echo "[mineru-api-cpu] 后台启动 port=$PORT (backend=pipeline, 日志 /tmp/mineru-api-cpu.log)"
    nohup "${CMD[@]}" > /tmp/mineru-api-cpu.log 2>&1 &
    echo "[mineru-api-cpu] PID=$! 等待就绪..."
    for i in $(seq 1 40); do
        sleep 3
        if curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
            echo "[mineru-api-cpu] 就绪 (port=$PORT)"
            exit 0
        fi
        echo "  等待中... ($i)"
    done
    echo "[mineru-api-cpu] 未就绪，查看 /tmp/mineru-api-cpu.log" >&2
    exit 1
fi
