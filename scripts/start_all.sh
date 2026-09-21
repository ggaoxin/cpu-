#!/usr/bin/env bash
# AutoDL 实例重启后一键恢复全部服务(容器无 systemd,重启后进程全部丢失)
set -uo pipefail

echo "[1/4] MySQL ..."
if ! mysqladmin ping --silent 2>/dev/null; then
    setsid nohup mysqld --user=root > /tmp/mysqld.log 2>&1 &
    for i in $(seq 1 30); do mysqladmin ping --silent 2>/dev/null && break; sleep 2; done
fi
mysqladmin ping --silent 2>/dev/null && echo "  MySQL OK" || echo "  MySQL 启动失败,查看 /tmp/mysqld.log"

echo "[2/4] mineru-api ..."
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:8899/docs; then
    MINERU_CPU_ENV=/root/autodl-tmp/conda/envs/mineru setsid nohup bash "$(dirname "$0")/mineru_api_cpu.sh" > /tmp/mineru-start.log 2>&1 &
    echo "  mineru 启动中(模型加载约 1-2 分钟,日志 /tmp/mineru-api-cpu.log)"
else
    echo "  mineru OK"
fi

echo "[3/4] FastAPI 后端(8000) ..."
# RESTART_BACKEND=1: 强制重启后端。多 worker 模式下 uvicorn 父进程被 kill 后,
# spawn 出的子进程会以孤儿进程继续占着 8000 端口跑旧代码(表现为"改了代码不生效"、
# 502),必须按端口把父+子进程全部清掉再启动。
if [ "${RESTART_BACKEND:-0}" = "1" ]; then
    PIDS=$(ss -ltnp 2>/dev/null | awk '/:8000 /{print $NF}' | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u)
    if [ -n "$PIDS" ]; then
        echo "  清理 8000 端口旧进程: $PIDS"
        kill -9 $PIDS 2>/dev/null || true
        sleep 2
    fi
fi
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:8000/docs; then
    cd "$(dirname "$0")/.." && WEB_CONCURRENCY="${BACKEND_WORKERS:-2}" setsid nohup python3 -m uvicorn presentation.main:app --workers "${BACKEND_WORKERS:-2}" --host 0.0.0.0 --port 8000 > /root/autodl-tmp/backend.log 2>&1 &
    for i in $(seq 1 20); do curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/docs && break; sleep 2; done
fi
curl -s -o /dev/null --max-time 3 http://127.0.0.1:8000/docs && echo "  后端 OK" || echo "  后端启动失败,查看 /root/autodl-tmp/backend.log"

echo "[4/4] 前端 Vite(6006) ..."
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:6006/; then
    cd "$(dirname "$0")/../frontend" && setsid nohup npx vite --host 0.0.0.0 --port 6006 > /tmp/vite.log 2>&1 &
    for i in $(seq 1 15); do curl -s -o /dev/null --max-time 2 http://127.0.0.1:6006/ && break; sleep 2; done
fi
curl -s -o /dev/null --max-time 3 http://127.0.0.1:6006/ && echo "  前端 OK" || echo "  前端启动失败,查看 /tmp/vite.log"

echo "完成:MySQL(3306) mineru(8899) 后端(8000) 前端(6006)"
