#!/usr/bin/env bash
# mineru-api 守护启动包装：启动前清理 GPU 残留进程并等待显存释放。
# 解决异常崩溃（SIGKILL/OOM）后 CUDA 显存不释放、重启时显存不足的问题。
# supervisor 的 command 指向本脚本（前台 exec，由 supervisor 接管生命周期）。
set -euo pipefail

ENV=/root/autodl-tmp/conda/envs/mineru_vllm
export PATH="$ENV/bin:/usr/local/cuda/bin:$PATH"
export CUDA_HOME=/usr/local/cuda
export MINERU_API_MAX_CONCURRENT_REQUESTS=${MINERU_API_MAX_CONCURRENT_REQUESTS:-8}
PORT=${MINERU_API_PORT:-8899}

# 1. 清理可能的 GPU 残留进程（崩溃留下的孤儿 EngineCore / vllm worker）
#    正常退出不会残留；此处只处理异常崩溃遗留。本脚本启动时不应有合法 mineru-api 在跑。
RESIDUAL_PIDS=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ' | grep -E '^[0-9]+$' || true)
if [ -n "$RESIDUAL_PIDS" ]; then
    echo "[guarded] 发现 GPU 残留进程: $RESIDUAL_PIDS，清理中..."
    for pid in $RESIDUAL_PIDS; do
        kill "$pid" 2>/dev/null || true
    done
    sleep 3
    # 仍未退出则强杀
    for pid in $RESIDUAL_PIDS; do
        kill -9 "$pid" 2>/dev/null || true
    done
    sleep 2
fi

# 2. 等待 GPU 显存释放（free > 20GB 视为可用，最多等 30 秒）
for i in $(seq 1 15); do
    FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
    if [ -n "$FREE" ] && [ "$FREE" -gt 20000 ]; then
        echo "[guarded] GPU 可用 free=${FREE}MiB，启动 mineru-api (port=$PORT)"
        break
    fi
    echo "[guarded] GPU 显存未释放 free=${FREE}MiB，等待... ($i)"
    sleep 2
done

# 3. 前台启动（exec 让 supervisor 直接管理该进程）
exec "$ENV/bin/mineru-api" --host 127.0.0.1 --port "$PORT" --enable-vlm-preload true
