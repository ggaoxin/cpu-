#!/usr/bin/env python3
"""迁移预热：在目标服务器上按本地路径/时间戳重算缓存文件名。

锚点向量缓存按 md5(绝对路径|mtime_ns|size|轴) 命名，跨机器拷贝后路径/mtime
变化会导致缓存失配 → 首次深度聚类要在 CPU 上重编码 11.7 万篇（数小时）。
本脚本在目标机上重算正确摘要并复制缓存文件，实现秒级加载、零编码。

用法（项目根目录下）：
  python3 migrate_prewarm_cache.py /path/to/semantic_toolkit
"""
import hashlib
import shutil
import sys
from pathlib import Path

SOURCES = {
    "technical": "anchors_35cced6a6a1ddd07",
    "application": "anchors_ed15750427b919a0",
}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    slot = root / "rules" / "deep_clustering" / "gold" / "anchor_gold_current.json"
    cache_dir = root / "rag_store" / "deep_clustering_anchor"
    if not slot.is_file():
        print(f"❌ 找不到 gold 槽位文件：{slot}")
        return 1
    stat = slot.stat()
    ok = True
    for axis, source in SOURCES.items():
        digest = hashlib.md5(
            f"{slot.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{axis}".encode()
        ).hexdigest()[:16]
        for ext in (".npy", ".json"):
            src = cache_dir / f"{source}{ext}"
            dst = cache_dir / f"anchors_{digest}{ext}"
            if dst.exists():
                print(f"✓ {axis}: {dst.name} 已存在")
                continue
            if not src.is_file():
                print(f"❌ {axis}: 源缓存缺失 {src.name}")
                ok = False
                continue
            shutil.copy2(src, dst)
            print(f"✓ {axis}: {source}{ext} → anchors_{digest}{ext}")
    print("\n完成。验证：跑一次深度聚类，后端日志应出现『锚点索引缓存命中』"
          "且无长时间编码等待。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
