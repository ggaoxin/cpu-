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
