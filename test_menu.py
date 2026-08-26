#!/usr/bin/env python3
"""已实现功能点测试菜单：交互式选择功能点，输入文本或文件地址测试。

运行：cd <项目根> && python test_menu.py
"""
import json
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def _norm(s: str) -> str:
    """全角→半角（数字/字母/标点），兼容中文输入法全角数字如"２"。"""
    return unicodedata.normalize("NFKC", s).strip()


from presentation.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# (编号, code, 功能项code, 中文名, 输入说明)
FPS = [
    ("1", "mr_zh_abstract", "move_recognition", "中文摘要语步识别", "中文摘要/文献"),
    ("2", "mr_en_abstract", "move_recognition", "英文摘要语步识别", "英文摘要/文献"),
    ("3", "mr_zh_fund", "move_recognition", "中文基金项目语步识别", "基金全文(含##章节)/文件"),
    ("4", "ac_zh", "auto_classification", "中文科技文献分类", "标题摘要关键词/文献"),
    ("5", "ac_en", "auto_classification", "英文科技文献分类", "标题摘要关键词/文献"),
    ("6", "ac_domain", "auto_classification", "专业领域科技文献分类", "标题摘要关键词/文献"),
    ("7", "kw_zh", "keyword_recognition", "中文关键词识别", "标题摘要/文献"),
    ("8", "kw_en", "keyword_recognition", "英文关键词识别", "摘要/文献"),
    ("9", "rq_identify", "research_question", "研究问题识别", "摘要/文献"),
    ("10", "dc_cluster", "deep_clustering", "深度聚类(双轴主题映射)", "多篇文献(文件/JSON/文本)"),
    ("11", "cl_label", "cluster_labeling", "聚类标签生成", "多篇文献(文件/JSON/文本)"),
    ("12", "sr_review", "structured_review", "结构化自动综述", "多篇文献+综述主题"),
    ("13", "ner", "ner", "命名实体识别", "文献全文/文件(通用/领域/科研/关系)"),
    ("14", "cr", "citation_recognition", "引用句识别", "文献全文/文件(意图/情感)"),
    ("15", "cd_identify", "concept_definition", "概念定义识别", "文献全文/文件"),
]


def get_text(code: str) -> str | None:
    """获取输入文本：直接输入 或 文件地址。"""
    print("\n输入方式：")
    print("  1. 直接输入文本（单行，回车结束）")
    print("  2. 输入文件地址（.md/.txt 直接解析；.pdf 走 MinerU 提取再解析）")
    m = _norm(input("选择 [1/2]: "))

    if m == "2":
        path = input("文件地址: ").strip().strip('"').strip("'")
        if not os.path.exists(path):
            print(f"❌ 文件不存在: {path}")
            return None
        is_pdf = path.lower().endswith(".pdf")
        # mr_zh_fund：返回 md 路径，让管线用 DocumentParser 解析（带 content_list 页码）
        if code == "mr_zh_fund":
            if is_pdf:
                from infrastructure.document_parser.document_processor import DocumentProcessor
                print("PDF 走 MinerU 提取（可能数分钟）...")
                try:
                    doc = DocumentProcessor().process_pdf(path)
                except Exception as e:
                    print(f"❌ 提取失败: {e}"); return None
                md_path = doc.get("_md_path", "")
                if not md_path:
                    print("❌ 未取到 md 路径"); return None
                print(f"已提取 md：{md_path}")
                return md_path
            print(f"使用 md 文件：{path}")
            return path
        # 其他功能：PDF 走 MinerU→DocumentParser；md/txt 直接 DocumentParser
        from infrastructure.document_parser.document_parser import DocumentParser
        from infrastructure.document_parser.document_processor import DocumentProcessor
        print(f"解析文档中{'（PDF 走 MinerU 提取，可能数分钟）' if is_pdf else '（md/txt 直接解析）'}...")
        try:
            doc = DocumentProcessor().process_pdf(path) if is_pdf else DocumentParser().parse(path)
        except Exception as e:
            print(f"❌ 解析失败: {e}")
            return None
        if code.startswith("ac_"):
            text = doc.get("full_text", "")          # 分类工具会自动提取标题/摘要/关键词
        elif code.startswith("ner_") or code.startswith("cr_") or code == "cd_identify":
            text = doc.get("full_text", "") or doc.get("abstract", "")  # 引用/概念/实体 需全文
        else:
            # mr_abstract / kw / rq 用摘要，空则兜底全文
            text = doc.get("abstract", "") or doc.get("full_text", "")
        print(f"已解析: 标题={doc.get('title', '')[:40]} | 类型={doc.get('doc_type', '')} | 取文本 {len(text)} 字符")
        if not text:
            print("❌ 未能从文档提取到可用文本")
            return None
        return text

    # ac_* 接受 paper JSON 或纯摘要
    if code.startswith("ac_"):
        print("输入 paper JSON（如 {\"ch_name\":\"...\",\"ch_abstract\":\"...\",\"keywords\":[...]}）：")
        print("或直接输入摘要文本：")
        return input("> ").strip()
    # 其他：直接输入文本
    print("输入文本（单行，回车结束；长文本建议用文件方式 2）：")
    return input("> ").strip()


