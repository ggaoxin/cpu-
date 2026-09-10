"""摘要提取 golden set 回归护栏（2026-09-09 工程化：未见版式正确性配套措施）。

用法：
  python3 scripts/tools/abstract_golden_eval.py            # 对比快照，报告差异
  python3 scripts/tools/abstract_golden_eval.py --update   # 重新生成快照（人工确认当前结果正确后）

校验对象：规则兜底路径（AbstractExtractor + repair，确定性输出，diff 稳定）。
LLM 主路径的正确性由运行时硬校验闭环保证（_validate_extracted_abstract），
不依赖本快照——温度 0 也无法保证跨次完全一致。

快照首次生成于 2026-09-09，覆盖 papers/（54 篇英文）+ ch_papers/（20 篇中文，
含双语/拆字/网络首发封面等疑难版式），当时已逐篇人工审计（无版权/水印/单位/
表格/碎片残留，中文篇全部中文摘要）。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from infrastructure.document_parser.pdf_citation_parser.abstracts import (  # noqa: E402
    AbstractConfig, AbstractExtractor,
)

GOLDEN_PATH = ROOT / "scripts" / "tools" / "abstract_golden.json"
CORPORA = [
    ("/root/autodl-tmp/datasets/papers/*.pdf", "en"),
    ("/root/autodl-tmp/datasets/ch_papers/*.pdf", "zh"),
]


def _key(path: str) -> str:
    raw = os.path.basename(path)
    # ch_papers 的 GBK 文件名经 glob 得到代理字符（无法直接进 JSON），
    # 还原成 GBK 可读形式作键
    try:
        return raw.encode("utf-8", "surrogateescape").decode("gbk", "replace")
    except Exception:  # noqa: BLE001
        return raw


def extract_all() -> dict:
    extractor = AbstractExtractor(AbstractConfig(search_pages=8, preferred_language="zh"))
    out = {}
    for pattern, _tag in CORPORA:
        for path in sorted(glob.glob(pattern)):
            try:
                content = open(path, "rb").read()
                # GBK 文件名兼容：走字节流临时文件
                tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp.write(content)
                tmp.close()
                try:
                    result = extractor.extract(tmp.name)
                finally:
                    os.unlink(tmp.name)
                out[_key(path)] = {
                    "len": len(result.text) if result and result.text else 0,
                    # 快照只存指纹特征而非全文：长度 + 首尾 40 字（对齐 diff 检查点）
                    "head": (result.text or "")[:40] if result else "",
                    "tail": (result.text or "")[-40:] if result else "",
                }
            except Exception as exc:  # noqa: BLE001
                out[_key(path)] = {"len": -1, "head": f"EXC:{exc}", "tail": ""}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="重新生成快照")
    args = parser.parse_args()

    current = extract_all()

    if args.update or not GOLDEN_PATH.exists():
        GOLDEN_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"快照已写入 {GOLDEN_PATH}（{len(current)} 篇）")
        return 0

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    diffs, added, missing = [], [], []
    for name, cur in current.items():
        old = golden.get(name)
        if old is None:
            added.append(name)
            continue
        if old.get("len") != cur.get("len") or old.get("head") != cur.get("head") or old.get("tail") != cur.get("tail"):
            diffs.append((name, old, cur))
    for name in golden:
        if name not in current:
            missing.append(name)

    print(f"共 {len(current)} 篇 | 一致 {len(current) - len(diffs) - len(added)} | 差异 {len(diffs)} | 新增 {len(added)} | 缺失 {len(missing)}")
    for name, old, cur in diffs:
        print(f"  ✗ {name}: len {old['len']}→{cur['len']}")
        print(f"      旧头: {old['head']!r}")
        print(f"      新头: {cur['head']!r}")
        print(f"      旧尾: {old['tail']!r}")
        print(f"      新尾: {cur['tail']!r}")
    for name in added:
        print(f"  + 新文件: {name}")
    for name in missing:
        print(f"  - 已移除: {name}")
    if diffs:
        print("\n有差异：人工确认新结果正确后运行 --update 更新快照；否则回退改动。")
        return 1
    print("全部一致 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
