"""HTTP integration coverage for the first five Vue tool families."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from application.service.tool_integration_service import ToolIntegrationService
from config.settings import settings
from domain.entity.base import SemanticResult
from infrastructure.database.connection import Database
from infrastructure.database.resource_repository import DatabaseResourceRepository
from infrastructure.database.task_repository import DatabaseTaskRepository
from presentation.api.v1.integration_controller import get_integration_service, router

from tests.test_fullstack_contracts import FakeSemanticService

ZH_ABSTRACT = "本文提出知识图谱方法，实验结果表明该方法能提升语义分析精度。"
EN_ABSTRACT = "We propose a knowledge graph method. Results show improved semantic analysis accuracy."
FUND_TEXT = "立项依据。研究目标。技术实施方案。预期成果。应用价值。"
CITATION_TEXT = "已有研究[1]证明该方法有效。本文采用李四等（2021）的方法作为基线。"


class StubSemanticService(FakeSemanticService):
    """HTTP boundary stub; GLM failure behavior is covered separately."""
    def execute(self, code, request):
        if code in {"kw_zh", "kw_en"}:
            custom = request.params.get("custom_dictionary") or {}
            english = code == "kw_en"
            keyword = "deep learning" if english else "知识图谱"
            mapping = {
                "system": "CLC", "code": "TP391", "label": "人工智能",
                "classification_path": ["工业技术", "自动化技术、计算机技术", "人工智能"],
                "confidence": 0.9,
            } if english else None
            return SemanticResult(code=code, name=code, success=True, data={
                "keywords": [{
                    "keyword": keyword, "weight": 0.9,
                    "custom_dictionary_hit": bool(custom),
                    "classification_mapping": mapping,
                }],
                "dictionary_usage": {
                    "dictionary_id": custom.get("id"),
                    "version_id": custom.get("version_id"),
                    "version": custom.get("version"),
                    "matched_term_count": 1,
                } if custom else None,
            })
        return super().execute(code, request)


class FiveToolHttpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        database = Database(f"sqlite:///{(root / 'http.db').as_posix()}")
        database.initialize()
        self.repository = DatabaseTaskRepository(database)
        self.resource_repository = DatabaseResourceRepository(database)
        integration = ToolIntegrationService(StubSemanticService(), self.repository, self.resource_repository)
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_integration_service] = lambda: integration
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.temporary_directory.cleanup()

    def assert_success(self, response, expected_field):
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["code"], 0, body)
        result = body["data"]
        self.assertIn(expected_field, result)
        record_id = body.get("meta", {}).get("record_id")
        self.assertTrue(record_id, body)
        stored = self.repository.get_result(record_id)
        self.assertIsNotNone(stored)
        return result

    def test_json_routes(self):
        cases = (
            ("/api/v1/move/abstract/zh/text", {"chinese_scientific_abstract": ZH_ABSTRACT}, "moves"),
            ("/api/v1/move/abstract/en/text", {"english_scientific_abstract": EN_ABSTRACT}, "moves"),
            ("/api/v1/classify/clc/zh/text", {
                "document_title": "基于知识图谱的科技文献语义分析",
                "chinese_scientific_document_text": "研究自然语言处理、深度学习与知识图谱方法。",
                "clc_labeled_data": {"source": "database", "resource_id": "RES-BUNDLED-CLC-ZH"},
            }, "classifications"),
            ("/api/v1/classify/clc/en/text", {
                "document_title": "Knowledge graph based semantic analysis",
                "english_scientific_document_text": "We study natural language processing and deep learning.",
                "clc_standard_and_mapping_rules": {"source": "database", "resource_id": "RES-BUNDLED-CLC-MAP"},
            }, "classifications"),
            ("/api/v1/classify/domain/text", {
                "professional_domain": "materials_science", "document_title": "合金材料微观结构分析",
                "domain_scientific_literature_data": "研究金属材料与晶界演化。",
                "domain_classification_rules": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-RULE"},
                "manually_labeled_training_data": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-GOLD"},
            }, "classifications"),
            ("/api/v1/keywords/zh/text", {"chinese_scientific_abstract": ZH_ABSTRACT, "domain_terminology_dictionary": {"use_mode": "system", "source": "system"}}, "keywords"),
            ("/api/v1/keywords/en/text", {"english_scientific_abstract": EN_ABSTRACT, "domain_terminology_library": {"source": "database", "resource_id": "RES-BUNDLED-EN-TERM"}, "classification_standard_mapping_table": {"source": "database", "resource_id": "RES-BUNDLED-EN-CLASS-MAP"}}, "keywords"),
            ("/api/v1/research-question/text", {"scientific_document_fragment": ZH_ABSTRACT}, "research_question_sentences"),
        )
        for path, payload, expected_field in cases:
            with self.subTest(path=path):
                result = self.assert_success(self.client.post(path, json=payload), expected_field)
                self.assertTrue(result[expected_field], result)

    def test_file_routes_for_fund_and_citations(self):
        cases = (
            ("/api/v1/move/fund/zh/file", "fund.txt", FUND_TEXT, "moves"),
            ("/api/v1/citation/sentiment/file", "citation.txt", CITATION_TEXT, "citation_sentiment_results"),
            ("/api/v1/citation/intent/file", "citation.txt", CITATION_TEXT, "citation_intent_results"),
        )
        for path, filename, content, expected_field in cases:
            with self.subTest(path=path):
                extra = {"citation_metadata": json.dumps({"source": "file_auto_parse"})} if "citation" in path else {}
                if "intent" in path:
                    extra["preprocessed_training_set"] = json.dumps({"source": "database", "resource_id": "RES-BUNDLED-CITATION-INTENT"})
                response = self.client.post(
                    path,
                    data=extra,
                    files={"file": (filename, content.encode("utf-8"), "text/plain")},
                )
                result = self.assert_success(response, expected_field)
                self.assertTrue(result[expected_field], result)
                self.assertTrue(result[expected_field])

    def test_validation_and_cors(self):
        invalid = self.client.post("/api/v1/classify/domain/text", json={
            "input_type": "text", "title": "测试", "abstract": "测试摘要",
        })
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["code"], 42201)
        with self.repository.db.session() as session:
            count = session.fetchone("SELECT COUNT(*) AS total FROM analysis_tasks")["total"]
        self.assertEqual(count, 0)

        preflight = self.client.options(
            "/api/v1/keywords/zh/text",
            headers={
                "Origin": "http://127.0.0.1:6006",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(preflight.status_code, 200, preflight.text)
        self.assertEqual(preflight.headers.get("access-control-allow-origin"), "http://127.0.0.1:6006")

    def test_keyword_dictionary_and_range_validation(self):
        from application.service.resource_service import ResourceService

        resources = ResourceService(self.resource_repository)
        dictionary = resources.create_dictionary({
            "name": "中文校验词典_20260813_1300",
            "language": "zh",
            "weight_boost": 0.08,
            "terms": ["知识图谱", "知识图谱", "深度学习"],
        })
        self.assertEqual(dictionary["term_count"], 2)

        invalid_requests = (
            {"input_type": "text", "abstract": EN_ABSTRACT, "dictionary_id": dictionary["id"]},
            {"input_type": "text", "abstract": EN_ABSTRACT, "min_keywords": 9, "max_keywords": 3},
            {"input_type": "text", "abstract": EN_ABSTRACT, "custom_dictionary": {
                "name": "bad", "weight_boost": 0.8, "terms": ["deep learning"],
            }},
        )
        for payload in invalid_requests:
            with self.subTest(payload=payload):
                response = self.client.post("/api/v1/keywords/en/text", json=payload)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["code"], 42201)

    def test_dictionary_version_keyword_hit_mapping_and_classification_confirmation(self):
        from application.service.resource_service import ResourceService
        from application.service.result_governance_service import ResultGovernanceService
        from presentation.api.v1 import integration_controller

        resources = ResourceService(self.resource_repository)
        dictionary = resources.create_dictionary({
            "name": "Semantic Terms_20260813_1200",
            "language": "zh",
            "weight_boost": 0.08,
            "terms": ["deep learning", "knowledge graph"],
        })
        keyword = self.client.post("/api/v1/keywords/zh/text", json={
            "chinese_scientific_abstract": ZH_ABSTRACT,
            "domain_terminology_dictionary": {
                "use_mode": "saved", "source": "database", "resource_id": dictionary["id"],
            },
        })
        keyword_result = self.assert_success(keyword, "keywords")
        hit = next(row for row in keyword_result["keywords"] if row["keyword"] == "知识图谱")
        self.assertTrue(hit["custom_dictionary_hit"])
        self.assertEqual(keyword_result["dictionary_usage"]["dictionary_id"], dictionary["id"])
        self.assertEqual(keyword_result["dictionary_usage"]["version_id"], dictionary["version_id"])

        classification = self.client.post("/api/v1/classify/domain/text", json={
            "professional_domain": "materials_science",
            "document_title": "合金材料微观结构分析",
            "domain_scientific_literature_data": "研究金属材料与晶界演化。",
            "domain_classification_rules": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-RULE"},
            "manually_labeled_training_data": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-GOLD"},
        }).json()
        record_id = classification["meta"]["record_id"]
        candidate = classification["data"]["candidate_classifications"][0]
        original_governance = integration_controller.result_governance_service
        integration_controller.result_governance_service = ResultGovernanceService(self.repository)
        try:
            confirmed = self.client.post(
                f"/api/v1/classification-results/{record_id}/confirm",
                json={
                    "primary_code": candidate["classification_code"],
                    "candidate_id": candidate["candidate_id"],
                    "confirmed_path": candidate["classification_path"],
                },
            )
        finally:
            integration_controller.result_governance_service = original_governance
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["data"]["status"], "confirmed")
        stored = self.repository.get_result(record_id)["result"]
        self.assertEqual(stored["confirmation_status"], "confirmed")
        self.assertEqual(stored["manual_confirmation"]["confirmed_candidate_id"], candidate["candidate_id"])


if __name__ == "__main__":
    unittest.main()
