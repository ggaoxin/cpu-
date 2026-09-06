#!/usr/bin/env python3
"""papers 前 20 篇 PDF 双轴测试：全文语步提取 → 双轴综述粒度聚类。

技术路线轴 = 方法句 → LLM 按方法分组（综述粒度）
应用场景轴 = 背景+目的句+题名 → LLM 按场景分组（综述粒度）
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from experiment_fulltext_move import chunk_text, EXTRACT_SYSTEM


def extract_chunk(glm, chunk):
    try:
        raw = glm.chat_json(EXTRACT_SYSTEM, f"文献片段：\n{chunk}", temperature=0.0, timeout=120.0, max_tokens=3000)
    except Exception:  # noqa: BLE001
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    return {k: ([str(v).strip() for v in raw.get(k) or [] if str(v).strip()] if isinstance(raw, dict) else [])
            for k in ("研究背景", "研究目的", "研究方法")}


def main(pdf_dir, take=20):
    pdfs = sorted((p for p in Path(pdf_dir).glob("*.pdf")), key=lambda p: int(p.stem) if p.stem.isdigit() else 999)[:take]
    print(f"处理前 {len(pdfs)} 篇: {[p.name for p in pdfs]}")

    from infrastructure.document_parser.mineru_reader import process_to_text
    from infrastructure.llm.glm_client import glm_client

    def parse(p):
        try:
            return {"name": p.name, "text": (process_to_text(str(p)).get("full_text") or "").strip()}
        except Exception:  # noqa: BLE001
            return {"name": p.name, "text": ""}
    with ThreadPoolExecutor(max_workers=4) as pool:
        docs = list(pool.map(parse, pdfs))
    docs = [d for d in docs if len(d["text"]) > 200]
    print(f"全文解析成功 {len(docs)}/{len(pdfs)}")

    # 标题从全文首行提取（文件名是数字编号无语义）
    for d in docs:
        head = "\n".join(ln.strip() for ln in d["text"].split("\n")[:8] if ln.strip())
        title_line = next((ln for ln in head.split("\n") if 8 <= len(ln) <= 60 and not ln.startswith(("摘要", "关键词", "http", "DOI", "第"))), "")
        d["title"] = title_line[:40] or d["name"]

    def extract(doc):
        chunks = chunk_text(doc["text"])
        with ThreadPoolExecutor(max_workers=6) as pool:
            parts = list(pool.map(lambda c: extract_chunk(glm_client, c), chunks))
        merged = {k: [] for k in ("研究背景", "研究目的", "研究方法")}
        for part in parts:
            for k in merged:
                merged[k].extend(part.get(k) or [])
        for k in merged:
            merged[k] = list(dict.fromkeys(merged[k]))[:15]
        return {"name": doc["name"], "title": doc["title"], **merged}

    out = []
    for doc in docs:
        r = extract(doc)
        out.append(r)
        print(f"  ✓ {r['name']}「{r['title'][:24]}」: 方法{len(r['研究方法'])} 背景{len(r['研究背景'])} 目的{len(r['研究目的'])}", flush=True)
    Path("/tmp/papers20_moves.json").write_text(json.dumps(out, ensure_ascii=True, indent=1), encoding="utf-8")

    # 双轴 LLM 综述粒度分组
    def llm_group(kind):
        lines = []
        for i, d in enumerate(out):
            if kind == "tech":
                sents = d["研究方法"][:2]
            else:
                sents = (d["研究背景"] + d["研究目的"])[:2] + [d["title"]]
            lines.append(f"[{i+1}]「{d['title'][:20]}」{'；'.join(s[:65] for s in sents[:2])}")
        system = (
            "你是科技文献聚类专家。把下面文献按"
            + ("所用的具体技术方法" if kind == "tech" else "所研究的应用场景/对象")
            + "分组。判断标准：同一簇的文献必须能直接合并为一篇聚焦的主题综述"
            "（簇内全部文献研究同类方法/同一场景）。研究同一主题但方法/表述不同的"
            "文献必须聚在一起；讲不同事情的文献绝不能混入同簇，宁可各自单列。"
            '只输出JSON：{"groups":[{"name":"簇名","docs":[编号,...]}]}'
        )
        raw = glm_client.chat_json(system, "\n".join(lines), temperature=0.0, timeout=180.0, max_tokens=3000)
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            raw = raw["data"]
        label_of = {}
        for g in (raw.get("groups") or []):
            if isinstance(g, dict):
                for x in (g.get("docs") or []):
                    try:
                        label_of[int(x)] = str(g.get("name") or "")
                    except (TypeError, ValueError):
                        pass
        return [label_of.get(i + 1, "未分组") for i in range(len(out))]

    for kind, label in [("tech", "技术路线轴（方法句→综述粒度分组）"), ("scene", "应用场景轴（背景+目的+题名→综述粒度分组）")]:
        labels = llm_group(kind)
        print(f"\n===== {label} =====")
        groups = {}
        for d, lab in zip(out, labels):
            groups.setdefault(lab, []).append(f"{d['name']}「{d['title'][:20]}」")
        for lab, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            print(f"  「{lab}」（{len(members)}）")
            for m in members:
                print(f"     {m}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/root/autodl-tmp/datasets/papers")
