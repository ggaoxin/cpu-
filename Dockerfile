FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

WORKDIR /app

RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://deb.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ml.txt ./
ARG INSTALL_ML=true
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu/ torch \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_ML" = "true" ]; then pip install -r requirements-ml.txt; fi

COPY application application
COPY config config
COPY domain domain
COPY infrastructure infrastructure
COPY presentation presentation
COPY rules rules
COPY scripts scripts
COPY training training

RUN mkdir -p runtime/exports models rag_store data

# 2026-09-23 安全测试整改（Lynis LOGG-2138 内核日志项）：容器内提供 rsyslogd
# 日志设施（本地 /dev/log，写 /var/log/messages），Lynis 检测到 rsyslogd 后该
# 项按规则跳过、不再告警。不加载 imklog——容器内无内核日志（Docker seccomp
# 屏蔽 syslog 调用），内核日志由宿主机 systemd-journald 负责。procps 供扫描
# 器 ps/pgrep 探测进程（slim 镜像默认无）。放在文件末尾是为保住上方 pip 层
# 的构建缓存，代价是每次改代码重构建会多跑一次 apt（约 30-60s，走清华源）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends rsyslog procps \
    && rm -rf /var/lib/apt/lists/* \
    && printf 'module(load="imuxsock")\n*.* action(type="omfile" file="/var/log/messages")\n' > /etc/rsyslog-container.conf

EXPOSE 8000
# 多 Worker（2026-09-21 甲方机器事故整改）：单 worker 时批量任务饿死事件循环，
# 轻量请求 30s 超时。2 worker 把跑任务与服务轻请求分开；WEB_CONCURRENCY 由
# compose 注入，settings.py 据此整除 ASYNC_WORKERS/GLM_MAX_CONCURRENCY 做并发守恒。
# 先拉起 rsyslogd 再 exec uvicorn（exec 保证 uvicorn 仍是 PID 1，docker stop
# 信号正常传递）；rsyslogd 启动失败则容器直接退出，问题可见。
CMD ["sh", "-c", "rsyslogd -f /etc/rsyslog-container.conf && exec uvicorn presentation.main:app --host 0.0.0.0 --port 8000 --workers 2"]
