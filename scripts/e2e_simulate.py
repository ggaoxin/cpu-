"""端到端用户视角模拟：逐工具提交真实输入，检查可视化字段质量 + DB 持久化 + 资源调用。

模拟前端 OnlineTester 的"在线测试"流程（=直接调 Vue API）。
只观察输出层，不改算法结果。
"""
import json
import os
import sys
import time
import httpx
import pymysql

BASE = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 180.0
OUT_DIR = "/tmp/e2e"
os.makedirs(OUT_DIR, exist_ok=True)

DB = dict(host="127.0.0.1", user="semantic_user", password="change_me", database="semantic_toolkit", charset="utf8mb4")

# 复用 audit 的 CASES（模拟用户输入）
sys.path.insert(0, os.path.dirname(__file__))
from audit_field_mapping import CASES, RELATION_CASE, RESULT_FIELDS

# 需要 DB 资源的工具及其 resource 字段
RESOURCE_TOOLS = {
    "zh-classify": ["clc_labeled_data"],
    "en-classify": ["clc_labeled_data"],
    "domain-classify": ["domain_classification_rules", "manually_labeled_training_data"],
    "en-keyword": ["domain_terminology_library", "classification_standard_mapping_table"],
    "citation-intent": ["preprocessed_training_set"],
    "general-ner": ["general_domain_annotated_corpus"],
    "research-ner": ["multi_domain_scientific_corpus", "manually_labeled_data"],
    "domain-ner": ["ontology_classification_system", "domain_labeled_training_data"],
}


def call(route, payload, client):
    r = client.post(BASE + route, json=payload, timeout=TIMEOUT)
    return r.json()


def db_record_exists(record_id):
    if not record_id:
        return None
    try:
        conn = pymysql.connect(**DB)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id, tool_id, task_id, created_at FROM result_records WHERE id=%s", (record_id,))
            row = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS c FROM task_items WHERE task_id IN (SELECT task_id FROM result_records WHERE id=%s)", (record_id,))
            ti = cur.fetchone()
        conn.close()
        return {"record": row, "task_items": ti["c"] if ti else 0}
    except Exception as e:
        return {"error": str(e)}


def is_empty(v):
    if v is None: return True
    if isinstance(v, (list, dict, str)) and len(v) == 0: return True
    return False


def preview(v, n=120):
    s = json.dumps(v, ensure_ascii=False)
    return s[:n] + ("…" if len(s) > n else "")


def analyze(tool_id, resp, client):
    lines = [f"\n{'='*70}\n=== {tool_id} ==="]
    code = resp.get("code")
    msg = resp.get("message", "")
    data = resp.get("data") or {}
    meta = resp.get("meta") or {}
    record_id = meta.get("record_id") or data.get("record_id") or (data[0].get("record_id") if isinstance(data, list) and data else None)
    lines.append(f"code={code}  record_id={record_id}  msg={msg[:80]}")

    if code != 0:
        lines.append("  [调用失败] 无字段可检")
        return "\n".join(lines), record_id, False

    # 字段质量
    fields = RESULT_FIELDS.get(tool_id, [])
    empty_fields = []
    for f in fields:
        v = data.get(f)
        st = "空" if is_empty(v) else "有内容"
        if is_empty(v):
            empty_fields.append(f)
        lines.append(f"  {f:42s} {st}  {'' if is_empty(v) else preview(v)}")
    if empty_fields:
        lines.append(f"  >> 空字段: {empty_fields}")

    # DB 持久化
    db = db_record_exists(record_id)
    if db and not db.get("error"):
        lines.append(f"  [DB] result_records={'有' if db.get('record') else '无'}  task_items={db.get('task_items')}")
    else:
        lines.append(f"  [DB] 查询失败/无record_id: {db}")

    # 资源调用
    if tool_id in RESOURCE_TOOLS:
        lines.append(f"  [资源] 需 {RESOURCE_TOOLS[tool_id]} → 调用成功(code=0 即资源加载成功)")

    return "\n".join(lines), record_id, (code == 0)


def main():
    client = httpx.Client()
    summary = []
    ner_record = None
    for tool_id, route, payload in CASES:
        try:
            resp = call(route, payload, client)
            with open(f"{OUT_DIR}/{tool_id}.json", "w") as fp:
                json.dump(resp, fp, ensure_ascii=False, indent=2)
            text, rid, ok = analyze(tool_id, resp, client)
            print(text)
            summary.append((tool_id, "OK" if ok else "FAIL", rid))
            if tool_id == "general-ner":
                meta = resp.get("meta") or {}
                ner_record = meta.get("record_id") or (resp.get("data") or {}).get("record_id")
        except Exception as e:
            print(f"\n=== {tool_id} ===\n  [异常] {e}")
            summary.append((tool_id, "EXC", None))

    # relation-extract
    if ner_record:
        try:
            resp = call(RELATION_CASE[1], {"upstream_ner_record_id": ner_record, "upstream_entity_record_id": ner_record}, client)
            with open(f"{OUT_DIR}/relation-extract.json", "w") as fp:
                json.dump(resp, fp, ensure_ascii=False, indent=2)
            text, rid, ok = analyze("relation-extract", resp, client)
            print(text)
            summary.append(("relation-extract", "OK" if ok else "FAIL", rid))
        except Exception as e:
            print(f"\n=== relation-extract ===\n  [异常] {e}")
            summary.append(("relation-extract", "EXC", None))

    print(f"\n{'='*70}\n=== 汇总 ===")
    for t, s, r in summary:
        print(f"  {t:22s} {s:6s} {r or ''}")


if __name__ == "__main__":
    main()
