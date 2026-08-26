"""Vue、DDD 应用服务和数据库之间的 19 功能契约测试，不调用真实大模型。"""
from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from application.service.export_service import ExportService
from application.service.resource_service import ResourceService
from application.service.result_governance_service import ResultGovernanceService
from application.service.tool_integration_service import ToolIntegrationService
from application.service.upstream_record_service import UpstreamRecordService
from config.tool_contracts import CONTRACTS
from config.vue_contracts import get_vue_contract
from domain.entity.base import SemanticResult
from infrastructure.database.connection import Database
from infrastructure.database.resource_repository import DatabaseResourceRepository
from infrastructure.database.task_repository import DatabaseTaskRepository


class FakeSemanticService:
    def execute(self, code, request):
        return SemanticResult(code=code, name=code, success=True, data=self._data(code))

    @staticmethod
    def _data(code):
        if code in {"mr_zh_abstract", "mr_en_abstract"}:
            return [{"label": "研究目的", "text": "研究一种语义计算方法", "confidence": 0.93}]
        if code == "mr_zh_fund":
            return [{"move_type": "研究内容", "content": "构建知识图谱", "confidence": 0.91}]
        if code in {"ac_zh", "ac_en"}:
            return {"main_classification": {"clc_code": "TP391", "label": "人工智能", "score": 0.94}, "auxiliary_classifications": []}
        if code == "ac_domain":
            return {"domain_code": "14", "domain_name": "材料科学", "clc_classification": {"clc_code": "TG", "label": "金属材料", "score": 0.9}}
        if code in {"kw_zh", "kw_en"}:
            return [{"keyword": "语义计算", "weight": 0.9}, {"keyword": "知识图谱", "weight": 0.8}]
        if code == "rq_identify":
            return [{"sentence": "现有方法仍难以处理长文本。", "phrase": "长文本处理", "implication": "如何提升长文本处理能力", "confidence": 0.88}]
        if code == "cr_sentiment":
            return [{"sentence": "该方法显著提升精度。", "sentiment": "支持", "confidence": 0.87}]
        if code == "cr_intent":
            return [{"sentence": "采用该方法作为基线。", "intent": "方法", "confidence": 0.86}]
        if code == "cd_identify":
            return [{"concept": "语义计算", "definition": "对文本语义进行结构化计算", "confidence": 0.9}]
        if code in {"ner_general", "ner_research", "ner_domain"}:
            return [{"entity": "知识图谱", "type": "METHOD", "confidence": 0.92}]
        if code == "ner_relation":
            return [{"subject": "模型", "predicate": "使用", "object": "知识图谱", "confidence": 0.89}]
        if code == "dc_cluster":
            return {"technical_topics": [{"topic_id": "C1", "topic_name": "语义建模", "doc_indices": [0, 1], "keywords": ["语义", "模型"]}]}
        if code == "cl_label":
            return {"clusters": [{"cluster_id": "C1", "label": "语义建模方法", "confidence": 0.9}]}
        if code == "sr_review":
            return {
                "tree": [{
                    "question_id": "RQ-01", "research_question": "如何增强语义建模",
                    "document_count": 1,
                    "methods": [{"method_id": "M-01", "method": "知识图谱方法", "progress": []}],
                }],
                "cluster_induction_results": {"cluster_count": 1, "clusters": []},
                "structured_report": {"overview": "语义建模综述", "sections": []},
                "trend_hotspot_distribution": {"time_range": None, "hotspots": []},
                "evidence_index": [{
                    "evidence_id": "EV-001", "document_id": "D1", "title": "文献一",
                    "source_section": "text", "evidence_excerpt": "语义模型研究",
                    "quote": "语义模型研究", "supported_nodes": ["RQ-01"],
                }],
            }
        raise AssertionError(f"缺少假输出：{code}")


class CapturingKeywordService:
    def __init__(self):
        self.request = None

    def execute(self, code, request):
        self.request = request
        dictionary = request.params.get("custom_dictionary") or {}
        return SemanticResult(code=code, name=code, success=True, data={
            "keywords": [{"keyword": "语义计算", "weight": 0.9, "custom_dictionary_hit": True}],
            "dictionary_usage": {
                "dictionary_id": dictionary.get("id"),
                "version_id": dictionary.get("version_id"),
                "version": dictionary.get("version"),
                "matched_term_count": 1,
            },
            "statistics": {"keyword_count": 1},
        })


