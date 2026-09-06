#!/usr/bin/env python3
"""构建 v2 口径的 silver gold：按"讲的事情"（方法口径/场景口径）GLM 归类。

Stage A：抽样归纳类目清单（方法类目 / 场景类目）
Stage B：全部双轴子集逐批 GLM 归类 → /tmp/silver_gold.json
  [{idx, method_class, scene_class, method_text, scene_text, tech_label, app_label}]
依赖 /tmp/gold_moves.json。
"""
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BATCH = 25
MAX_WORKERS = 6


def glm():
    from infrastructure.llm.glm_client import glm_client
    return glm_client


def stage_a_categories(client, samples: list, kind: str) -> list:
    """抽样归纳类目清单（kind: method/scene）。"""
    lines = []
    for i, sents in enumerate(samples):
        joined = "；".join(sents[:3])[:150]
        lines.append(f"[{i + 1}] {joined}")
    label_hint = ("研究方法" if kind == "method" else "应用场景/研究对象")
    system = (
        f"你是科技文献分析专家。下面是多篇文献的{label_hint}描述片段。"
        f"请归纳出这些文献所做的事情的类目清单——每个类目是一件具体的事情"
        f"（如'YOLO目标检测''聚类分析''有限元仿真'/'糖尿病诊疗''机器人检测''桥梁结构监测'），"
        "硬性要求：类目总数不超过 50 个，宁粗勿细（相近的事情合并为一类，"
        "单篇独有的事情并入最接近的大类）；类目互不重叠。"
        '只输出JSON：{"categories":["类目1","类目2",...]}'
    )
    raw = client.chat_json(system, "\n".join(lines), temperature=0.0, timeout=120.0, max_tokens=2000)
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    cats = [str(c).strip() for c in (raw.get("categories") or []) if str(c).strip()]
    # 超出硬约束 → 让 GLM 归并到 ≤50（第一轮实测 281 类太碎，每类平均 6 篇无聚类价值）
    if len(cats) > 50:
        merge_system = (
            f"以下是{len(cats)}个过于细碎的类目。把它们归并成不超过 50 个大类"
            "（相近的事情合并，输出归并后的类目清单，仍须互不重叠、覆盖原全部类目）。"
            '只输出JSON：{"categories":[...]}'
        )
        raw2 = client.chat_json(merge_system, "\n".join(cats), temperature=0.0, timeout=120.0, max_tokens=2000)
        if isinstance(raw2, dict) and isinstance(raw2.get("data"), dict):
            raw2 = raw2["data"]
        merged = [str(c).strip() for c in (raw2.get("categories") or []) if str(c).strip()]
        if 5 <= len(merged) <= 50:
            cats = merged
    return cats[:50]


def stage_b_assign(client, rows: list, cats: list, kind: str) -> list:
    """逐批归类：rows=[{idx,text}] → [{idx, cls}]。"""
    label_hint = ("研究方法" if kind == "method" else "应用场景")
    cat_list = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(cats))
    lines = [f"[{r['idx']}] {'；'.join(r['sents'][:3])[:150]}" for r in rows]
    system = (
        f"你是科技文献归类专家。给定类目清单和各文献的{label_hint}描述，"
        "把每篇文献归入最贴切的一个类目（只填类目编号数字）。描述与所有类目都不贴切时填 0。"
        "只输出JSON："
        '{"assign":[{"id":编号,"cat":类目序号},...]}，每篇一条。'
    )
    raw = client.chat_json(system, f"类目清单：\n{cat_list}\n\n文献：\n" + "\n".join(lines),
                           temperature=0.0, timeout=120.0, max_tokens=2500)
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    out = {}
    for item in (raw.get("assign") or []):
        if isinstance(item, dict) and item.get("id") is not None:
            try:
                ci = int(item.get("cat"))
            except (TypeError, ValueError):
                continue
            cls = cats[ci - 1] if 1 <= ci <= len(cats) else "未归类"
            out[str(item["id"])] = cls
    return out




