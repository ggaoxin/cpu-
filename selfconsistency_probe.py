"""self-consistency 探针：对真实文献多次采样，对比 一致率 vs 平均自报置信度。

复用生产 prompt 构造（_system_prompt + _render_classification_user_prompt），
仅在外层包 N 次 GLM 采样（temperature=0.3 带多样性），不改生产代码。
"""
import sys, json, os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infrastructure.llm.glm_client import glm_client
from infrastructure.rule_engine.rule_loader import rule_loader
from application.service.semantic_service import SemanticApplicationService
from application.dto.common_dto import SemanticRequest

N = 5          # 采样次数
TEMP = 0.3     # self-consistency 采样温度（>0 才有多样性；生产默认 0.1 近确定）

service = SemanticApplicationService(glm=glm_client, rule_loader=rule_loader)
rule = rule_loader.load("ac_zh")

# 从 gold 数据集取 3 篇真实文献（经济 F / 电工 TM / 电工 TM）
ds = json.load(open("data/datasets/random_50_chinese_papers_clc_classification_v3.json",
                    encoding="utf-8"))
papers = ds if isinstance(ds, list) else list(ds.values())[0]
picks = [papers[0], papers[3], papers[5]]

def parse_one(data):
    """从单次 GLM 返回解析 首选组合 (main_code, aux_code, confidence)。"""
    data = data.get("data", data) if isinstance(data, dict) else {}
    combos = data.get("combinations") or []
    if not combos:
        legacy_main = (data.get("main_code") or "").strip()
        legacy_aux = [c for c in (data.get("auxiliary_codes") or []) if c and c.strip()]
        if legacy_main:
            return legacy_main, (legacy_aux[0] if legacy_aux else ""), float(data.get("confidence") or 1.0)
        return "", "", 0.0
    c0 = combos[0]
    auxs = [c for c in (c0.get("auxiliary_codes") or []) if c and c.strip()]
    return (c0.get("main_code") or "").strip(), (auxs[0] if auxs else ""), float(c0.get("confidence") or 0)

print(f"=== self-consistency 探针  N={N}  temperature={TEMP}（生产默认 0.1）===\n")
for pi, p in enumerate(picks):
    nm = p.get("ch_name") or p.get("title") or ""
    kw = p.get("keywords", [])
    req = SemanticRequest(text=json.dumps({
        "ch_name": nm, "ch_abstract": p.get("ch_abstract", ""), "keywords": kw,
    }, ensure_ascii=False))
    title, abstract, _, _ = service._parse_paper_input(req)
    sys_p = service._system_prompt(rule, req)
    usr_p = service._render_classification_user_prompt(title, abstract, [], None)

    print(f"【文献{pi}】{nm}")
    print(f"  摘要前80字：{abstract[:80]}")

    codes, confs, auxs = [], [], []
    for k in range(N):
        try:
            d = glm_client.chat_json(sys_p, usr_p, temperature=TEMP,
                                     timeout=120.0, max_tokens=1500)
            mc, ac, cf = parse_one(d)
            codes.append(mc); confs.append(cf); auxs.append(ac)
            print(f"  第{k+1}次: 主={mc:12s} 次={ac or '—':10s} 自报conf={cf:.2f}  原始={mc}/{ac or '-'}")
        except Exception as e:
            print(f"  第{k+1}次: 失败 {e}")
            codes.append(""); confs.append(0.0)

    # 统计
    valid = [c for c in codes if c]
    if valid:
        mode_code, mode_cnt = Counter(valid).most_common(1)[0]
        consistency = mode_cnt / len(valid)                       # 一致率（投票）
        avg_conf = sum(confs) / len(confs)                        # 平均自报置信度
        sc_conf = consistency * avg_conf                          # 一致率 × 平均
        prod_now = min(confs[0], 0.95)                           # 生产现值（首次 min 封顶）
        print(f"  ── 主码分布: {dict(Counter(valid))}")
        print(f"  ── 一致率(mode {mode_code}): {mode_cnt}/{len(valid)} = {consistency:.2f}  ← 客观稳定性")
        print(f"  ── 平均自报conf: {avg_conf:.2f}  ← 平均 N 个 LLM 自报值")
        print(f"  ── SC置信度(一致率×平均): {sc_conf:.2f}  ← 推荐值")
        print(f"  ── 生产现值(min(首次,{confs[0]:.2f},0.95)): {prod_now:.2f}  ← 当前入库值")
        print(f"  ★ 结论：{'一致' if consistency==1.0 else '摇摆'} | SC={sc_conf:.2f} vs 生产={prod_now:.2f} "
              f"{'(SC更稳，生产虚高)' if prod_now>sc_conf+0.05 else '(接近)'}\n")
    else:
        print("  ── 全部解析失败\n")

print("=== 探针完成 ===")
