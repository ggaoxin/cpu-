"""V7.74 public HTTP contract tests for all 19 tools and every Vue input mode.

No real GLM call is made.  The test verifies public field names, routing,
input adaptation, result persistence and the response consumed by the modal.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.service.tool_integration_service import ToolIntegrationService
from application.service.resource_service import ResourceService
from config.vue_contracts import get_vue_contract
from infrastructure.database.connection import Database
from infrastructure.database.resource_repository import DatabaseResourceRepository
from infrastructure.database.task_repository import DatabaseTaskRepository
from presentation.api.v1.integration_controller import get_integration_service, router
from tests.test_fullstack_contracts import FakeSemanticService
from domain.entity.base import SemanticResult


RESOURCE_IDS = {
    "clc_labeled_data": "RES-BUNDLED-CLC-ZH",
    "domain_classification_rules": "RES-BUNDLED-DOMAIN-RULE",
    "manually_labeled_training_data": "RES-BUNDLED-DOMAIN-GOLD",
    "domain_terminology_library": "RES-BUNDLED-EN-TERM",
    "classification_standard_mapping_table": "RES-BUNDLED-EN-CLASS-MAP",
    "preprocessed_training_set": "RES-BUNDLED-CITATION-INTENT",
    "general_domain_annotated_corpus": "RES-BUNDLED-NER-GENERAL",
    "multi_domain_scientific_corpus": "RES-BUNDLED-NER-RESEARCH",
    "manually_labeled_data": "RES-BUNDLED-NER-RESEARCH-GOLD",
    "ontology_classification_system": "RES-BUNDLED-ONTOLOGY",
    "domain_labeled_training_data": "RES-BUNDLED-DOMAIN-NER-GOLD",
}


def resource(field: str):
    return {"source": "database", "resource_id": RESOURCE_IDS[field]}


TEXT_CASES = {
    "zh-abstract-move": ("/move/abstract/zh/text", {"chinese_scientific_abstract": "本文提出语义计算方法。"}),
    "en-abstract-move": ("/move/abstract/en/text", {"english_scientific_abstract": "We propose a semantic computing method."}),
    "fund-move": ("/move/fund/zh/text", {"project_name": "语义计算项目", "project_document_text": "本项目拟研究语义计算方法。"}),
    "zh-classify": ("/classify/clc/zh/text", {"chinese_scientific_document_text": "本文研究知识图谱。", "document_title": "知识图谱研究", "clc_labeled_data": resource("clc_labeled_data")}),
    "en-classify": ("/classify/clc/en/text", {"english_scientific_document_text": "We study knowledge graphs.", "document_title": "Knowledge graph research", "clc_labeled_data": resource("clc_labeled_data")}),
    "domain-classify": ("/classify/domain/text", {"domain_scientific_literature_data": "本文研究合金材料。", "professional_domain": "materials_science", "domain_classification_rules": resource("domain_classification_rules"), "manually_labeled_training_data": resource("manually_labeled_training_data")}),
    "zh-keyword": ("/keywords/zh/text", {"chinese_scientific_abstract": "本文研究语义计算与知识图谱。", "domain_terminology_dictionary": {"use_mode": "system", "source": "system"}}),
    "en-keyword": ("/keywords/en/text", {"english_scientific_abstract": "Semantic computing with knowledge graphs.", "domain_terminology_library": resource("domain_terminology_library"), "classification_standard_mapping_table": resource("classification_standard_mapping_table")}),
    "rq-detect": ("/research-question/text", {"scientific_document_fragment": "现有方法难以处理长文本，如何提升其能力？", "text_format_requirement": "自动识别"}),
    "citation-sentiment": ("/citation-sentiment/text", {"scientific_document_full_text": "已有研究[1]证明该方法有效。", "citation_sentence_and_context": [{"citation_sentence": "已有研究[1]证明该方法有效。", "previous_context": "研究背景。", "next_context": "本文继续研究。"}], "citation_metadata": [{"citation_marker": "[1]", "work_name": "被引文献"}]}),
    "citation-intent": ("/citation-intent/text", {"citation_sentence_and_context": [{"citation_sentence": "本文采用已有方法[1]。", "previous_context": "研究背景。", "next_context": "开展实验。"}], "citation_metadata": [{"citation_marker": "[1]", "work_name": "被引文献"}], "preprocessed_training_set": resource("preprocessed_training_set")}),
    "definition-detect": ("/concept-definition/text", {"scientific_document_fragment_or_batch_text": "语义计算是对文本语义进行结构化计算的方法。", "domain_label": "自动识别", "output_format_requirement": "JSON"}),
    "general-ner": ("/ner/general/text", {"bilingual_scientific_document_text": "燕山大学与剑桥大学开展联合研究。", "general_domain_annotated_corpus": resource("general_domain_annotated_corpus")}),
    "research-ner": ("/ner/research/text", {"academic_abstract_or_technical_report_text": "采用机器学习分析科研数据。", "multi_domain_scientific_corpus": resource("multi_domain_scientific_corpus"), "manually_labeled_data": resource("manually_labeled_data")}),
    "domain-ner": ("/ner/domain/text", {"domain_scientific_document_text": "阿司匹林抑制血小板聚集。", "ontology_classification_system": resource("ontology_classification_system"), "domain_labeled_training_data": resource("domain_labeled_training_data")}),
}


class V774HttpContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database = Database(f"sqlite:///{(Path(self.temp.name) / 'v774.db').as_posix()}")
        database.initialize()
        self.repository = DatabaseTaskRepository(database)
        self.resources = DatabaseResourceRepository(database)
        integration = ToolIntegrationService(FakeSemanticService(), self.repository, self.resources)
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1")
        self.app.dependency_overrides[get_integration_service] = lambda: integration
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def assert_public_result(self, tool_id: str, body: dict, *, batch: bool = False):
        self.assertEqual(body.get("code"), 0, body)
        rows = body["data"].get("results", []) if batch else [{"result": body["data"]}]
        self.assertTrue(rows, body)
        for row in rows:
            if batch:
                self.assertEqual(row["status"], "succeeded", row)
            result = row["result"]
            for field in get_vue_contract(tool_id).result_fields:
                self.assertIn(field, result, (tool_id, field, result.keys()))
        self.assertTrue(body.get("meta", {}).get("task_id"), body)

    def test_all_single_text_contracts(self):
        for tool_id, (path, payload) in TEXT_CASES.items():
            with self.subTest(tool_id=tool_id):
                response = self.client.post(f"/api/v1{path}", json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assert_public_result(tool_id, response.json())

    def test_all_batch_text_contracts(self):
        for tool_id, (single_path, payload) in TEXT_CASES.items():
            if tool_id in {"citation-sentiment", "citation-intent"}:
                repeated = dict(payload)
                repeated["citation_sentence_and_context"] = payload["citation_sentence_and_context"] * 2
                if isinstance(payload.get("scientific_document_full_text"), str):
                    repeated["scientific_document_full_text"] = [{"id": "T1", "text": payload["scientific_document_full_text"]}, {"id": "T2", "text": payload["scientific_document_full_text"]}]
            else:
                repeated = dict(payload)
                primary = get_vue_contract(tool_id).primary_input_field
                value = payload[primary]
                repeated[primary] = [{"id": "T1", "text": value}, {"id": "T2", "text": value}]
                if tool_id == "fund-move":
                    repeated[primary] = [{"project_name": "项目一", "text": value}, {"project_name": "项目二", "text": value}]
            path = single_path.removesuffix("/text") + "/texts"
            with self.subTest(tool_id=tool_id):
                response = self.client.post(f"/api/v1{path}", json=repeated)
                self.assertEqual(response.status_code, 200, response.text)
                self.assert_public_result(tool_id, response.json(), batch=True)

    def test_relation_cluster_label_deep_cluster_and_review(self):
        ner_response = self.client.post("/api/v1/ner/general/text", json=TEXT_CASES["general-ner"][1]).json()
        relation = self.client.post("/api/v1/relation/from-ner-record", json={
            "upstream_ner_record_id": ner_response["meta"]["record_id"],
        })
        self.assertEqual(relation.status_code, 200, relation.text)
        self.assert_public_result("relation-extract", relation.json())

        phrase_sets = [
            {"cluster_id": "C1", "phrases": ["知识图谱", "语义计算"]},
            {"cluster_id": "C2", "phrases": ["机器学习", "文本分类"]},
        ]
        labels = self.client.post("/api/v1/cluster-labels/generate", json={
            "cluster_phrase_sets": phrase_sets, "label_length_limit": 12,
            "language_type": "auto", "distinctiveness_threshold": 0.75,
        })
        self.assertEqual(labels.status_code, 200, labels.text)
        self.assert_public_result("cluster-label", labels.json())

        documents = [{"document_id": f"D{i}", "text": f"第{i}篇语义计算科技文本"} for i in range(1, 5)]
        metadata = [{"document_id": f"D{i}", "title": f"文献{i}", "publication_date": f"202{i}-01-01"} for i in range(1, 5)]
        deep = self.client.post("/api/v1/cluster/deep/texts", json={
            "scientific_document_texts": documents, "document_metadata": metadata,
            "cluster_dimension": "technology", "clustering_algorithm_type": "auto",
            "cluster_count": None, "output_format": "JSON",
        })
        self.assertEqual(deep.status_code, 200, deep.text)
        self.assert_public_result("deep-cluster", deep.json())

        review = self.client.post("/api/v1/review/structured/texts", json={
            "document_set": documents[:3], "topic_or_keywords": "语义计算",
            "document_metadata": metadata[:3],
        })
        self.assertEqual(review.status_code, 200, review.text)
        self.assert_public_result("structured-review", review.json())

    def test_cluster_label_phrase_sets_reach_production_request_and_history_route(self):
        class CapturingService(FakeSemanticService):
            def __init__(self):
                self.calls = []

            def execute(self, code, request):
                self.calls.append((code, request))
                return super().execute(code, request)

        algorithm = CapturingService()
        integration = ToolIntegrationService(algorithm, self.repository, self.resources)
        self.app.dependency_overrides[get_integration_service] = lambda: integration
        phrase_sets = [
            {"cluster_id": "C1", "phrases": ["知识图谱", "语义计算"]},
            {"cluster_id": "C2", "phrases": ["机器学习", "文本分类"]},
        ]
        direct = self.client.post("/api/v1/cluster-labels/generate", json={
            "cluster_phrase_sets": phrase_sets, "label_length_limit": 12,
            "language_type": "auto", "distinctiveness_threshold": 0.75,
        })
        self.assertEqual(direct.status_code, 200, direct.text)
        direct_request = [call[1] for call in algorithm.calls if call[0] == "cl_label"][-1]
        self.assertEqual(direct_request.params["cluster_phrase_sets"], phrase_sets)

        documents = [{"document_id": f"D{i}", "text": f"第{i}篇语义计算文本"} for i in range(1, 5)]
        metadata = [{"document_id": f"D{i}", "publication_date": f"202{i}-01-01"} for i in range(1, 5)]
        deep = self.client.post("/api/v1/cluster/deep/texts", json={
            "scientific_document_texts": documents, "document_metadata": metadata,
            "cluster_dimension": "technology", "clustering_algorithm_type": "auto",
            "cluster_count": None, "output_format": "JSON",
        })
        self.assertEqual(deep.status_code, 200, deep.text)
        history = self.client.post("/api/v1/cluster-labels/from-cluster-task", json={
            "cluster_task_id": deep.json()["meta"]["task_id"],
            "label_length_limit": 12, "language_type": "auto", "distinctiveness_threshold": 0.75,
        })
        self.assertEqual(history.status_code, 200, history.text)
        self.assert_public_result("cluster-label", history.json())
        history_request = [call[1] for call in algorithm.calls if call[0] == "cl_label"][-1]
        self.assertTrue(history_request.params["cluster_phrase_sets"])

    def test_every_file_and_batch_file_route_uses_public_primary_field(self):
        file_tools = {tool_id: value for tool_id, value in TEXT_CASES.items() if tool_id != "citation-intent"}
        file_tools["citation-intent"] = TEXT_CASES["citation-intent"]
        for tool_id, (text_path, payload) in file_tools.items():
            contract = get_vue_contract(tool_id)
            base_path = text_path.removesuffix("/text")
            extra = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
                     for key, value in payload.items() if key != contract.primary_input_field}
            for suffix, count in (("/file", 1), ("/files", 2)):
                files = [(contract.primary_input_field, (f"paper{i}.txt", b"semantic computing text [1]", "text/plain")) for i in range(count)]
                with self.subTest(tool_id=tool_id, suffix=suffix):
                    response = self.client.post(f"/api/v1{base_path}{suffix}", data=extra, files=files)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assert_public_result(tool_id, response.json(), batch=count > 1)

    def test_database_records_every_successful_request(self):
        response = self.client.post("/api/v1/move/abstract/zh/text", json=TEXT_CASES["zh-abstract-move"][1])
        task_id = response.json()["meta"]["task_id"]
        self.assertIsNotNone(self.repository.get_task(task_id))
        with self.repository.db.session() as session:
            self.assertGreater(session.fetchone("SELECT COUNT(*) total FROM result_records")["total"], 0)
            self.assertEqual(session.fetchone("SELECT COUNT(*) total FROM semantic_resources")["total"], 14)

    def test_independent_deep_cluster_evaluation_uses_real_gold_and_persists_run(self):
        class EvaluationSemanticService:
            def execute(_, code, request):
                self.assertEqual(code, "dc_cluster")
                documents = []
                for raw in request.texts or []:
                    row = json.loads(raw)
                    label = "C-A" if "甲类" in row["text"] else "C-B"
                    documents.append({
                        "document_id": row["document_id"],
                        "technical": {"topic_id": label},
                        "application": {"topic_id": label},
                    })
                return SemanticResult(code=code, name=code, success=True, data={
                    "documents": documents,
                    "clustering_quality": {"silhouette_score": 0.81},
                })

        rows = [
            {"document_id": "D1", "text": "甲类 文本一", "technical_cluster_id": "C-A"},
            {"document_id": "D2", "text": "甲类 文本二", "technical_cluster_id": "C-A"},
            {"document_id": "D3", "text": "乙类 文本三", "technical_cluster_id": "C-B"},
            {"document_id": "D4", "text": "乙类 文本四", "technical_cluster_id": "C-B"},
        ]
        source = Path(self.temp.name) / "evaluation.json"
        source.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        for resource_id, key in (("RES-TEST-TRAIN", "training_samples"), ("RES-TEST-GOLD", "manually_labeled_category_data")):
            self.resources.register_semantic_resource("default", {
                "id": resource_id, "resource_key": key, "name": key,
                "version": "test", "status": "current", "source_type": "test",
                "storage_uri": source.as_posix(),
            })
        integration = ToolIntegrationService(EvaluationSemanticService(), self.repository, self.resources)
        self.app.dependency_overrides[get_integration_service] = lambda: integration
        response = self.client.post("/api/v1/cluster/deep/evaluate", json={
            "training_samples": {"source": "database", "resource_id": "RES-TEST-TRAIN"},
            "manually_labeled_category_data": {"source": "database", "resource_id": "RES-TEST-GOLD"},
            "cluster_dimension": "technology",
        })
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["metrics"]["adjusted_rand_index"], 1.0)
        with self.repository.db.session() as session:
            self.assertEqual(session.fetchone("SELECT COUNT(*) total FROM model_evaluation_runs")["total"], 1)

    def test_batch_titles_and_project_names_remain_bound_to_each_item(self):
        classification = self.client.post("/api/v1/classify/clc/zh/texts", json={
            "chinese_scientific_document_text": [
                {"id": "D1", "title": "第一篇文献", "text": "第一篇知识图谱研究。"},
                {"id": "D2", "title": "第二篇文献", "text": "第二篇语义计算研究。"},
            ],
            "document_title": ["第一篇文献", "第二篇文献"],
            "clc_labeled_data": resource("clc_labeled_data"),
        })
        self.assertEqual(classification.status_code, 200, classification.text)
        titles = [item["result"]["document_title"] for item in classification.json()["data"]["results"]]
        self.assertEqual(titles, ["第一篇文献", "第二篇文献"])

        research_questions = self.client.post("/api/v1/research-question/texts", json={
            "scientific_document_fragment": [
                {"id": "Q1", "title": "问题文献甲", "text": "现有方法有什么不足？"},
                {"id": "Q2", "title": "问题文献乙", "text": "如何提升模型精度？"},
            ],
            "document_title": ["问题文献甲", "问题文献乙"],
            "text_format_requirement": "自动识别",
        })
        self.assertEqual(research_questions.status_code, 200, research_questions.text)
        rq_titles = [item["result"]["document"]["title"] for item in research_questions.json()["data"]["results"]]
        self.assertEqual(rq_titles, ["问题文献甲", "问题文献乙"])

        projects = self.client.post("/api/v1/move/fund/zh/texts", json={
            "project_document_text": [
                {"project_name": "项目甲", "text": "项目甲研究内容。"},
                {"project_name": "项目乙", "text": "项目乙研究内容。"},
            ],
        })
        self.assertEqual(projects.status_code, 200, projects.text)
        names = [item["result"]["document"]["title"] for item in projects.json()["data"]["results"]]
        self.assertEqual(names, ["项目甲", "项目乙"])

    def test_batch_citation_context_and_metadata_are_isolated_per_item(self):
        class CapturingService(FakeSemanticService):
            def __init__(self):
                self.requests = []

            def execute(self, code, request):
                if code == "cr_intent":
                    self.requests.append(request)
                return super().execute(code, request)

        algorithm = CapturingService()
        integration = ToolIntegrationService(algorithm, self.repository, self.resources)
        self.app.dependency_overrides[get_integration_service] = lambda: integration
        contexts = [
            {"citation_sentence": "第一篇采用方法[1]。", "previous_context": "甲上文", "next_context": "甲下文"},
            {"citation_sentence": "第二篇比较结果[2]。", "previous_context": "乙上文", "next_context": "乙下文"},
        ]
        metadata = [
            {"citation_marker": "[1]", "work_name": "被引文献甲"},
            {"citation_marker": "[2]", "work_name": "被引文献乙"},
        ]
        response = self.client.post("/api/v1/citation-intent/texts", json={
            "citation_sentence_and_context": contexts,
            "citation_metadata": metadata,
            "preprocessed_training_set": resource("preprocessed_training_set"),
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(algorithm.requests), 2)
        self.assertEqual(algorithm.requests[0].params["citation_sentence_and_context"], [contexts[0]])
        self.assertEqual(algorithm.requests[1].params["citation_sentence_and_context"], [contexts[1]])
        self.assertEqual(algorithm.requests[1].params["citation_metadata"], [metadata[1]])

    def test_deep_and_review_file_metadata_and_collection_inputs_reach_algorithms(self):
        class CapturingService(FakeSemanticService):
            def __init__(self):
                self.calls = []

            def execute(self, code, request):
                self.calls.append((code, request))
                return super().execute(code, request)

        algorithm = CapturingService()
        integration = ToolIntegrationService(algorithm, self.repository, self.resources)
        self.app.dependency_overrides[get_integration_service] = lambda: integration

        deep_metadata = [
            {"document_id": f"D{i}", "title": f"深度文献{i}", "publication_date": f"202{i}-01-01",
             "authors": [f"作者{i}"], "source": "测试期刊", "keywords": ["聚类"]}
            for i in range(1, 5)
        ]
        deep_files = [
            ("scientific_document_texts", (f"deep{i}.txt", f"第{i}篇深度聚类文本".encode(), "text/plain"))
            for i in range(1, 5)
        ]
        deep = self.client.post("/api/v1/cluster/deep/files", data={
            "document_metadata": json.dumps(deep_metadata, ensure_ascii=False),
            "cluster_dimension": "technology", "clustering_algorithm_type": "auto",
            "output_format": "JSON",
        }, files=deep_files)
        self.assertEqual(deep.status_code, 200, deep.text)
        self.assert_public_result("deep-cluster", deep.json())
        _, deep_request = next(call for call in algorithm.calls if call[0] == "dc_cluster")
        deep_rows = [json.loads(value) for value in deep_request.texts]
        self.assertEqual([row["document_id"] for row in deep_rows], ["D1", "D2", "D3", "D4"])
        self.assertEqual(deep_rows[2]["publication_date"], "2023-01-01")
        self.assertEqual(deep_rows[2]["title"], "深度文献3")

        review_metadata = [
            {"document_id": f"R{i}", "title": f"综述文献{i}", "authors": [f"团队{i}"],
             "institutions": [f"机构{i}"], "publication_date": f"202{i}-06-01",
             "source": "综述期刊", "keywords": ["语义计算"]}
            for i in range(1, 4)
        ]
        review_files = [
            ("document_set", (f"review{i}.txt", f"第{i}篇结构化综述文本".encode(), "text/plain"))
            for i in range(1, 4)
        ]
        review_files.append((
            "document_metadata",
            ("review_metadata.json", json.dumps(review_metadata, ensure_ascii=False).encode(), "application/json"),
        ))
        review = self.client.post("/api/v1/review/structured/files", data={
            "topic_or_keywords": "语义计算",
        }, files=review_files)
        self.assertEqual(review.status_code, 200, review.text)
        self.assert_public_result("structured-review", review.json())
        review_request = [call[1] for call in algorithm.calls if call[0] == "sr_review"][-1]
        review_rows = [json.loads(value) for value in review_request.texts]
        self.assertEqual(review_rows[1]["document_id"], "R2")
        self.assertEqual(review_rows[1]["institutions"], ["机构2"])
        self.assertEqual(review_rows[1]["publication_date"], "2022-06-01")

        collection = ResourceService(self.resources).create_collection({
            "name": "数据库综述文献集",
            "documents": [
                {"document_id": f"C{i}", "title": f"集合文献{i}", "text": f"集合文本{i}",
                 "publication_date": f"202{i}-08-01", "authors": [f"集合作者{i}"]}
                for i in range(1, 4)
            ],
        })
        collection_review = self.client.post("/api/v1/review/structured/collections", json={
            "document_set": {"source": "database", "collection_id": collection["id"]},
            "topic_or_keywords": "数据库综述",
            "document_metadata": {"source": "collection", "collection_id": collection["id"]},
        })
        self.assertEqual(collection_review.status_code, 200, collection_review.text)
        self.assert_public_result("structured-review", collection_review.json())
        collection_request = [call[1] for call in algorithm.calls if call[0] == "sr_review"][-1]
        self.assertEqual(len(collection_request.texts), 3)

    def test_relation_history_uses_the_exact_selected_batch_ner_text(self):
        class CapturingService(FakeSemanticService):
            def __init__(self):
                self.calls = []

            def execute(self, code, request):
                self.calls.append((code, request))
                return super().execute(code, request)

        algorithm = CapturingService()
        integration = ToolIntegrationService(algorithm, self.repository, self.resources)
        self.app.dependency_overrides[get_integration_service] = lambda: integration
        source_texts = ["第一篇文本：燕山大学研发模型。", "第二篇文本：剑桥大学验证算法。"]
        ner = self.client.post("/api/v1/ner/general/texts", json={
            "bilingual_scientific_document_text": [
                {"id": "NER-1", "text": source_texts[0]},
                {"id": "NER-2", "text": source_texts[1]},
            ],
            "general_domain_annotated_corpus": resource("general_domain_annotated_corpus"),
        })
        self.assertEqual(ner.status_code, 200, ner.text)
        rows = ner.json()["data"]["results"]
        second_record_id = rows[1]["record_id"]

        history = self.client.get("/api/v1/history/compatible", params={
            "downstream_tool": "relation-extract", "upstream_type": "entity",
        })
        self.assertEqual(history.status_code, 200, history.text)
        by_record = {item["record_id"]: item for item in history.json()["data"]}
        self.assertEqual(by_record[rows[0]["record_id"]]["sentence"], source_texts[0])
        self.assertEqual(by_record[second_record_id]["sentence"], source_texts[1])

        relation = self.client.post("/api/v1/relation/from-ner-record", json={
            "upstream_ner_record_id": second_record_id,
        })
        self.assertEqual(relation.status_code, 200, relation.text)
        relation_request = [request for code, request in algorithm.calls if code == "ner_relation"][-1]
        self.assertEqual(relation_request.text, source_texts[1])


if __name__ == "__main__":
    unittest.main()
