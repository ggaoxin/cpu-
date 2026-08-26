"""The first five tool families must fail closed when GLM-5.2 is unavailable."""
from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import patch

from application.dto.common_dto import SemanticRequest
from application.service.semantic_service import SemanticApplicationService
from config.settings import settings
from infrastructure.rule_engine.rule_loader import RuleLoader


class OfflineGlm:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, *args, **kwargs):
        self.calls += 1
        raise ConnectionError("GLM-5.2 offline")


class GlmRequiredTests(unittest.TestCase):
    def test_startup_key_check_is_deployment_configurable(self):
        self.assertTrue(settings.GLM_MODEL)
        with patch.object(settings, "GLM_API_KEY", ""), patch.object(settings, "GLM_REQUIRED_AT_STARTUP", False):
            settings.ensure_ready()
        with patch.object(settings, "GLM_API_KEY", ""), patch.object(settings, "GLM_REQUIRED_AT_STARTUP", True):
            with self.assertRaisesRegex(RuntimeError, "GLM_API_KEY"):
                settings.ensure_ready()

    def test_first_five_tool_families_never_fall_back_locally(self):
        glm = OfflineGlm()
        service = SemanticApplicationService(glm, RuleLoader())
        paper = json.dumps({
            "title": "知识图谱语义分析",
            "abstract": "本文研究知识图谱与深度学习方法。",
            "keywords": ["知识图谱", "深度学习"],
        }, ensure_ascii=False)
        cases = (
            ("mr_zh_abstract", SemanticRequest(text="本文提出新方法并验证其有效性。")),
            ("mr_en_abstract", SemanticRequest(text="We propose and evaluate a semantic model.")),
            ("mr_zh_fund", SemanticRequest(text="立项依据。研究目标。技术方案。预期成果。应用价值。")),
            ("ac_zh", SemanticRequest(text=paper)),
            ("ac_en", SemanticRequest(text=paper)),
            ("ac_domain", SemanticRequest(text=paper, params={"domain_code": "14"})),
            ("kw_zh", SemanticRequest(text="知识图谱与深度学习用于科技文献语义分析。")),
            ("kw_en", SemanticRequest(text="Knowledge graphs and deep learning support semantic analysis.")),
            ("rq_identify", SemanticRequest(text="现有方法难以处理长文本，如何提升其语义表示能力？")),
            ("cr_sentiment", SemanticRequest(text="已有研究[1]证明该方法有效。")),
            ("cr_intent", SemanticRequest(text="本文采用李四等（2021）的方法作为基线。")),
        )

        keyword_zh = types.ModuleType("training.keyword_phrase_miner")
        keyword_en = types.ModuleType("training.keyword_phrase_miner_en")
        for module in (keyword_zh, keyword_en):
            module.mine_candidates = lambda *args, **kwargs: []
            module.score_candidates = lambda candidates, *args, **kwargs: candidates

        with patch.dict(sys.modules, {
            "training.keyword_phrase_miner": keyword_zh,
            "training.keyword_phrase_miner_en": keyword_en,
        }), patch("application.service.semantic_service.logger.exception"):
            for code, request in cases:
                with self.subTest(code=code):
                    result = service.execute(code, request)
                    self.assertFalse(result.success)
                    self.assertTrue(result.error)
                    self.assertIsNone(result.data)

        # A deterministic pre-check may reject one malformed/no-candidate
        # request before the model boundary; every remaining request fails
        # closed instead of inventing a local business result.
        self.assertGreaterEqual(glm.calls, len(cases) - 1)


if __name__ == "__main__":
    unittest.main()
