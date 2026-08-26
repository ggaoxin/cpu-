from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import numpy as np

from application.dto.common_dto import SemanticRequest
from application.service.cluster_labeling_service import execute_cluster_labeling
from infrastructure.cluster_labeling import (
    ClusterLabelGenerator,
    SemanticClusterLabelGenerator,
    SoftFallbackClusterLabelGenerator,
    create_cluster_label_generator,
    normalize_label_engine_mode,
)


class ClusterLabelGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ClusterLabelGenerator()

    def test_batch_contract_and_report(self) -> None:
        result = self.engine.generate([
            {
                "cluster_id": "T-01",
                "phrases": [
                    {"text": "图神经网络", "weight": 1.0, "frequency": 8},
                    {"text": "时空特征建模", "weight": 0.9, "frequency": 6},
                    {"text": "交通流预测", "weight": 0.8, "frequency": 5},
                ],
            },
            {
                "cluster_id": "T-02",
                "phrases": [
                    {"text": "联邦学习", "weight": 1.0, "frequency": 7},
                    {"text": "隐私保护", "weight": 0.9, "frequency": 6},
                    {"text": "分布式训练", "weight": 0.8, "frequency": 5},
                ],
            },
        ])
        self.assertEqual(result["generation_report"]["input_type"], "cluster_phrase_sets")
        self.assertEqual(result["generation_report"]["cluster_count"], 2)
        self.assertFalse(result["generation_report"]["topic_library_used"])
        self.assertEqual(len(result["labels"]), 2)
        self.assertTrue(all(item["evidence_terms"] for item in result["labels"]))

    def test_single_cluster_mode(self) -> None:
        result = self.engine.generate([
            {"cluster_id": "A-01", "phrases": ["风电设备", "故障诊断", "状态监测"]}
        ])
        self.assertEqual(result["generation_report"]["run_mode"], "single_cluster")

    def test_rejects_missing_phrase_sets(self) -> None:
        with self.assertRaisesRegex(ValueError, "至少包含一个类簇"):
            self.engine.generate([])

    def test_english_length_is_counted_by_words(self) -> None:
        result = self.engine.generate([
            {
                "cluster_id": "E-01",
                "language": "en",
                "phrases": ["graph neural networks", "traffic flow forecasting", "spatiotemporal modeling"],
            }
        ], label_length_limit=8, language_type="en")
        self.assertLessEqual(len(result["labels"][0]["label"].split()), 8)

    def test_chinese_phrase_fusion_is_readable_and_evidence_only(self) -> None:
        variants = self.engine._compose_variants("故障定位", "故障诊断", "zh", 12)
        self.assertIn("故障诊断与定位", variants)
        self.assertTrue(all(len(value) <= 12 for value in variants))

    def test_english_phrase_fusion_preserves_both_concepts(self) -> None:
        variants = self.engine._compose_variants(
            "systematic review", "meta-analysis", "en", 8
        )
        self.assertIn("systematic review and meta-analysis", variants)

    def test_english_phrase_fusion_rejects_morphological_duplicates(self) -> None:
        variants = self.engine._compose_variants("synthesis", "synthesized", "en", 8)
        self.assertEqual(variants, [])

    def test_task_fusion_uses_a_term_present_in_evidence(self) -> None:
        result = self.engine.generate([{
            "cluster_id": "T-01",
            "phrases": ["深度学习", "剩余使用寿命预测", "神经网络"],
        }])
        candidates = result["labels"][0]["candidate_labels"]
        self.assertTrue(any("预测" in value for value in candidates))

    def test_llm_failure_is_audited_and_local_fallback_survives(self) -> None:
        class FailingLLM:
            def chat_json(self, *args, **kwargs):
                raise ConnectionError("offline")

        result = ClusterLabelGenerator(llm_client=FailingLLM()).generate([{
            "cluster_id": "T-01",
            "phrases": ["深度学习", "图像分割", "目标检测"],
        }])
        self.assertEqual(len(result["labels"]), 1)
        self.assertTrue(result["generation_report"]["llm_used"])
        self.assertEqual(result["generation_report"]["llm_failures"][0]["cluster_id"], "T-01")

    def test_ungrounded_llm_candidate_is_rejected(self) -> None:
        class HallucinatingLLM:
            def chat_json(self, *args, **kwargs):
                return {
                    "candidates": [{
                        "label": "量子医学诊断",
                        "evidence_phrases": ["输入中不存在的证据"],
                    }]
                }

        result = ClusterLabelGenerator(llm_client=HallucinatingLLM()).generate([{
            "cluster_id": "T-01",
            "phrases": ["深度学习", "图像分割", "目标检测"],
        }])
        self.assertGreaterEqual(result["generation_report"]["rejected_candidate_count"], 1)
        self.assertNotEqual(result["labels"][0]["label"], "量子医学诊断")

    def test_application_service_uses_client_phrase_set_contract(self) -> None:
        class FakeEncoder:
            def encode(self, texts):
                rows = []
                for index, _ in enumerate(texts):
                    row = np.zeros(4, dtype=float)
                    row[index % 4] = 1.0
                    rows.append(row)
                return np.asarray(rows)

        class FunctionalPoint:
            name = "聚类标签自动生成"

        request = SemanticRequest(params={
            "cluster_phrase_sets": [
                {"cluster_id": "C01", "phrases": ["图神经网络", "故障诊断"]},
                {"cluster_id": "C02", "phrases": ["联邦学习", "隐私保护"]},
            ],
            "generation_mode": "local",
        })
        with patch("application.service.cluster_labeling_service.m3_encoder", FakeEncoder()):
            result = execute_cluster_labeling("cl_label", request, FunctionalPoint(), object())
        self.assertTrue(result.success)
        self.assertEqual(result.data["generation_report"]["direct_input_contract"], "deep_clustering_cluster_phrase_sets")
        self.assertEqual(
            result.data["generation_report"]["effective_label_engine_mode"],
            "bounded_soft_fallback",
        )
        self.assertEqual(
            result.data["generation_report"]["engine_version"],
            "cluster-label-semantic-soft-fallback-v11",
        )
        self.assertEqual(len(result.data["labels"]), 2)
        self.assertEqual(result.data["cluster_count"], 2)
        self.assertEqual(result.data["generated_label_count"], 2)
        self.assertIn("average_confidence", result.data["statistics"])
        self.assertEqual(
            result.data["labels"][0]["recommended_label"],
            result.data["labels"][0]["label"],
        )
        self.assertEqual(
            result.data["labels"][0]["evidence"]["keywords"],
            result.data["labels"][0]["evidence_terms"],
        )

    def test_application_service_can_select_v10_fallback(self) -> None:
        class FakeEncoder:
            def encode(self, texts):
                rows = []
                for index, _ in enumerate(texts):
                    row = np.zeros(8, dtype=float)
                    row[index % 8] = 1.0
                    rows.append(row)
                return np.asarray(rows)

        class FunctionalPoint:
            name = "聚类标签自动生成"

        request = SemanticRequest(params={
            "cluster_phrase_sets": [
                {"cluster_id": "C01", "phrases": ["图神经网络", "故障诊断"]},
                {"cluster_id": "C02", "phrases": ["联邦学习", "隐私保护"]},
            ],
            "generation_mode": "local",
            "label_engine_mode": "v10",
        })
        with patch("application.service.cluster_labeling_service.m3_encoder", FakeEncoder()):
            result = execute_cluster_labeling("cl_label", request, FunctionalPoint(), object())
        self.assertEqual(
            result.data["generation_report"]["effective_label_engine_mode"],
            "semantic_only",
        )
        self.assertEqual(
            result.data["generation_report"]["engine_version"],
            "cluster-label-semantic-only-v10",
        )

    def test_application_service_defaults_to_glm_hybrid_generation(self) -> None:
        class FakeEncoder:
            def encode(self, texts):
                rows = []
                for text in texts:
                    row = np.zeros(16, dtype=float)
                    for char in str(text):
                        row[ord(char) % 16] += 1.0
                    rows.append(row)
                return np.asarray(rows)

        class FakeGLM:
            def __init__(self):
                self.calls = 0

            def chat_json(self, _system, user_prompt, **_kwargs):
                self.calls += 1
                payload = json.loads(user_prompt)
                evidence = payload["evidence_phrases"][:2]
                return {
                    "candidates": [{
                        "label": "综合语义标签",
                        "evidence_phrases": evidence,
                    }]
                }

        class FunctionalPoint:
            name = "聚类标签自动生成"

        glm = FakeGLM()
        request = SemanticRequest(params={
            "cluster_phrase_sets": [
                {"cluster_id": "C01", "phrases": ["图神经网络", "故障诊断"]},
                {"cluster_id": "C02", "phrases": ["联邦学习", "隐私保护"]},
            ],
        })
        with (
            patch("application.service.cluster_labeling_service.m3_encoder", FakeEncoder()),
            patch("application.service.cluster_labeling_service.settings.GLM_API_KEY", "test-key"),
        ):
            result = execute_cluster_labeling("cl_label", request, FunctionalPoint(), glm)

        report = result.data["generation_report"]
        self.assertEqual(glm.calls, 2)
        self.assertEqual(report["requested_generation_mode"], "hybrid")
        self.assertEqual(report["effective_generation_mode"], "hybrid")
        self.assertTrue(report["llm_requested"])
        self.assertTrue(report["llm_candidate_generation_enabled"])
        self.assertEqual(report["llm_model"], "glm-5.2")
        self.assertEqual(report["llm_failure_count"], 0)
        self.assertFalse(report["llm_fallback_used"])

    def test_glm_failure_falls_back_per_cluster_and_is_audited(self) -> None:
        class FakeEncoder:
            def encode(self, texts):
                return np.eye(len(texts), dtype=float)

        class FailingGLM:
            def chat_json(self, *_args, **_kwargs):
                raise ConnectionError("offline")

        class FunctionalPoint:
            name = "聚类标签自动生成"

        request = SemanticRequest(params={
            "cluster_phrase_sets": [{
                "cluster_id": "C01",
                "phrases": ["图神经网络", "故障诊断"],
            }],
        })
        with (
            patch("application.service.cluster_labeling_service.m3_encoder", FakeEncoder()),
            patch("application.service.cluster_labeling_service.settings.GLM_API_KEY", "test-key"),
        ):
            result = execute_cluster_labeling(
                "cl_label", request, FunctionalPoint(), FailingGLM()
            )

        report = result.data["generation_report"]
        self.assertEqual(len(result.data["labels"]), 1)
        self.assertEqual(report["llm_failure_count"], 1)
        self.assertTrue(report["llm_fallback_used"])
        self.assertIn("回退", report["llm_fallback_reason"])

    def test_engine_factory_defaults_to_verified_v11(self) -> None:
        class FakeEncoder:
            def encode(self, texts):
                return np.eye(len(texts), dtype=float)

        engine = create_cluster_label_generator(encoder=FakeEncoder())
        self.assertIsInstance(engine, SoftFallbackClusterLabelGenerator)
        self.assertEqual(normalize_label_engine_mode("v11"), "bounded_soft_fallback")

    def test_engine_factory_keeps_v10_as_explicit_fallback(self) -> None:
        class FakeEncoder:
            def encode(self, texts):
                return np.eye(len(texts), dtype=float)

        engine = create_cluster_label_generator(mode="semantic_only", encoder=FakeEncoder())
        self.assertIsInstance(engine, SemanticClusterLabelGenerator)
        self.assertEqual(normalize_label_engine_mode("v10"), "semantic_only")

    def test_engine_factory_rejects_unknown_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "label_engine_mode"):
            normalize_label_engine_mode("unverified_experiment")

    def test_v11_soft_fallback_is_bounded_and_audited(self) -> None:
        class Candidate:
            def __init__(self, label, evidence, score, relevance, coverage, distinctiveness, origin):
                self.label = label
                self.evidence = evidence
                self.total_score = score
                self.relevance = relevance
                self.coverage = coverage
                self.distinctiveness = distinctiveness
                self.origin = origin

        base = Candidate("图神经网络", ["图神经网络"], 0.72, 0.80, 0.79, 0.70, "semantic_phrase")
        alternative = Candidate(
            "图神经网络与故障诊断",
            ["图神经网络", "故障诊断"],
            0.68,
            0.80,
            0.79,
            0.72,
            "semantic_phrase_pair",
        )
        winner, audit = SoftFallbackClusterLabelGenerator._select_with_soft_fallback(
            [base, alternative],
            0.75,
        )
        self.assertEqual(winner.label, alternative.label)
        self.assertTrue(audit["triggered"])
        self.assertTrue(audit["changed"])
        self.assertLessEqual(audit["contribution"], audit["max_contribution"])
        self.assertLessEqual(audit["max_contribution"], 0.08)
        self.assertFalse(audit["hard_mapping_used"])

    def test_application_service_rejects_raw_text_without_phrase_sets(self) -> None:
        class FunctionalPoint:
            name = "聚类标签自动生成"

        request = SemanticRequest(texts=["raw document text"], params={})
        with self.assertRaisesRegex(ValueError, "cluster_phrase_sets"):
            execute_cluster_labeling("cl_label", request, FunctionalPoint(), object())


if __name__ == "__main__":
    unittest.main()