def show(code: str, r: dict) -> None:
    """格式化展示结果。"""
    print("\n" + "─" * 60)
    if not r.get("success"):
        print(f"❌ 失败: {str(r.get('error', ''))[:400]}")
        return
    d = r.get("data")
    print("✅ 成功")

    if code == "mr_zh_fund":
        for m in d:
            print(f"\n【{m.get('move_type')}】")
            print(m.get("content") or "（空）")
            loc = m.get("text_location", [])
            if loc:
                print(f"文本位置：第{'、'.join(str(p) for p in loc)}页")
    elif code.startswith("mr_"):
        if isinstance(d, dict):
            for k, v in d.items():
                print(f"  {k}: {v}")
        else:
            print(json.dumps(d, ensure_ascii=False, indent=2)[:1500])
    elif code == "dc_cluster":
        print(f"共 {d.get('n',0)} 篇文献")
        print(f"\n技术路线轴主题 ({len(d.get('technical_topics',[]))} 个):")
        for t in sorted(d.get("technical_topics", []), key=lambda x: -len(x.get("doc_indices", []))):
            print(f"  [{t['topic_name']}] (n={len(t.get('doc_indices',[]))})")
        print(f"\n应用场景轴主题 ({len(d.get('application_topics',[]))} 个):")
        for t in sorted(d.get("application_topics", []), key=lambda x: -len(x.get("doc_indices", []))):
            print(f"  [{t['topic_name']}] (n={len(t.get('doc_indices',[]))})")
        print("\n各文献映射:")
        for doc in d.get("documents", []):
            print(f"  {doc.get('title','')[:35]}")
            print(f"    技术→{doc.get('technical',{}).get('topic_name','')}({doc.get('technical',{}).get('status','')})")
            print(f"    应用→{doc.get('application',{}).get('topic_name','')}({doc.get('application',{}).get('status','')})")
    elif code == "cl_label":
        clusters = d.get("clusters", [])
        print(f"共 {d.get('n',0)} 篇文献，{len(clusters)} 个簇标签：")
        for c in clusters:
            print(f"  [{c['label']}] (n={c.get('n',0)}, axis={c.get('axis','')}) docs={c.get('doc_indices',[])}")
    elif code == "sr_review":
        print(f"标题: {d.get('title','')}")
        print(f"文献数: {d.get('n_documents',0)}  类簇数: {d.get('n_clusters',0)}  RQ数: {len(d.get('tree',[]))}")
        print(f"\n=== 研究背景 ===")
        print(d.get("background","")[:300])
        print(f"\n=== 三层树（RQ→M→进展/结论/DOC）===")
        for rq in d.get("tree",[]):
            n_docs = sum(len(m.get("doc_indices",[])) for m in rq.get("methods",[]))
            print(f"\n{rq['rq_id']} · {rq['rq_label']} ({n_docs}篇)")
            for m in rq.get("methods",[]):
                print(f"  {m['method_id']} · {m['method_label']}")
                print(f"    进展: {m['progress'][:100]}...")
                print(f"    结论: {m['conclusion']}")
                print(f"    DOC: {m.get('doc_indices',[])}")
        print(f"\n=== 现有问题 ===")
        print(d.get("problems","")[:300])
        print(f"\n=== 发展趋势 ===")
        print(d.get("trends","")[:300])
    elif code == "ac_domain":
        print(f"专业领域: {d.get('domain_code')}  {d.get('domain_name')}")
        clc = d.get("clc_classification", {}) or {}
        print(f"CLC三级类: {clc.get('clc_code', '')}  {clc.get('name', '')}")
        print(f"路径: {clc.get('classification_path', '')}")
        print(f"理由: {str(d.get('selection_reason', ''))[:250]}")
    elif code.startswith("ac_"):
        mc = d.get("main_classification", {}) or {}
        print(f"主分类: {mc.get('clc_code', '')}  {mc.get('name', '')}")
        print(f"路径: {mc.get('classification_path', '')}")
        aux = d.get("auxiliary_classifications", []) or []
        if aux:
            print(f"辅助分类: {[(a.get('clc_code'), a.get('name')) for a in aux]}")
        print(f"交叉学科: {d.get('is_interdisciplinary')}")
        print(f"理由: {str(d.get('selection_reason', ''))[:200]}")
        print(f"防幻觉: {d.get('alignment_check', {})}")
    elif code.startswith("kw_"):
        for k in d:
            print(f"  {k.get('keyword')}  (weight={k.get('weight')})")
    elif code == "rq_identify":
        if not d:
            print("（未识别到研究问题句）")
        for q in d:
            print(f"  句: {q.get('sentence')}")
            print(f"    短语: {q.get('phrase')}  |  释义: {str(q.get('implication', ''))[:80]}")
    elif code == "ner_relation":
        ents = d.get("entities", []) if isinstance(d, dict) else []
        rels = d.get("relations", []) if isinstance(d, dict) else []
        print(f"实体 {len(ents)} 个 / 关系 {len(rels)} 个")
        print("\n实体:")
        for e in ents:
            print(f"  {e.get('text')}  ({e.get('type', '')})")
        print("\n关系:")
        for r in rels:
            print(f"  {r.get('head')} —[{r.get('relation')}]→ {r.get('tail')}  (conf={r.get('confidence')})")
            if r.get("context"):
                print(f"    上下文: {str(r['context'])[:80]}")
    elif code.startswith("ner_"):
        if not d:
            print("（未识别到实体）")
        for e in d:
            print(f"  {e.get('text')}  ({e.get('type', '')})  conf={e.get('confidence')}  位置={e.get('start')}-{e.get('end')}")
    elif code.startswith("cr_"):
        if not d:
            print("（未识别到引用句）")
        label_field = "sentiment" if code == "cr_sentiment" else "intent"
        for c in d:
            print(f"  [{c.get(label_field, '')}] conf={c.get('confidence')}  {c.get('sentence', '')[:70]}")
            if c.get("citation_marker"):
                print(f"    标记: {c['citation_marker']}")
    elif code == "cd_identify":
        if not d:
            print("（未识别到定义句）")
        for df in d:
            print(f"  概念: {df.get('concept', '')}  conf={df.get('confidence')}")
            print(f"    定义: {df.get('sentence', '')[:90]}")
    else:
        print(json.dumps(d, ensure_ascii=False, indent=2)[:1500])


