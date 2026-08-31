#!/usr/bin/env bash
# AutoDL 实例重启后一键恢复全部服务(容器无 systemd,重启后进程全部丢失)
set -uo pipefail

echo "[1/4] MySQL ..."
if ! mysqladmin ping --silent 2>/dev/null; then
    nohup mysqld --user=root > /tmp/mysqld.log 2>&1 &
    for i in $(seq 1 30); do mysqladmin ping --silent 2>/dev/null && break; sleep 2; done
fi
mysqladmin ping --silent 2>/dev/null && echo "  MySQL OK" || echo "  MySQL 启动失败,查看 /tmp/mysqld.log"

echo "[2/4] mineru-api ..."
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:8899/docs; then
    MINERU_CPU_ENV=/root/autodl-tmp/conda/envs/mineru nohup bash "$(dirname "$0")/mineru_api_cpu.sh" > /tmp/mineru-start.log 2>&1 &
    echo "  mineru 启动中(模型加载约 1-2 分钟,日志 /tmp/mineru-api-cpu.log)"
else
    echo "  mineru OK"
fi

echo "[3/4] FastAPI 后端(8000) ..."
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:8000/docs; then
    cd "$(dirname "$0")/.." && nohup python3 -m uvicorn presentation.main:app --host 0.0.0.0 --port 8000 > /root/autodl-tmp/backend.log 2>&1 &
    for i in $(seq 1 20); do curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/docs && break; sleep 2; done
fi
curl -s -o /dev/null --max-time 3 http://127.0.0.1:8000/docs && echo "  后端 OK" || echo "  后端启动失败,查看 /root/autodl-tmp/backend.log"

echo "[4/4] 前端 Vite(6006) ..."
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:6006/; then
    cd "$(dirname "$0")/../frontend" && nohup npx vite --host 0.0.0.0 --port 6006 > /tmp/vite.log 2>&1 &
    for i in $(seq 1 15); do curl -s -o /dev/null --max-time 2 http://127.0.0.1:6006/ && break; sleep 2; done
fi
curl -s -o /dev/null --max-time 3 http://127.0.0.1:6006/ && echo "  前端 OK" || echo "  前端启动失败,查看 /tmp/vite.log"

echo "完成:MySQL(3306) mineru(8899) 后端(8000) 前端(6006)"
