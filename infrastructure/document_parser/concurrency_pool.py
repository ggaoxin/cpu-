"""基于在途总页数的自适应并发调度（同步版）。

实测规律（RTX 3090，vllm 常驻）：
- 小文件(3-5页)：并发8最优，吞吐38文件/分
- 中文件(13页)：并发4见顶，吞吐11.4文件/分
- 大文件(50+页)：并发无收益，单文件已喂满GPU算力，串行最优
- 显存永不超基线（vllm kv cache池预分配），OOM非约束

故不用固定并发数，而用「在途总页数预算」：
  准入条件 = 当前在途页数 + 新请求页数 ≤ PAGE_BUDGET  且  在途请求数 < MAX_CONCURRENCY
- 小文件几乎不占预算 → 自动高并发
- 大文件占预算多 → 自动串行
一个公式适配所有混合场景。PAGE_BUDGET=60 来自 4×13页=52 的最优batch上限。

同步（threading.Condition）而非 asyncio：让 ThreadPoolExecutor 工作线程（en-keyword
_semantic_request 延迟解析、use_concurrent 并发篇）能直接同步调用 acquire/release 控制
GPU 并发，实现 mineru 解析与 GLM 处理流水线（不同资源并行）。async 调用方（端点层
extract_uploads / _extract_abstract_only）用 asyncio.to_thread 桥接。
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class PageBudgetPool:
    """在途总页数预算 + 硬上限的自适应并发池（同步）。"""

    def __init__(self, page_budget: int = 60, max_concurrency: int = 8) -> None:
        self._page_budget = page_budget
        self._max_concurrency = max_concurrency
        self._in_flight_pages = 0
        self._in_flight_count = 0
        self._cond = threading.Condition()

    def acquire(self, pages: int) -> None:
        """阻塞直到准入条件满足（在途预算+本请求≤预算 且 在途数<上限）。

        大文件(pages>page_budget)按预算值封顶独占运行——否则 0+pages>budget
        恒真会永久阻塞，导致 /files 多文件(含>60页PDF)死锁无响应。
        """
        pages = max(1, pages)  # 至少占1页预算，防0页文件绕过硬上限
        budget = min(pages, self._page_budget)  # 封顶到预算，防 >budget 死锁
        with self._cond:
            while (self._in_flight_pages + budget > self._page_budget
                   or self._in_flight_count >= self._max_concurrency):
                self._cond.wait()
            self._in_flight_pages += budget
            self._in_flight_count += 1

    def release(self, pages: int) -> None:
        """归还页数预算并唤醒等待者。"""
        pages = max(1, pages)
        budget = min(pages, self._page_budget)  # 与 acquire 口径一致
        with self._cond:
            self._in_flight_pages = max(0, self._in_flight_pages - budget)
            self._in_flight_count = max(0, self._in_flight_count - 1)
            self._cond.notify_all()

    @property
    def status(self) -> dict:
        return {
            "in_flight_pages": self._in_flight_pages,
            "in_flight_count": self._in_flight_count,
            "page_budget": self._page_budget,
            "max_concurrency": self._max_concurrency,
        }


_pool: Optional[PageBudgetPool] = None


def get_page_budget_pool() -> PageBudgetPool:
    """获取全局 PageBudgetPool 单例（配置从 settings 读取）。"""
    global _pool
    if _pool is None:
        _pool = PageBudgetPool(
            page_budget=settings.MINERU_PAGE_BUDGET,
            max_concurrency=settings.MINERU_MAX_CONCURRENCY,
        )
    return _pool