def get_texts() -> list:
    """多篇输入（dc_cluster 用）：每行一个，支持文件路径(.pdf/.md) / paper JSON / 摘要文本。"""
    print("\n输入多篇文献，每行一个：")
    print("  - 文件路径（.pdf 走MinerU / .md 直接解析）")
    print("  - paper JSON（{\"ch_name\":\"...\",\"ch_abstract\":\"...\",\"keywords\":[...]}）")
    print("  - 纯摘要文本")
    print("空行结束：")
    texts = []
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line and texts:
            break
        if line:
            texts.append(line)
    return texts


def select_domain() -> dict:
    """选专业领域(01-32)，返回 {'domain_code': 'XX'}。"""
    import yaml
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "rules", "auto_classification", "ac_domain.yaml")
    dl = (yaml.safe_load(open(p, encoding="utf-8")) or {}).get("domain_list", []) or []
    print("\n请选择专业领域（输入编号，如 10）：")
    for x in dl:
        print(f"  {x}")
    code = _norm(input("领域编号: "))
    for x in dl:
        if x.split()[0] == code:
            print(f"✅ 已选: {x}")
            return {"domain_code": code}
    print(f"❌ 无效编号: {code}")
    return {}


def select_ner_subtype() -> str | None:
    """NER 子类型选择，返回规则 code（ner_general 等）。"""
    subs = [
        ("1", "ner_general", "通用实体（人名/地名/机构/事件）"),
        ("2", "ner_domain", "领域实体（药物/疾病/化合物，可映射知识库ID）"),
        ("3", "ner_research", "科研实体（模型方法/数据/仪器/理论/研究问题）"),
        ("4", "ner_relation", "实体关系抽取（三元组）"),
    ]
    print("\n请选择 NER 子类型：")
    for n, _, desc in subs:
        print(f"  {n}. {desc}")
    choice = _norm(input("子类型编号: "))
    sel = next((c for n, c, _ in subs if n == choice), None)
    if sel:
        print(f"✅ 已选: {sel}")
    else:
        print(f"❌ 无效编号: {choice}")
    return sel