def stage_c_audit(client, rows, results, kind, sample_per_class=5):
    """质量审查：每类抽 N 篇，GLM 验证'该篇是否真属于此类'，输出类目纯度报告。

    纯度 <70% 的类目标记为低质量（后续评估时剔除或降权）。
    """
    from collections import defaultdict, Counter
    by_class = defaultdict(list)
    rng = random.Random(99)
    for r in rows:
        cls = results.get(str(r["idx"]))
        if cls and cls != "未归类":
            by_class[cls].append(r)
    label_hint = ("研究方法" if kind == "method" else "应用场景")
    audit_rows = []
    for cls, members in by_class.items():
        for r in rng.sample(members, min(sample_per_class, len(members))):
            audit_rows.append((cls, r))
    system = (
        f"你是科技文献归类质量审查员。给定类目名和一篇文献的{label_hint}描述，"
        "判断该文献是否确实属于这个类目（讲的是同一件事）。"
        '只输出JSON：{"audit":[{"cls":"类目","id":文献编号,"ok":true},...]}'
    )
    lines = [f"[{r['idx']}] 类目「{cls}」：{'；'.join(r['sents'][:2])[:110]}" for cls, r in audit_rows]
    batches = [lines[i:i + 40] for i in range(0, len(lines), 40)]
    ok_map, total_map = Counter(), Counter()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        def one(batch):
            try:
                raw = client.chat_json(system, "\n".join(batch), temperature=0.0, timeout=120.0, max_tokens=3000)
            except Exception:  # noqa: BLE001
                return {}
            if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
                raw = raw["data"]
            out = {}
            for item in (raw.get("audit") or []):
                if isinstance(item, dict) and item.get("cls") is not None:
                    out[(str(item["cls"]), str(item.get("id")))] = bool(item.get("ok"))
            return out
        for part in pool.map(one, batches):
            ok_map.update({k: v for k, v in part.items() if v})
            for k in part:
                total_map[k[0]] += 0  # 占位
    # 按类汇总
    class_ok, class_total = Counter(), Counter()
    for cls, r in audit_rows:
        class_total[cls] += 1
        if ok_map.get((cls, str(r["idx"]))):
            class_ok[cls] += 1
    purity_map = {cls: class_ok[cls] / max(class_total[cls], 1) for cls in class_total}
    bad = {c: p for c, p in purity_map.items() if p < 0.7}
    print(f"[{kind}] 审查 {len(class_total)} 类: 平均纯度 {sum(purity_map.values())/max(len(purity_map),1):.0%} | "
          f"低质量(<70%) {len(bad)} 类: {list(bad.items())[:5]}", flush=True)
    return purity_map

def run_axis(client, rows, kind, rng):
    texts = [r["sents"] for r in rows]
    sample_idx = rng.sample(range(len(rows)), min(300, len(rows)))
    cats = stage_a_categories(client, [texts[i] for i in sample_idx], kind)
    print(f"[{kind}] Stage A 类目数: {len(cats)}: {cats[:8]}...", flush=True)
    if not cats:
        return {}
    batches = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for part in pool.map(lambda b: stage_b_assign(client, b, cats, kind), batches):
            results.update(part)
    assigned = sum(1 for r in rows if results.get(str(r["idx"])) not in (None, "", "未归类"))
    print(f"[{kind}] Stage B 归类: {assigned}/{len(rows)}", flush=True)
    return results


def main():
    rng = random.Random(7)
    rows = json.loads(Path("/tmp/gold_moves.json").read_text(encoding="utf-8"))
    client = glm()

    method_rows = [{"idx": r["idx"], "sents": r["method"]} for r in rows if r["method"]]
    scene_rows = [{"idx": r["idx"], "sents": r["background"] + r["purpose"]}
                  for r in rows if (r["background"] or r["purpose"])]
    print(f"技术轴池: {len(method_rows)} | 应用轴池: {len(scene_rows)}", flush=True)

    method_map = run_axis(client, method_rows, "method", rng)
    scene_map = run_axis(client, scene_rows, "scene", rng)

    # Stage C 质量审查（迭代修正依据：低质量类在评估中剔除）
    method_purity = stage_c_audit(client, method_rows, method_map, "method") if method_map else {}
    scene_purity = stage_c_audit(client, scene_rows, scene_map, "scene") if scene_map else {}

    out = []
    for r in rows:
        mc = method_map.get(str(r["idx"]), "")
        sc = scene_map.get(str(r["idx"]), "")
        if mc or sc:
            out.append({"idx": r["idx"], "method_class": mc, "scene_class": sc,
                        "method_purity": method_purity.get(mc), "scene_purity": scene_purity.get(sc),
                        "tech_label": r["tech_label"], "app_label": r.get("app_label")})
    Path("/tmp/silver_gold.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    mc = Counter(x["method_class"] for x in out if x["method_class"] and x["method_class"] != "未归类")
    sc = Counter(x["scene_class"] for x in out if x["scene_class"] and x["scene_class"] != "未归类")
    print(f"\n完成 {len(out)} 篇 | 方法类目 {len(mc)} 个 top5: {mc.most_common(5)}")
    print(f"场景类目 {len(sc)} 个 top5: {sc.most_common(5)}")
    print("已存 /tmp/silver_gold.json")


if __name__ == "__main__":
    main()
