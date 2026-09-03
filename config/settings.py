"""全局配置：从环境变量 / .env 加载 GLM 大模型连接信息。

设计说明：
- 所有敏感信息（API Key）只存放于 config/.env，已在 .gitignore 中排除。
- 业务代码统一通过 ``settings`` 单例读取配置，避免硬编码。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# 项目根目录：config/settings.py -> 上两层即为项目根
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = PROJECT_ROOT / "rules"

# 加载 .env
load_dotenv(PROJECT_ROOT / "config" / ".env")


def _path(env_key: str, default: Path) -> Path:
    """从环境变量读路径（支持 .env 覆盖），无则用项目根相对默认值。"""
    v = os.getenv(env_key)
    return Path(v) if v else default


class Settings:
    """应用配置单例。"""

    # ---- GLM 大模型 ----
    GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
    GLM_BASE_URL: str = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    GLM_MODEL: str = os.getenv("GLM_MODEL", "glm-5.2")
    GLM_TEMPERATURE: float = float(os.getenv("GLM_TEMPERATURE", "0.1"))
    GLM_CONNECT_TIMEOUT_SECONDS: float = max(1.0, float(os.getenv("GLM_CONNECT_TIMEOUT_SECONDS", "8")))
    GLM_REQUIRED_AT_STARTUP: bool = os.getenv("GLM_REQUIRED_AT_STARTUP", "false").lower() == "true"
    # 用户上传资源 LLM 结构整理（上传时一次性转换；确定性归一化 0 条时触发）
    RESOURCE_LLM_NORMALIZE_ENABLED: bool = os.getenv("RESOURCE_LLM_NORMALIZE_ENABLED", "true").lower() == "true"
    RESOURCE_LLM_NORMALIZE_MAX_BYTES: int = int(os.getenv("RESOURCE_LLM_NORMALIZE_MAX_BYTES", str(512 * 1024)))
    RESOURCE_LLM_NORMALIZE_MAX_ROWS: int = int(os.getenv("RESOURCE_LLM_NORMALIZE_MAX_ROWS", "2000"))

    # ---- 应用 ----
    APP_NAME: str = "语义计算工具库"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    DEFAULT_WORKSPACE_ID: str = os.getenv("DEFAULT_WORKSPACE_ID", "default")
    MODEL_VERSION: str = os.getenv("MODEL_VERSION", "semantic-toolkit-2026.08")

    # ---- 数据库 ----
    # 生产环境使用 MySQL 8：mysql+pymysql://user:password@mysql:3306/semantic_toolkit
    # 本地没有 MySQL 时默认使用 SQLite，接口与仓储行为保持一致，便于开发和自动测试。
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(PROJECT_ROOT / 'runtime' / 'semantic_toolkit.db').as_posix()}",
    )
    DATABASE_AUTO_CREATE: bool = os.getenv("DATABASE_AUTO_CREATE", "true").lower() == "true"
    DATABASE_REQUIRED: bool = os.getenv("DATABASE_REQUIRED", "false").lower() == "true"
    ASYNC_WORKERS: int = max(1, int(os.getenv("ASYNC_WORKERS", "4")))
    # 逐篇工具批量执行时单任务的 GLM 并发数上限；同时受进程级 _GLM_SEMAPHORE 约束，
    # 多个批量任务同时运行时全进程在途 GLM 调用总数不超过此值。
    # 实测单篇语步识别 GLM 约 3-5s；GLM QPS 通常 5-10，默认 6 偏保守。
    # 遇 429 限流下调到 3-4，QPS 充裕上调到 8-10。
    GLM_MAX_CONCURRENCY: int = max(1, int(os.getenv("GLM_MAX_CONCURRENCY", "6")))

    # ---- Web / 上传 ----
    CORS_ORIGINS: List[str] = [
        value.strip()
        for value in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:6006,http://localhost:6006,http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if value.strip()
    ]
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    # 批量文件单次提交数量上限（在线测试与 API 一致）
    MAX_BATCH_FILES: int = int(os.getenv("MAX_BATCH_FILES", "20"))

    # ---- 路径（全部 PROJECT_ROOT 相对，可被 .env 覆盖；项目自包含）----
    PROJECT_ROOT: Path = PROJECT_ROOT
    RULES_DIR: Path = RULES_DIR
    DATA_DIR: Path = _path("DATA_DIR", PROJECT_ROOT / "data" / "datasets")          # 数据集
    NER_GOLD_DIR: Path = _path("NER_GOLD_DIR", PROJECT_ROOT / "data" / "ner")        # NER gold
    RAG_STORE_DIR: Path = _path("RAG_STORE_DIR", PROJECT_ROOT / "rag_store")        # RAG 存储
    CLC_RAG_DIR: Path = _path("CLC_RAG_DIR", PROJECT_ROOT / "rag_store" / "clc_rag")
    CLC_META_FULL: Path = _path("CLC_META_FULL", CLC_RAG_DIR / "clc_meta_full.json")
    CLC_INDEX_LARGE: Path = _path("CLC_INDEX_LARGE", CLC_RAG_DIR / "clc_index_large")
    CLC_INDEX_M3: Path = _path("CLC_INDEX_M3", CLC_RAG_DIR / "clc_index_m3")
    MODELS_DIR: Path = _path("MODELS_DIR", PROJECT_ROOT / "models")                  # bge 权重
    BGE_SMALL_PATH: Path = _path("BGE_SMALL_PATH", MODELS_DIR / "bge-small-zh-v1.5")
    BGE_LARGE_PATH: Path = _path("BGE_LARGE_PATH", MODELS_DIR / "bge-large-zh-v1.5")
    BGE_M3_PATH: Path = _path("BGE_M3_PATH", MODELS_DIR / "bge-m3")
    # ---- CLC 用户上传资源分治阈值 ----
    CLC_SMALL_MAX_RECORDS: int = int(os.getenv("CLC_SMALL_MAX_RECORDS", "50"))  # 少量→few-shot 注入
    CLC_SMALL_MAX_BYTES: int = int(os.getenv("CLC_SMALL_MAX_BYTES", "65536"))
    CLC_BUILD_MIN_RECORDS: int = int(os.getenv("CLC_BUILD_MIN_RECORDS", "51"))  # >此值且完整树才建库
    CLC_USER_CACHE_MAX: int = max(1, int(os.getenv("CLC_USER_CACHE_MAX", "4")))  # for_path LRU 上限
    # MinerU：外部 conda 工具，无法搬入项目；默认指向 mineru conda 环境的可执行文件，
    # 否则 .env 用 MINERU_BIN 指定绝对路径。注意默认值会被写回 os.environ，
    # 因此必须与 document_processor/mineru_reader 的默认值一致（完整路径），否则污染下游。
    MINERU_BIN: str = os.getenv("MINERU_BIN", "/root/autodl-tmp/conda/envs/mineru/bin/mineru")
    # ---- MinerU vLLM 常驻服务 ----
    # 主路径：通过 HTTP 调 mineru-api 常驻服务（vllm-engine 后端，单文件~9.5s，批量并发吞吐8倍于CLI）。
    # MINERU_BIN 仅作降级备用（常驻服务不可用时由调用方决定是否回退 CLI）。
    MINERU_API_URL: str = os.getenv("MINERU_API_URL", "http://127.0.0.1:8899")
    MINERU_BACKEND: str = os.getenv("MINERU_BACKEND", "vlm-engine")  # vlm-engine(vllm) | pipeline
    MINERU_API_TIMEOUT: float = float(os.getenv("MINERU_API_TIMEOUT", "600"))
    # 自适应并发：基于在途总页数预算（实测小文件并发8最优、中文件4见顶、大文件并发无收益）。
    # 页数预算60≈4×13页最优batch上限；硬上限8防小文件过度并发。
    MINERU_PAGE_BUDGET: int = int(os.getenv("MINERU_PAGE_BUDGET", "60"))
    MINERU_MAX_CONCURRENCY: int = int(os.getenv("MINERU_MAX_CONCURRENCY", "8"))
    # 页切片并行解析：15核CPU实测单请求已吃满核（并发分片抢核反而更慢：877s vs ~600s），
    # 默认关闭。GPU/vllm 部署（推理不再吃CPU核）时可开启换吞吐。
    MINERU_PARALLEL_SLICES: bool = os.getenv("MINERU_PARALLEL_SLICES", "false").lower() == "true"

    # ---- PDF 抽取双模式 ----
    # full=所有 PDF 走 mineru vlm-engine（原样，高质量慢）；light=所有工具走 PyMuPDF
    # 直抽（毫秒级，快 80+ 倍），双栏/扫描件自动回退 mineru 保质量。
    # fund-move（字数切块+LLM汇总）/deep-cluster（聚类不依赖abstract）/abstract-move
    # （前8000字+正则+LLM校验）结构依赖已弱化，light 也走 PyMuPDF。切换改 .env 重启生效。
    PDF_EXTRACT_MODE: str = os.getenv("PDF_EXTRACT_MODE", "full")  # full | light
    # light 模式强制 mineru 的工具白名单。citation-intent/citation-sentiment 放回：
    # PyMuPDF 双栏走版面分栏读取偶发失败回退 mineru，回退链文本方差影响引用句召回稳定性；
    # mineru md 全文召回稳定（54 条）。引用句识别依赖全文 [n] 标记 + 参考文献章节截断，
    # mineru 结构化输出更可靠。ref_re 已适配冒号变体（参考文献：），空 intent 已兜底。
    STRUCTURE_DEPENDENT_TOOLS: frozenset = frozenset({'citation-intent', 'citation-sentiment'})

    def should_use_light(self, tool_id: str) -> bool:
        """轻量模式 → True（走 PyMuPDF，双栏/扫描回退 mineru）；full → False（走 mineru）。

        fund-move（字数切块+LLM汇总）、deep-cluster（聚类核心不依赖 abstract/keywords）、
        abstract-move（PyMuPDF 前8000字+正则+LLM校验）均已改走 PyMuPDF，不再强制 mineru。
        """
        return self.PDF_EXTRACT_MODE == "light" and tool_id not in self.STRUCTURE_DEPENDENT_TOOLS

    def ensure_ready(self) -> None:
        """启动期校验：确保关键配置就绪。"""
        if self.GLM_REQUIRED_AT_STARTUP and not self.GLM_API_KEY:
            raise RuntimeError("未配置 GLM_API_KEY，请在 config/.env 中设置。")
        if not self.RULES_DIR.exists():
            raise RuntimeError(f"规则库目录不存在：{self.RULES_DIR}")

    @property
    def llm_configured(self) -> bool:
        return bool(self.GLM_API_KEY)

settings = Settings()