def repositories(root: Path):
    db = Database(f"sqlite:///{(root / 'test.db').as_posix()}")
    db.initialize()
    return DatabaseTaskRepository(db), DatabaseResourceRepository(db)


def payload_for(tool_id):
    resource_ids = {
        "zh-classify": {"clc_labeled_data": "RES-BUNDLED-CLC-ZH"},
        "en-classify": {"clc_labeled_data": "RES-BUNDLED-CLC-ZH"},
        "domain-classify": {
            "domain_classification_rules": "RES-BUNDLED-DOMAIN-RULE",
            "manually_labeled_training_data": "RES-BUNDLED-DOMAIN-GOLD",
        },
        "en-keyword": {
            "domain_terminology_library": "RES-BUNDLED-EN-TERM",
            "classification_standard_mapping_table": "RES-BUNDLED-EN-CLASS-MAP",
        },
        "citation-intent": {"preprocessed_training_set": "RES-BUNDLED-CITATION-INTENT"},
        "general-ner": {"general_domain_annotated_corpus": "RES-BUNDLED-NER-GENERAL"},
        "research-ner": {
            "multi_domain_scientific_corpus": "RES-BUNDLED-NER-RESEARCH",
            "manually_labeled_data": "RES-BUNDLED-NER-RESEARCH-GOLD",
        },
        "domain-ner": {
            "ontology_classification_system": "RES-BUNDLED-ONTOLOGY",
            "domain_labeled_training_data": "RES-BUNDLED-DOMAIN-NER-GOLD",
        },
    }
    resources = {key: {"source": "database", "resource_id": value} for key, value in resource_ids.get(tool_id, {}).items()}
    if tool_id in {"zh-classify", "en-classify", "domain-classify"}:
        field = {"zh-classify": "chinese_scientific_document_text", "en-classify": "english_scientific_document_text", "domain-classify": "domain_scientific_literature_data"}[tool_id]
        payload = {"input_type": "text", field: "研究知识图谱方法。", "document_title": "语义计算研究", **resources}
        if tool_id == "domain-classify":
            payload["professional_domain"] = "materials_science"
        return payload
    if tool_id == "structured-review":
        return {
            "input_type": "texts",
            "document_set": [
                {"document_id": "D1", "text": "语义模型研究"},
                {"document_id": "D2", "text": "知识图谱研究"},
                {"document_id": "D3", "text": "文本挖掘研究"},
                {"document_id": "D4", "text": "科研分类研究"},
            ],
            "topic_or_keywords": "语义计算",
            "document_metadata": [
                {"document_id": f"D{index}", "title": f"文献{index}"} for index in range(1, 5)
            ],
        }
    if tool_id == "deep-cluster":
        return {
            "input_type": "texts",
            "cluster_dimension": "technology",
            "scientific_document_texts": [{"document_id": f"D{i}", "text": f"第{i}篇语义模型研究"} for i in range(1, 5)],
            "document_metadata": [{"document_id": f"D{i}", "title": f"文献{i}", "publication_date": f"202{i}-01-01"} for i in range(1, 5)],
        }
    if tool_id == "cluster-label":
        return {"input_type": "texts", "cluster_phrase_sets": [
            {"cluster_id": "C1", "phrases": ["语义模型", "知识图谱"]},
            {"cluster_id": "C2", "phrases": ["文本挖掘", "科研分类"]},
        ], "label_length_limit": 12, "language_type": "auto", "distinctiveness_threshold": 0.75}
    special = {
        "zh-abstract-move": {"chinese_scientific_abstract": "本文研究语义计算与知识图谱方法。"},
        "en-abstract-move": {"english_scientific_abstract": "We study semantic computing and knowledge graphs."},
        "fund-move": {"project_document_text": "本项目拟研究语义计算方法。", "project_name": "语义计算项目"},
        "zh-keyword": {"chinese_scientific_abstract": "本文研究语义计算与知识图谱方法。"},
        "en-keyword": {"english_scientific_abstract": "We study semantic computing and knowledge graphs.", **resources},
        "rq-detect": {"scientific_document_fragment": "现有方法存在不足，如何提高精度？"},
        "citation-sentiment": {"scientific_document_full_text": "已有研究[1]证明该方法有效。", "citation_sentence_and_context": [{"citation_sentence": "已有研究[1]证明该方法有效。", "previous_context": "背景。", "next_context": "继续研究。"}], "citation_metadata": [{"citation_marker": "[1]", "work_name": "被引文献"}]},
        "citation-intent": {"citation_sentence_and_context": [{"citation_sentence": "本文采用已有方法[1]。", "previous_context": "背景。", "next_context": "开展实验。"}], "citation_metadata": [{"citation_marker": "[1]", "work_name": "被引文献"}], **resources},
        "definition-detect": {"scientific_document_fragment_or_batch_text": "语义计算是对文本语义进行结构化计算的方法。"},
        "general-ner": {"bilingual_scientific_document_text": "燕山大学开展语义计算研究。", **resources},
        "research-ner": {"academic_abstract_or_technical_report_text": "采用机器学习分析科研数据。", **resources},
        "domain-ner": {"domain_scientific_document_text": "阿司匹林抑制血小板聚集。", **resources},
        "relation-extract": {"text": "模型使用知识图谱。"},
    }
    return {"input_type": "text", **special[tool_id]}


