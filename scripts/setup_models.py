"""下载 bge 模型权重到项目 models/ 目录（GitHub 交付不含大模型文件，clone 后跑此脚本获取）。

从 ModelScope（国内可达）下载三个 bge 模型，放到 models/ 下：
  models/bge-small-zh-v1.5   — CLC 检索回退 + 部分功能
  models/bge-large-zh-v1.5   — CLC 向量索引主编码器
  models/bge-m3              — 跨语言检索 + 深度聚类父类打分 + NER 边相似度

用法：
  python -m scripts.setup_models            # 下载全部三个
  python -m scripts.setup_models --only bge-m3   # 只下某个

依赖：pip install modelscope
注意：bge-m3 约 4.3GB，下载需几分钟；网络不通时可用 HF 镜像或手动放置。
"""
from __future__ import annotations

import argparse
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"

# ModelScope 模型 ID → 本地目录名
MODELS = {
    "bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5",
    "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
    "bge-m3": "BAAI/bge-m3",
}


def download_one(local_name: str, ms_id: str) -> None:
    target = MODEL_DIR / local_name
    if target.exists() and any(target.iterdir()):
        print(f"[跳过] {local_name} 已存在：{target}")
        return
    print(f"[下载] {ms_id} → {target} ...")
    try:
        from modelscope import snapshot_download  # noqa: PLC0415
    except ImportError:
        raise SystemExit("缺少 modelscope，先 pip install modelscope")
    snapshot_download(ms_id, local_dir=str(target))
    print(f"[完成] {local_name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(MODELS.keys()), help="只下载指定模型")
    args = ap.parse_args()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    items = [(args.only, MODELS[args.only])] if args.only else MODELS.items()
    for local_name, ms_id in items:
        download_one(local_name, ms_id)
    print(f"\n模型目录：{MODEL_DIR}")
    print("下一步：重建 CLC 向量索引（见 docs/SETUP.md 第 3.2 节）")


if __name__ == "__main__":
    main()
