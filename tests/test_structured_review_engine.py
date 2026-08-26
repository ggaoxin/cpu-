"""结构化自动综述第一阶段的可重复单元测试。"""
from __future__ import annotations

import unittest
import importlib.util
from pathlib import Path

import numpy as np

from application.service.result_normalizer import normalize_result
from domain.entity.analysis_task import ResultRecord
from infrastructure.structured_review.engine import StructuredReviewEngine


_PROJECTION_SPEC = importlib.util.spec_from_file_location(
    "_structured_review_projection_test",
    Path(__file__).resolve().parents[1] / "infrastructure" / "database" / "result_projection.py",
)
_PROJECTION_MODULE = importlib.util.module_from_spec(_PROJECTION_SPEC)
assert _PROJECTION_SPEC.loader is not None
_PROJECTION_SPEC.loader.exec_module(_PROJECTION_MODULE)
save_result_projection = _PROJECTION_MODULE.save_result_projection


class TopicEncoder:
    """测试专用确定性编码器；不读取 Gold，也不调用外部模型。"""

    def encode(self, texts):
        rows = []
        for text in texts:
            if "图神经网络" in text or "变量依赖" in text:
                rows.append([1.0, 0.05, 0.0])
            elif "联邦" in text or "隐私" in text:
                rows.append([0.02, 1.0, 0.0])
            else:
                rows.append([0.0, 0.0, 1.0])
        return np.asarray(rows, dtype=np.float32)


class EvidenceCheckingGLM:
    """只用于验证模型抽取结果必须通过原文证据校验。"""

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        return {"data": {"items": [
            {
                "question": "如何保护联邦训练中的数据隐私？",
                "evidence_quote": "本文研究联邦环境下数据隐私泄露问题",
                "method": "安全聚合算法",
                "method_evidence_quote": "采用安全聚合算法保护客户端数据",
            },
            {
                "question": "原文不存在的问题",
                "evidence_quote": "这是一条并不存在于原文中的证据",
                "method": "不存在的方法",
                "method_evidence_quote": "不存在的方法证据",
            },
        ]}}


class RecordingSession:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), params))


class StructuredReviewEngineTests(unittest.TestCase):
    def setUp(self):
        self.raw_documents = [
            {"document_id": "D01", "text": "本文研究如何建模多变量之间的依赖关系，并采用图神经网络构建动态邻接矩阵。"},
            {"document_id": "D02", "text": "本研究旨在解决复杂变量依赖难以表达的问题，使用层次图神经网络完成关系建模。"},
            {"document_id": "D03", "text": "本文研究联邦环境下数据隐私泄露问题，采用安全聚合算法保护客户端数据。"},
            {"document_id": "D04", "text": "本研究旨在解决跨机构联邦训练中的隐私风险，使用差分隐私方法限制信息泄露。"},
        ]
        self.metadata = [
            {"document_id": item["document_id"], "title": f"测试文献{index + 1}"}
            for index, item in enumerate(self.raw_documents)
        ]
        self.engine = StructuredReviewEngine(glm=None, encoder=TopicEncoder())

    def test_end_to_end_output_is_evidence_grounded(self):
        documents = self.engine.normalize_documents(self.raw_documents, self.metadata)
        output = self.engine.run(documents, "多变量建模；联邦隐私")

        self.assertEqual(output["document_count"], 4)
        self.assertEqual(output["cluster_induction_results"]["cluster_count"], 2)
        self.assertEqual(output["cluster_induction_results"]["diagnostics"]["representation"], "bge-m3")
        self.assertEqual(output["trend_hotspot_distribution"], {"time_range": None, "hotspots": []})
        self.assertTrue(output["tree"])
        self.assertTrue(output["structured_report"]["sections"])

        text_by_id = {item.document_id: item.text for item in documents}
        evidence_ids = set()
        for evidence in output["evidence_index"]:
            evidence_ids.add(evidence["evidence_id"])
            self.assertIn(evidence["evidence_excerpt"], text_by_id[evidence["document_id"]])
            self.assertEqual(
                text_by_id[evidence["document_id"]][evidence["start"]:evidence["end"]],
                evidence["evidence_excerpt"],
            )
        for section in output["structured_report"]["sections"]:
            self.assertTrue(section["evidence_ids"])
            self.assertTrue(set(section["evidence_ids"]).issubset(evidence_ids))
        for question in output["tree"]:
            for method in question["methods"]:
                self.assertEqual(method["progress"], [])

    def test_duplicate_document_id_is_rejected(self):
        duplicated = list(self.raw_documents) + [{"document_id": "D01", "text": "另一篇文献内容。"}]
        with self.assertRaisesRegex(ValueError, "文献编号重复"):
            self.engine.normalize_documents(duplicated, self.metadata)

    def test_llm_candidate_without_source_quote_is_discarded(self):
        engine = StructuredReviewEngine(glm=EvidenceCheckingGLM(), encoder=TopicEncoder())
        documents = engine.normalize_documents([self.raw_documents[2]], [self.metadata[2]])
        candidates = engine.extract_candidates(documents, "联邦隐私")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].method, "安全聚合算法")
        self.assertIn(candidates[0].question_evidence.quote, documents[0].text)
        self.assertIn(candidates[0].method_evidence.quote, documents[0].text)

    def test_normalized_result_is_projected_to_review_tables(self):
        documents = self.engine.normalize_documents(self.raw_documents, self.metadata)
        raw = self.engine.run(documents, "多变量建模；联邦隐私")
        normalized = normalize_result("structured-review", raw, {
            "document_set": self.raw_documents,
            "topic_or_keywords": "多变量建模；联邦隐私",
        })
        session = RecordingSession()
        save_result_projection(session, ResultRecord(
            id="REC-001", task_id="TASK-001", tool_id="structured-review",
            backend_code="sr_review", result=normalized,
        ))
        sql = "\n".join(statement for statement, _ in session.statements)
        self.assertIn("INSERT INTO review_results", sql)
        self.assertIn("INSERT INTO review_nodes", sql)
        self.assertIn("INSERT INTO review_sections", sql)
        self.assertIn("INSERT INTO review_evidence_links", sql)


if __name__ == "__main__":
    unittest.main()
