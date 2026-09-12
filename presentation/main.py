"""应用入口：创建 FastAPI 应用并挂载 v1 路由。

启动：
    uvicorn presentation.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from infrastructure.database.connection import database
from presentation.api.v1.router import router as v1_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings.ensure_ready()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.DATABASE_AUTO_CREATE:
            try:
                database.initialize()
                logging.getLogger(__name__).info("数据库结构初始化完成：%s", database.dialect)
            except Exception:
                logging.getLogger(__name__).exception("数据库初始化失败")
                if settings.DATABASE_REQUIRED:
                    raise
        # mineru-api 常驻服务健康检查（不阻塞启动，不可用时文件解析降级 pdfplumber）
        try:
            from infrastructure.document_parser.mineru_api_client import mineru_api_client
            if mineru_api_client.healthy():
                logging.getLogger(__name__).info(
                    "mineru-api 常驻服务就绪：%s (backend=%s)", settings.MINERU_API_URL, settings.MINERU_BACKEND)
            else:
                logging.getLogger(__name__).warning(
                    "mineru-api 不可用(%s)，文件解析将降级 pdfplumber", settings.MINERU_API_URL)
        except Exception:
            logging.getLogger(__name__).warning("mineru-api 健康检查异常，文件解析将降级 pdfplumber", exc_info=True)
        # GIL 切换间隔：默认 5ms 在 6+ 线程并发时切换开销 3×（实测纯 CPU 3 任务
        # 串行 1.5s vs 3 线程 5.0s）。增大到 50ms 减少无谓切换，让 IO 等待的线程
        # 能拿到更长的 CPU 量子。零功能影响。
        import sys as _sys
        _sys.setswitchinterval(0.05)
        # bge-m3 / bge-large-zh 预热：懒加载在首个请求线程触发（CPU ~30s），
        # 批量并发线程排队等锁——实测 en-keyword 6 篇卡 39s 空转的根因。
        # 启动后台线程预热，批量首个请求零等待
        import threading as _threading

        def _warm_encoders():
            try:
                from infrastructure.rag.m3_encoder import m3_encoder
                m3_encoder.encode(["预热"])
                logging.getLogger(__name__).info("bge-m3 编码器预热完成")
            except Exception:
                logging.getLogger(__name__).warning("bge-m3 预热失败（首次使用时再懒加载）", exc_info=True)
            try:
                from infrastructure.rag.clc_retriever import clc_retriever
                clc_retriever._ensure_loaded()
                clc_retriever._ensure_m3_loaded()
                logging.getLogger(__name__).info("CLC 检索索引预热完成")
            except Exception:
                logging.getLogger(__name__).warning("CLC 索引预热失败", exc_info=True)

        _threading.Thread(target=_warm_encoders, name="encoder-warmup", daemon=True).start()
        yield

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="面向科技文献全生命周期的语义计算工具库（10 功能项 / 19 功能点）",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- API Key 鉴权（2026-09-12，默认关闭不影响现有使用）----
    # 开启：config/.env 设 API_AUTH_ENABLED=true + API_KEYS=key1,key2
    # 请求头 X-API-Key 携带任一密钥即通过；/health 与 /docs 系列豁免。
    if settings.API_AUTH_ENABLED:
        _PUBLIC_PATHS = ("/health", "/docs", "/openapi.json", "/redoc")

        @app.middleware("http")
        async def api_key_guard(request, call_next):
            if request.url.path.startswith(_PUBLIC_PATHS):
                return await call_next(request)
            provided = request.headers.get("X-API-Key", "")
            if provided and provided in settings.API_KEYS:
                return await call_next(request)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"code": 40101, "message": "未授权：缺少或无效的 X-API-Key 请求头"},
            )

    @app.get("/health", tags=["系统"])
    def health() -> dict:
        db = database.healthcheck()
        return {
            "status": "ok" if db.get("connected") else "degraded",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "llm_configured": settings.llm_configured,
            "llm_required_for_model_tools": True,
            "llm_required_at_startup": settings.GLM_REQUIRED_AT_STARTUP,
            "llm_model": settings.GLM_MODEL,
            "database": db,
        }

    app.include_router(v1_router, prefix=settings.API_PREFIX)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("presentation.main:app", host="0.0.0.0", port=8000, reload=True)