def select_citation_subtype() -> str | None:
    """引用句识别子类型选择，返回规则 code（cr_intent/cr_sentiment）。"""
    subs = [
        ("1", "cr_intent", "引用意图（背景介绍/引入方法/结果比较）"),
        ("2", "cr_sentiment", "引用情感（支持/中立/有局限性）"),
    ]
    print("\n请选择引用句识别子类型：")
    for n, _, desc in subs:
        print(f"  {n}. {desc}")
    choice = _norm(input("子类型编号: "))
    sel = next((c for n, c, _ in subs if n == choice), None)
    if sel:
        print(f"✅ 已选: {sel}")
    else:
        print(f"❌ 无效编号: {choice}")
    return sel


def select_concurrency() -> int:
    """并发解析数选择（MinerU 解析并发，RTX 3090 实测上限 6）。"""
    print("\n并发解析数（多篇 PDF/MD 走 MinerU 并发解析）:")
    print("  默认 5（安全），最多 6（91% 显存，大/密 PDF 可能 OOM）")
    raw = _norm(input("并发数 [回车=5]: "))
    if not raw:
        return 5
    try:
        return max(1, min(int(raw), 6))
    except ValueError:
        print("❌ 无效，用默认 5")
        return 5


def main():
    while True:
        try:
            print("\n" + "=" * 60)
            print("  语义计算工具库 — 功能点测试菜单")
            print("=" * 60)
            for num, code, _, name, desc in FPS:
                print(f"  {num}. {name}  ({code})  输入: {desc}")
            print("  0. 退出")
            choice = _norm(input("\n选择功能点编号: "))
            if choice == "0":
                print("再见")
                break
            sel = next((f for f in FPS if f[0] == choice), None)
            if not sel:
                print("❌ 无效编号")
                continue
            _, code, item, name, _ = sel
            # NER / 引用句识别：先选子类型，得到具体规则 code
            if code == "ner":
                sub = select_ner_subtype()
                if not sub:
                    continue
                code = sub
            elif code == "cr":
                sub = select_citation_subtype()
                if not sub:
                    continue
                code = sub
            # dc_cluster / cl_label / sr_review 是多篇输入（multi_text）
            if code in ("dc_cluster", "cl_label", "sr_review"):
                texts = get_texts()
                if not texts:
                    print("❌ 未获取到输入")
                    continue
                params = {}
                if code == "sr_review":
                    topic = input("请输入综述主题（如'多变量时间序列异常检测'）: ").strip()
                    if not topic:
                        print("❌ 综述主题不能为空")
                        continue
                    params = {"topic": topic, "cluster_axis": "technical"}
                # 并发解析数（多篇 PDF/MD 走 MinerU 并发解析）
                params["concurrency"] = select_concurrency()
                payload = {"texts": texts, "params": params}
                print(f"\n调用 /api/v1/{item}/{code} （并发解析={params['concurrency']}）...")
                r = client.post(f"/api/v1/{item}/{code}", json=payload, timeout=600).json()
                show(code, r)
                input("\n回车继续（Ctrl+C 退出）...")
                continue
            text = get_text(code)
            if not text:
                print("❌ 未获取到输入文本")
                continue
            params = {}
            if code == "ac_domain":
                params = select_domain()
                if not params:
                    continue
            payload = {"text": text}
            if params:
                payload["params"] = params
            print(f"\n调用 /api/v1/{item}/{code} ...")
            r = client.post(f"/api/v1/{item}/{code}", json=payload, timeout=300).json()
            show(code, r)
            input("\n回车继续（Ctrl+C 退出）...")
        except KeyboardInterrupt:
            print("\n再见")
            break
        except Exception as e:
            print(f"❌ 异常: {e}")
            input("\n回车继续...")


if __name__ == "__main__":
    main()