class FullstackContractTests(unittest.TestCase):
    def test_all_19_vue_contracts_persist_unified_results(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            task_repo, _ = repositories(Path(temporary_directory))
            service = ToolIntegrationService(FakeSemanticService(), task_repo)
            expected_keys = {
                "zh-abstract-move": "moves", "en-abstract-move": "moves", "fund-move": "moves",
                "zh-classify": "classifications", "en-classify": "classifications", "domain-classify": "classifications",
                "zh-keyword": "keywords", "en-keyword": "keywords", "rq-detect": "research_question_sentences",
                "citation-sentiment": "citations", "citation-intent": "citations", "definition-detect": "definitions",
                "general-ner": "entities", "research-ner": "entities", "domain-ner": "entities",
                "relation-extract": "triples", "deep-cluster": "clusters", "cluster-label": "labels",
                "structured-review": "tree",
            }
            for contract in CONTRACTS:
                with self.subTest(tool_id=contract.tool_id):
                    result = service.execute(contract.tool_id, payload_for(contract.tool_id))
                    self.assertEqual(result["code"], 0, (contract.tool_id, result))
                    self.assertEqual(result["data"]["status"], "succeeded")
                    self.assertEqual(result["data"]["success_count"], 1)
                    record = result["data"]["results"][0]
                    self.assertIn(expected_keys[contract.tool_id], record["result"])
                    for field in get_vue_contract(contract.tool_id).result_fields:
                        self.assertIn(field, record["result"], (contract.tool_id, field))
                    self.assertIsNotNone(task_repo.get_task(result["data"]["task_id"]))
                    self.assertIsNotNone(task_repo.get_result(record["record_id"]))
            projection_tables = (
                "move_results", "move_segments", "classification_results", "classification_candidates",
                "keyword_results", "keyword_items", "research_question_results", "research_question_items",
                "citation_results", "citation_items", "definition_results", "definition_items",
                "entity_results", "entity_mentions", "relation_results", "relation_triples",
                "cluster_runs", "clusters", "cluster_memberships", "cluster_label_results", "cluster_labels",
                "review_results", "review_nodes", "review_evidence_links",
            )
            with task_repo.db.session() as session:
                for table in projection_tables:
                    with self.subTest(projection_table=table):
                        row = session.fetchone(f"SELECT COUNT(*) AS total FROM {table}")
                        self.assertGreater(row["total"], 0, table)

    def test_collection_dictionary_history_and_exports(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            task_repo, resource_repo = repositories(root)
            resources = ResourceService(resource_repo)
            collection = resources.create_collection({
                "name": "科研文献集合",
                "documents": [
                    {"title": "文献一", "abstract": "语义计算研究"},
                    {"title": "文献二", "text": "知识图谱研究"},
                ],
            })
            self.assertEqual(collection["document_count"], 2)
            dictionary = resources.create_dictionary({
                "name": "领域词典", "language": "zh", "weight_boost": 0.08,
                "terms": ["语义计算", "知识图谱"],
            })
            self.assertEqual(dictionary["term_count"], 2)
            dictionary_v2 = resources.create_dictionary({
                "name": "领域词典", "language": "zh", "weight_boost": 0.1,
                "terms": "语义计算\n知识图谱\n文本挖掘",
            })
            self.assertEqual(dictionary_v2["id"], dictionary["id"])
            self.assertEqual(dictionary_v2["version"], 2)
            self.assertEqual(dictionary_v2["term_count"], 3)
            stored_dictionary = resources.get_dictionary(dictionary["id"], 1)
            self.assertEqual(stored_dictionary["version"], 1)
            self.assertEqual(len(stored_dictionary["versions"]), 2)

            capturing_service = CapturingKeywordService()
            keyword_integration = ToolIntegrationService(capturing_service, task_repo, resource_repo)
            keyword_result = keyword_integration.execute("zh-keyword", {
                "input_type": "text",
                "abstract": "本文研究语义计算与知识图谱。",
                "dictionary_id": dictionary["id"],
                "dictionary_version": 1,
                "min_keywords": 1,
                "max_keywords": 8,
            })
            loaded_dictionary = capturing_service.request.params["custom_dictionary"]
            self.assertEqual(loaded_dictionary["version"], 1)
            self.assertEqual({term["term"] for term in loaded_dictionary["terms"]}, {"语义计算", "知识图谱"})
            keyword_payload = keyword_result["data"]["results"][0]["result"]
            self.assertEqual(keyword_payload["dictionary_usage"]["dictionary_id"], dictionary["id"])

            service = ToolIntegrationService(FakeSemanticService(), task_repo)
            result = service.execute("relation-extract", payload_for("relation-extract"))
            record_id = result["data"]["results"][0]["record_id"]
            exporter = ExportService(task_repo, resource_repo)
            exporter.export_dir = root / "exports"
            for export_format in ("json", "csv", "rdf"):
                exported = exporter.create(record_id, export_format)
                stored = exporter.get(exported["id"])
                self.assertIsNotNone(stored)
                self.assertTrue(Path(stored["path"]).is_file())

    def test_external_upstream_records_drive_relation_task(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            task_repo, _ = repositories(Path(temporary_directory))
            upstream = UpstreamRecordService(task_repo)
            entity = upstream.create("entity", {
                "text": "模型使用知识图谱。",
                "entities": [{"text": "模型", "type": "METHOD"}, {"text": "知识图谱", "type": "METHOD"}],
            })
            dependency = upstream.create("dependency", {
                "text": "模型使用知识图谱。",
                "dependencies": [{"head": "使用", "dependent": "知识图谱", "relation": "VOB"}],
            })
            service = ToolIntegrationService(FakeSemanticService(), task_repo)
            result = service.execute("relation-extract", {
                "input_type": "upstream_records",
                "upstream_entity_record_id": entity["record_id"],
                "upstream_dependency_record_id": dependency["record_id"],
            })
            self.assertEqual(result["code"], 0)
            relation_record = result["data"]["results"][0]["record_id"]
            with task_repo.db.session() as session:
                dependencies = session.fetchall("SELECT * FROM record_dependencies WHERE record_id=?", (relation_record,))
            self.assertEqual(len(dependencies), 2)
            lineage = ResultGovernanceService(task_repo).lineage(relation_record)
            self.assertEqual(len(lineage["upstream"]), 2)

    def test_confirmation_feedback_and_archive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            task_repo, _ = repositories(Path(temporary_directory))
            service = ToolIntegrationService(FakeSemanticService(), task_repo)
            governance = ResultGovernanceService(task_repo)
            classification = service.execute("zh-classify", payload_for("zh-classify"))
            classification_record = classification["data"]["results"][0]["record_id"]
            stored_before = task_repo.get_result(classification_record)["result"]
            candidate = stored_before["candidate_classifications"][0]
            confirmation = governance.confirm_classification(classification_record, {
                "primary_code": candidate["main_code"],
                "secondary_codes": [candidate["aux_code"]] if candidate.get("aux_code") else [],
                "candidate_id": candidate["candidate_id"],
                "confirmed_path": candidate["classification_path"],
            })
            self.assertEqual(confirmation["primary_code"], "TP391")
            self.assertEqual(confirmation["status"], "confirmed")
            persisted_classification = task_repo.get_result(classification_record)
            self.assertEqual(persisted_classification["result"]["confirmation_status"], "confirmed")
            self.assertEqual(persisted_classification["result"]["manual_confirmation"]["primary_code"], "TP391")
            with task_repo.db.session() as session:
                projection = session.fetchone(
                    "SELECT confirmation_status FROM classification_results WHERE result_record_id=?",
                    (classification_record,),
                )
            self.assertEqual(projection["confirmation_status"], "confirmed")
            feedback = governance.feedback(classification_record, {"rating": 5, "comment": "结果正确"})
            self.assertEqual(feedback["result_record_id"], classification_record)

            labels = service.execute("cluster-label", payload_for("cluster-label"))
            label_record = labels["data"]["results"][0]["record_id"]
            label_confirmation = governance.confirm_cluster_label(label_record, {"cluster_id": "C1", "label_text": "语义建模"})
            self.assertEqual(label_confirmation["label_text"], "语义建模")
            self.assertTrue(task_repo.archive_task(classification["data"]["task_id"]))

    def test_classification_confirmation_rejects_foreign_candidate(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            task_repo, _ = repositories(Path(temporary_directory))
            service = ToolIntegrationService(FakeSemanticService(), task_repo)
            governance = ResultGovernanceService(task_repo)
            classification = service.execute("zh-classify", payload_for("zh-classify"))
            record_id = classification["data"]["results"][0]["record_id"]
            with self.assertRaisesRegex(ValueError, "candidate_id"):
                governance.confirm_classification(record_id, {
                    "primary_code": "TP391",
                    "candidate_id": "foreign-candidate",
                })
            candidate = task_repo.get_result(record_id)["result"]["candidate_classifications"][0]
            with self.assertRaisesRegex(ValueError, "secondary_codes"):
                governance.confirm_classification(record_id, {
                    "primary_code": candidate["main_code"],
                    "secondary_codes": ["FOREIGN"],
                    "candidate_id": candidate["candidate_id"],
                })

    def test_invalid_payloads_return_validation_errors_without_creating_tasks(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            task_repo, _ = repositories(Path(temporary_directory))
            service = ToolIntegrationService(FakeSemanticService(), task_repo)
            cases = [
                ("domain-classify", {"input_type": "text", "text": "测试", "domain": ""}),
                ("zh-keyword", {"input_type": "text", "abstract": "测试", "min_keywords": "bad"}),
                ("zh-keyword", {"input_type": "text", "abstract": "测试", "dictionary_id": "missing"}),
                ("cluster-label", {
                    "input_type": "texts",
                    "texts": [{"id": "D1", "text": "一"}, {"id": "D2", "text": "二"}],
                }),
                ("relation-extract", {"input_type": "upstream_records"}),
            ]
            for tool_id, payload in cases:
                with self.subTest(tool_id=tool_id):
                    result = service.execute(tool_id, payload)
                    self.assertEqual(result["code"], 42201)
            with task_repo.db.session() as session:
                row = session.fetchone("SELECT COUNT(*) AS total FROM analysis_tasks")
            self.assertEqual(row["total"], 0)

    def test_async_submission_can_be_polled(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            task_repo, _ = repositories(Path(temporary_directory))
            service = ToolIntegrationService(FakeSemanticService(), task_repo)
            accepted = service.submit("deep-cluster", payload_for("deep-cluster"))
            self.assertEqual(accepted["code"], 0)
            task_id = accepted["data"]["task_id"]
            task = None
            for _ in range(100):
                task = task_repo.get_task(task_id)
                if task and task["status"] in {"succeeded", "partial_failed", "failed", "cancelled"}:
                    break
                time.sleep(0.01)
            self.assertIsNotNone(task)
            self.assertEqual(task["status"], "succeeded")
            self.assertEqual(len(task_repo.list_results(task_id)), 1)


if __name__ == "__main__":
    unittest.main()
