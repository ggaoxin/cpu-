#!/usr/bin/env python3
"""契约一致性检查（CI 用）：演示数据/真实快照 vs 后端实际响应结构。

三方一致性是本项目对 API 使用者的承诺（2026-09-11 定稿）：
- 在线测试表单的必填红星 = API/SDK 示例的必填标注
- 演示数据（demo-semantic-consistency.ts）与真实快照
  （real-responses.generated.json）= 后端实际响应结构

本脚本做结构级断言（键集合比对），不调 LLM、不连数据库，CI 秒级完成：
1. 三个手写演示块（deep-cluster / cluster-label / structured-review）
   的关键字段存在性（近期漂移高发区）
2. 快照信封形状（{code, message, data} 模式嵌套）
3. 语步规则含"非语步声明"条款（防回退）
退出码非零 = 有漂移，CI 拦截。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def main() -> int:
    demo = (FRONTEND / "data" / "demo-semantic-consistency.ts").read_text(encoding="utf-8")

    # ---- 结构化自动综述演示块 ----
    rv = demo[demo.find("const reviewResponse = {"):demo.find("const singleProfileIndex")]
    for field in ("progress_id", "source_evidence", "question_summary", "document_ids",
                  "year_coverage", "supporting_years", "evidence_id", "quote:"):
        check(f"综述演示含 {field}", f"{field}" in rv)
    check("综述热点新枚举", "'持续热门'" in rv and "'上升趋势'" in rv)
    check("综述旧枚举已清", "快速发展" not in rv and "新兴方向" not in rv)

    # ---- 聚类标签演示块 ----
    cl = demo[demo.find("const clusterLabelResponse = {"):demo.find("const reviewResponse = {")]
    for field in ("alternatives", "evidence_terms", "generation_method", "representativeness",
                  "status", "phrase_count", "items:", "optimized_count", "threshold_passed"):
        check(f"聚类标签演示含 {field}", field in cl)
    check("聚类标签旧rank已清", "rank:" not in cl)
    check("聚类标签旧opt结构已清", "duplicate_candidate_count" not in cl)

    # ---- 深度聚类演示块 ----
    dc = demo[demo.find("const deepClusterResponse = "):demo.find("const clusterLabelResponse = {")]
    for field in ('"documents"', '"theme_trend_analysis"', '"partition_strategy"',
                  '"quality_metrics"', '"correction_status"', '"input_type"'):
        check(f"深度聚类演示含 {field}", field in dc)
    check("深度聚类旧tool字段已清", "tool:" not in dc)
    check("深度聚类trend旧字段已清", "trend_score" not in dc)

    # ---- 快照信封形状 ----
    gen = json.loads((FRONTEND / "data" / "real-responses.generated.json").read_text(encoding="utf-8"))
    for tool, modes in gen.items():
        if not isinstance(modes, dict):
            continue
        for mode, resp in modes.items():
            ok = isinstance(resp, dict) and "code" in resp and "data" in resp
            check(f"快照信封 {tool}/{mode}", ok)

    # ---- 语步规则：非语步声明条款（双层防线之 LLM 层）----
    en_rule = (ROOT / "rules" / "move_recognition" / "mr_en_abstract.yaml").read_text(encoding="utf-8")
    zh_rule = (ROOT / "rules" / "move_recognition" / "mr_zh_abstract.yaml").read_text(encoding="utf-8")
    check("英文语步规则含非语步声明条款", "Non-move declarations" in en_rule or "non-move" in en_rule.lower())
    check("中文语步规则含非语步声明条款", "非语步声明" in zh_rule)

    # ---- 前端资源 fetch 均走鉴权包装（开启鉴权时可用）----
    api_ts = (FRONTEND / "services" / "api.ts").read_text(encoding="utf-8")
    check("前端无绕过鉴权的裸 fetch(apiUrl", "fetch(apiUrl(" not in api_ts.replace("fetchWithApiKey(apiUrl(", ""))

    print(f"\n{'=' * 40}\n{'全部通过' if not failures else '失败 ' + str(len(failures)) + ' 项: ' + '; '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
